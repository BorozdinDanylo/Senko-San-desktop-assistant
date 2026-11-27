#!/usr/bin/env python3
"""Small terminal-invoked Markdown editor. No task execution or scheduling."""
import argparse
from contextlib import contextmanager
from datetime import date, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import uuid

DEFAULT_FILE = Path('/home/Senka/todo.md')
HEADER = '# Senko-San tasks\n\n'
STATUSES = ('pending', 'in_progress', 'blocked', 'deferred', 'completed', 'cancelled')
PRIORITIES = ('critical', 'high', 'normal', 'low')
REQUIRED = ('description', 'status', 'priority', 'created', 'effort')
EDITABLE = ('description', 'status', 'priority', 'effort', 'deadline', 'depends_on', 'reason', 'memory', 'notes')
ID = re.compile(r'T-[0-9a-f]{12}')


def timestamp():
    value = subprocess.check_output(['date', '-Is'], text=True).strip()
    valid_time(value)
    return value


def valid_time(value):
    if datetime.fromisoformat(value).utcoffset() is None:
        raise ValueError('Timestamp must include timezone')


def dependencies(task):
    return [value.strip() for value in task.get('depends_on', '').split(',') if value.strip()]


def normalized(value):
    return ' '.join(re.findall(r'\w+', value.casefold()))


def parse(text):
    if not text.startswith('# Senko-San tasks\n'):
        raise ValueError('Unrecognized task file header; inspect without overwriting')
    parts = re.split(r'(?m)^## ', text)
    tasks = {}
    for part in parts[1:]:
        heading, _, body = part.partition('\n')
        if not ID.fullmatch(heading) or heading in tasks:
            raise ValueError('Invalid or duplicate task ID: ' + heading)
        fields = {}
        for line in body.splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r'- ([a-z_]+): (.*)', line)
            if not match or match[1] in fields:
                raise ValueError('Invalid or repeated field in ' + heading)
            fields[match[1]] = match[2]
        tasks[heading] = fields
    validate(tasks)
    return parts[0], tasks, {part.split('\n', 1)[0]: '## ' + part for part in parts[1:]}


def validate(tasks):
    for task_id, fields in tasks.items():
        if any(not fields.get(key, '').strip() for key in REQUIRED):
            raise ValueError('Missing required metadata in ' + task_id)
        if fields['status'] not in STATUSES or fields['priority'] not in PRIORITIES:
            raise ValueError('Invalid status or priority in ' + task_id)
        for key, value in fields.items():
            if '\n' in value or '\r' in value or not value.strip():
                raise ValueError('Fields must be nonempty single-line values: ' + key)
        valid_time(fields['created'])
        if 'updated' in fields:
            valid_time(fields['updated'])
        if 'deadline' in fields:
            value = fields['deadline']
            if len(value) == 10:
                date.fromisoformat(value)
            else:
                valid_time(value)
        for dep in dependencies(fields):
            if dep not in tasks:
                raise ValueError('Missing dependency ' + dep)
        if fields['status'] == 'in_progress' and any(tasks[dep]['status'] != 'completed' for dep in dependencies(fields)):
            raise ValueError('In-progress task has unmet dependencies: ' + task_id)
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            raise ValueError('Dependency cycle at ' + task_id)
        if task_id not in visited:
            visiting.add(task_id)
            for dep in dependencies(tasks[task_id]):
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)
    for task_id in tasks:
        visit(task_id)


def render(task_id, fields):
    return '## ' + task_id + '\n' + ''.join(f'- {key}: {value}\n' for key, value in fields.items()) + '\n'


def read(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'r', encoding='utf-8') as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Task store must be a regular file without hard links')
        return file.read()


@contextmanager
def locked(path):
    fd = os.open(path.with_name('.' + path.name + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'a') as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            raise ValueError('Invalid lock file')
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def save(path, original, content):
    parse(content)
    if read(path) != original:
        raise ValueError('Task file changed; reread before retrying')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if original is None:
            os.link(temporary, path)  # Exclusive initialization: never replace an existing file.
            os.unlink(temporary)  # Drop the temporary link before checking the live file.
        else:
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            if read(path) != original:
                raise ValueError('Task file changed; reread before retrying')
            os.replace(temporary, path)
        if read(path) != content:
            raise OSError('Read-back verification failed')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def operate(args):
    path = args.file.absolute()
    with locked(path):
        original = read(path)
        preamble, tasks, blocks = parse(original if original is not None else HEADER)
        if args.action == 'list':
            if args.id and args.id not in tasks:
                raise ValueError('Unknown task ID: ' + args.id)
            return {'tasks': {args.id: tasks[args.id]} if args.id else tasks, 'exists': original is not None}
        if args.action == 'init':
            if original is None:
                save(path, None, HEADER)
            return {'created': original is None, 'tasks': tasks}
        task_id = getattr(args, 'id', None)
        if args.action in ('update', 'remove') and task_id not in tasks:
            raise ValueError('Unknown task ID: ' + task_id)
        if args.action == 'remove':
            if any(task_id in dependencies(task) for task in tasks.values()):
                raise ValueError('Task is referenced by dependencies; reconcile those first')
            del tasks[task_id]
            del blocks[task_id]
        else:
            fields = {key: getattr(args, key) for key in EDITABLE if getattr(args, key, None) is not None}
            candidate = {**tasks.get(task_id, {}), **fields}
            if args.action == 'add' or 'description' in fields:
                for other_id, other in tasks.items():
                    if other_id != task_id and other['status'] not in ('completed', 'cancelled') and normalized(other['description']) == normalized(candidate['description']):
                        return {'duplicate': other_id, 'task': other, 'changed': False}
            if args.action == 'add':
                task_id = 'T-' + uuid.uuid4().hex[:12]
                while task_id in tasks:
                    task_id = 'T-' + uuid.uuid4().hex[:12]
                candidate = {'description': args.description, 'status': 'pending', 'priority': args.priority, 'created': timestamp(), 'effort': args.effort, **fields}
            else:
                candidate['updated'] = timestamp()
            for key in tuple(candidate):
                if candidate[key] == '' and key not in REQUIRED:
                    del candidate[key]
            tasks[task_id] = candidate
            blocks[task_id] = render(task_id, candidate)
        validate(tasks)
        save(path, original, preamble.rstrip('\n') + '\n\n' + ''.join(blocks.values()))
        return {'id': task_id, 'task': tasks.get(task_id), 'removed': args.action == 'remove'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, default=DEFAULT_FILE, help='Alternate store for isolated tests')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('init')
    listing = commands.add_parser('list')
    listing.add_argument('id', nargs='?')
    for action in ('add', 'update'):
        command = commands.add_parser(action)
        if action == 'update':
            command.add_argument('id')
        for key in EDITABLE:
            if action == 'add' and key == 'status':
                continue
            options = {'required': True} if action == 'add' and key == 'description' else {}
            if action == 'add' and key in ('priority', 'effort'):
                options['default'] = 'normal' if key == 'priority' else 'unknown'
            command.add_argument('--' + key.replace('_', '-'), **options)
    commands.add_parser('remove').add_argument('id')
    args = parser.parse_args()
    try:
        print(json.dumps({'ok': True, **operate(args)}, ensure_ascii=False))
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
