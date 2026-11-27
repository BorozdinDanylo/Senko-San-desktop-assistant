from datetime import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HELPER = Path(__file__).resolve().parents[1] / 'skills/todo/scripts/tasks.py'
spec = importlib.util.spec_from_file_location('todo_tasks', HELPER)
tasks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tasks)


class TodoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Path(self.temp.name) / 'todo.md'

    def run_helper(self, *arguments, ok=True):
        result = subprocess.run([sys.executable, str(HELPER), '--file', str(self.store), *arguments], cwd='/', capture_output=True, text=True, timeout=5)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if ok else 1, data)
        self.assertEqual(data['ok'], ok, data)
        return data

    def add(self, description='Перевірити голос', **fields):
        args = ['add', '--description', description]
        for key, value in fields.items():
            args += ['--' + key.replace('_', '-'), value]
        return self.run_helper(*args)

    def test_exclusive_initialization_and_restart_persistence(self):
        self.assertFalse(self.run_helper('list')['exists'])
        self.assertFalse(self.store.exists())
        self.assertTrue(self.run_helper('init')['created'])
        entry = self.add()
        saved = self.store.read_bytes()
        self.assertFalse(self.run_helper('init')['created'])
        self.assertEqual(self.store.read_bytes(), saved)
        self.assertEqual(self.run_helper('list', entry['id'])['tasks'][entry['id']], entry['task'])
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o600)

    def test_lifecycle_and_unrelated_entries_preserved(self):
        first = self.add()
        second = self.add('Інша справа')
        untouched = tasks.parse(self.store.read_text())[2][second['id']]
        for status in ('in_progress', 'blocked', 'deferred', 'pending', 'completed', 'cancelled'):
            result = self.run_helper('update', first['id'], '--status', status, '--notes', 'Перевірено або очікує', '--effort', '1–2 години; непевно', '--priority', 'high')
            self.assertEqual(result['task']['status'], status)
            self.assertEqual(result['task']['created'], first['task']['created'])
            self.assertIn('updated', result['task'])
            self.assertEqual(tasks.parse(self.store.read_text())[2][second['id']], untouched)
        renamed = self.run_helper('update', first['id'], '--description', 'Уточнена справа', '--deadline', '2027-01-01', '--reason', 'Користь')
        self.assertEqual(renamed['task']['description'], 'Уточнена справа')
        cleared = self.run_helper('update', first['id'], '--deadline', '')
        self.assertNotIn('deadline', cleared['task'])
        self.assertTrue(self.run_helper('remove', first['id'])['removed'])
        self.assertNotIn(first['id'], self.run_helper('list')['tasks'])
        self.assertEqual(tasks.parse(self.store.read_text())[2][second['id']], untouched)

    def test_creation_uses_actual_os_date_with_timezone_and_unique_ids(self):
        before = datetime.fromisoformat(subprocess.check_output(['date', '-Is'], text=True).strip())
        first = self.add()
        second = self.add('Ще справа')
        after = datetime.fromisoformat(subprocess.check_output(['date', '-Is'], text=True).strip())
        created = datetime.fromisoformat(first['task']['created'])
        self.assertIsNotNone(created.utcoffset())
        self.assertLessEqual(before, created)
        self.assertLessEqual(created, after)
        self.assertNotEqual(first['id'], second['id'])
        with patch.object(tasks.subprocess, 'check_output', return_value='2026-10-22T22:15:00+02:00\n') as clock:
            self.assertEqual(tasks.timestamp(), '2026-10-22T22:15:00+02:00')
            clock.assert_called_once_with(['date', '-Is'], text=True)

    def test_duplicates_are_idempotent_and_do_not_reprioritize_silently(self):
        first = self.add('Review voice, interruptions!', priority='high')
        original = self.store.read_bytes()
        result = self.add('review   VOICE interruptions', priority='low')
        self.assertEqual(result['duplicate'], first['id'])
        self.assertEqual(self.store.read_bytes(), original)
        self.run_helper('update', first['id'], '--status', 'completed')
        self.assertNotEqual(self.add('Review voice interruptions')['id'], first['id'])

    def test_dependencies_cycles_blocked_and_removal(self):
        parent = self.add('Підготовка')['id']
        child = self.add('Залежна справа', depends_on=parent)['id']
        original = self.store.read_bytes()
        self.run_helper('update', child, '--status', 'in_progress', ok=False)
        self.run_helper('update', parent, '--depends-on', child, ok=False)
        self.run_helper('remove', parent, ok=False)
        self.run_helper('update', child, '--depends-on', 'T-000000000000', ok=False)
        self.assertEqual(self.store.read_bytes(), original)
        self.run_helper('update', parent, '--status', 'cancelled')
        self.run_helper('update', child, '--status', 'in_progress', ok=False)
        self.run_helper('update', parent, '--status', 'completed')
        self.run_helper('update', child, '--status', 'in_progress')
        self.run_helper('update', child, '--status', 'blocked', '--notes', 'Потрібен доступ')
        self.assertEqual(self.run_helper('list', child)['tasks'][child]['status'], 'blocked')

    def test_invalid_edits_and_malformed_files_never_reset_content(self):
        entry = self.add()
        good = self.store.read_text()
        for flag, value in (('--status', 'running'), ('--priority', 'top'), ('--description', ''), ('--notes', 'line\n## injected'), ('--deadline', 'tomorrow'), ('--deadline', '2027-01-01T12:00:00')):
            self.run_helper('update', entry['id'], flag, value, ok=False)
            self.assertEqual(self.store.read_text(), good)
        block = tasks.parse(good)[2][entry['id']]
        for invalid in ('unrecognized document', good + block, good.replace('- status: pending', '- status: invalid'), good.replace('- created: ', '- created: invalid'), good + '\n## broken\n', good.replace('- effort: unknown', '- effort: unknown\n- effort: 10m')):
            self.store.write_text(invalid)
            self.run_helper('init', ok=False)
            self.run_helper('remove', entry['id'], ok=False)
            self.assertEqual(self.store.read_text(), invalid)

    def test_symlinks_lock_contention_and_failed_write(self):
        victim = self.store.parent / 'victim.md'
        victim.write_text('keep me')
        self.store.symlink_to(victim)
        self.run_helper('init', ok=False)
        self.assertEqual(victim.read_text(), 'keep me')
        self.store.unlink()
        self.run_helper('init')
        lock = self.store.with_name('.todo.md.lock')
        with lock.open('a') as file:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_helper('add', '--description', 'busy', ok=False)
        original = self.store.read_text()
        with patch.object(tasks.os, 'replace', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):
                tasks.save(self.store, original, original + '\n')
        self.assertEqual(self.store.read_text(), original)
        self.assertEqual(set(self.store.parent.iterdir()), {self.store, victim, lock})

    def test_task_text_remains_data(self):
        marker = self.store.parent / 'should-not-exist'
        description = 'Do not run $(touch ' + str(marker) + ') or `id`; inspect only'
        entry = self.add(description)
        self.assertEqual(entry['task']['description'], description)
        self.assertFalse(marker.exists())
