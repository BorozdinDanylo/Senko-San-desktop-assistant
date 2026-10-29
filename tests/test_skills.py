import os
from pathlib import Path
import subprocess
import sys
import unittest

from senko import NewMessage, SENKO_PROMPT


class SkillTests(unittest.TestCase):
    def test_static_prompt_catalog_and_no_embedded_workflows(self):
        project = Path(__file__).resolve().parents[1]
        self.assertEqual(SENKO_PROMPT, (project / 'senko_prompt.md').read_text())
        for name in ('memory', 'todo'):
            self.assertEqual(SENKO_PROMPT.count(f'/home/Senka/skills/{name}/SKILL.md'), 1)
            body = (project / 'skills' / name / 'SKILL.md').read_text().split('---', 2)[2].strip()
            self.assertNotIn(body, SENKO_PROMPT)

    def test_static_catalog_does_not_access_runtime_skills_at_startup(self):
        script = """
from pathlib import Path
from unittest.mock import patch
with patch.object(Path, 'rglob', side_effect=AssertionError('dynamic discovery called')):
    from senko import SENKO_PROMPT
    print(SENKO_PROMPT)
"""
        result = subprocess.run([sys.executable, '-c', script], cwd='/', env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src')}, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, SENKO_PROMPT + '\n')

    def test_empty_and_interrupted_history(self):
        NewMessage.clear()
        self.assertEqual(NewMessage.get_message(), '')
        NewMessage.add_text('First.')
        NewMessage.add_text('Second.')
        NewMessage.spoken('First.')
        history = NewMessage.get_message()
        self.assertIn('First.', history.split('Unspoken text:')[0])
        self.assertIn('Second.', history.split('Unspoken text:')[1])
        self.assertEqual(NewMessage.get_message(), '')
        NewMessage.add_text('Unheard.')
        self.assertIn('<empty>', NewMessage.get_message().split('Unspoken text:')[0])


class TerminalIntegrationTests(unittest.TestCase):
    def test_real_terminal_tools_load_both_skills_and_manage_tasks(self):
        # Load the real terminal tool without initializing unrelated Codex/GPU services.
        script = '''
import asyncio, json, sys, types
from pathlib import Path
package = types.ModuleType('tools')
package.__path__ = [str(Path('src/tools').resolve())]
sys.modules['tools'] = package
from tools.terminal.terminal_tool import TerminalTool
from tools.types.tool import Tool
from openai.types.responses import ResponseFunctionToolCall
async def settle(coroutine):
    # Keep a timer active: this sandbox can miss cross-thread selector wakeups.
    task = asyncio.create_task(coroutine)
    for _ in range(500):
        if task.done():
            return task.result()
        await asyncio.sleep(.01)
    task.cancel()
    raise TimeoutError('terminal tool did not finish')
async def main():
    call = ResponseFunctionToolCall(type='function_call', call_id='memory', name='terminal_command', arguments=json.dumps({'command': "cat -- /home/Senka/skills/memory/SKILL.md"}))
    output = await settle(Tool.execute(call))
    data = json.loads(output['output'])
    assert data['success'] and '## Store and reconcile' in data['result'], data
    assert '/home/Senka/memory/' in data['result']
    todo = await settle(TerminalTool.command("cat -- /home/Senka/skills/todo/SKILL.md"))
    assert '## Choose what deserves attention next' in todo
    import tempfile, shlex
    with tempfile.TemporaryDirectory() as sandbox:
        store = shlex.quote(str(Path(sandbox) / 'todo.md'))
        helper = 'python3 /home/Senka/skills/todo/scripts/tasks.py --file ' + store
        result = json.loads(await settle(TerminalTool.command(helper + ' init')))
        assert result['ok'] and result['created']
        result = json.loads(await settle(TerminalTool.command(helper + " add --description 'Terminal integration task'")))
        assert result['ok'] and result['task']['status'] == 'pending'
        task_id = result['id']
        result = json.loads(await settle(TerminalTool.command(helper + ' update ' + task_id + ' --status completed')))
        assert result['ok'] and result['task']['status'] == 'completed'
        result = json.loads(await settle(TerminalTool.command(helper + ' list ' + task_id)))
        assert result['tasks'][task_id]['status'] == 'completed'
    # Apply the loaded read-only guidance to locate the configured root index.
    output = await settle(TerminalTool.command("if test -r /home/Senka/memory/index.md; then sed -n '1,20p' /home/Senka/memory/index.md; else printf 'memory-index-unavailable'; fi"))
    print('MEMORY_TOOL_OK', output)
    bad = await Tool.execute(ResponseFunctionToolCall(type='function_call', call_id='bad', name='missing_tool', arguments='{}'))
    assert json.loads(bad['output'])['error'] == 'KeyError'
    TerminalTool.process.close(force=True)
loop = asyncio.new_event_loop()
try:
    loop.run_until_complete(main())
finally:
    loop.close()
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('MEMORY_TOOL_OK', result.stdout)
