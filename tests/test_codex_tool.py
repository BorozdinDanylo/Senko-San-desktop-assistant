"""Offline contract tests; use the installed SDK, without starting a Codex server.

Only application registration and global queues are stubbed to avoid booting
unrelated assistant components. Failures describe defects in the audited file.
"""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from openai_codex.generated.v2_all import Turn, TurnCompletedNotification

SOURCE = Path(__file__).resolve().parents[1] / 'core/src/tools/codex/codex_tool.py'


def load_module():
    components = ModuleType('core.components')
    components.Queues = NS(text_analiz=None)
    registration = ModuleType('tools.types.tool')
    registration.Tool = type('Tool', (), {
        'initialize_class': staticmethod(lambda cls: cls),
        'tool': staticmethod(lambda method: method),
    })
    spec = importlib.util.spec_from_file_location('_codex_tool_audit', SOURCE)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        'core.components': components,
        'tools.types.tool': registration,
        spec.name: module,
    }):
        spec.loader.exec_module(module)
    return module


class CodexToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {'LOG_DIR': self.temp.name}):
            self.module = load_module()
        self.tool = self.module.CodexTool
        self.module.Queues.text_analiz = asyncio.Queue()
        self.handle = NS(id='turn-1')
        self.thread = NS(id='thread-1', turn=AsyncMock(return_value=self.handle))
        self.tool.codex = NS(
            thread_start=AsyncMock(return_value=self.thread),
            thread_resume=AsyncMock(return_value=self.thread),
        )

    def task(self, directory='/project'):
        return self.module.Task(directory, self.module.CodexThread(self.thread, True), self.handle)

    async def stream(self, *events):
        for event in events:
            yield event

    async def test_start_registers_task_and_monitor(self):
        monitor = AsyncMock()
        with patch.object(self.tool, 'checking_task', monitor):
            result = await self.tool.start_task('inspect project', '/project')
            await asyncio.sleep(0)
        self.assertIn('turn-1', result)
        self.assertIn('turn-1', self.tool.tasks)
        self.assertIs(self.tool.tasks['turn-1'].working_thread, self.tool.threads['thread-1'])
        monitor.assert_awaited_once()

    async def test_concurrent_starts_reserve_directory_before_await(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed_start(**kwargs):
            entered.set()
            await release.wait()
            return self.thread

        self.tool.codex.thread_start.side_effect = delayed_start
        with patch.object(self.tool, 'checking_task', AsyncMock()):
            first = asyncio.create_task(self.tool.start_task('first', '/project'))
            await asyncio.wait_for(entered.wait(), timeout=1)
            try:
                second = await self.tool.start_task('second', '/project')
                self.assertIn('Cannot start', second)
            finally:
                release.set()
                await first
            await asyncio.sleep(0)
        self.assertEqual(self.tool.codex.thread_start.await_count, 1)

    def test_import_without_log_dir_is_supported(self):
        with patch.dict(os.environ):
            os.environ.pop('LOG_DIR', None)
            load_module()

    async def test_same_directory_is_rejected(self):
        self.tool.tasks['existing'] = self.task()
        result = await self.tool.start_task('inspect', '/project')
        self.assertIn('Cannot start', result)
        self.tool.codex.thread_start.assert_not_awaited()

    async def test_equivalent_directory_is_rejected(self):
        self.tool.tasks['existing'] = self.task()
        result = await self.tool.start_task('inspect', '/project/./')
        self.assertIn('Cannot start', result)
        self.tool.codex.thread_start.assert_not_awaited()

    async def test_busy_thread_cannot_be_reused_in_another_directory(self):
        task = self.task()
        self.tool.tasks['existing'] = task
        self.tool.threads['thread-1'] = task.working_thread
        result = await self.tool.start_task('inspect', '/another', 'thread-1')
        self.assertIn('Cannot start', result)
        self.tool.codex.thread_resume.assert_not_awaited()

    async def test_failed_turn_notification_includes_error(self):
        turn = Turn.model_validate({
            'id': 'turn-1', 'items': [], 'status': 'failed',
            'error': {'message': 'quota exhausted', 'additionalDetails': None, 'codexErrorInfo': None},
        })
        event = NS(payload=TurnCompletedNotification(thread_id='thread-1', turn=turn))
        self.handle.stream = lambda: self.stream(event)
        task = self.task()
        self.tool.tasks['turn-1'] = task
        await self.tool.checking_task(task, 'turn-1')
        notice = self.module.Queues.text_analiz.get_nowait()
        self.assertIn('quota exhausted', notice)
        self.assertFalse(task.working_thread.busy)
        self.assertNotIn('turn-1', self.tool.tasks)

    async def test_missing_log_directory_does_not_prevent_consuming_result(self):
        self.module.LOG_PATH = Path(self.temp.name) / 'not-created'
        turn = Turn(id='turn-1', items=[], status='completed')
        event = NS(payload=TurnCompletedNotification(thread_id='thread-1', turn=turn))
        self.handle.stream = lambda: self.stream(event)
        await self.tool.checking_task(self.task(), 'turn-1')
        notice = self.module.Queues.text_analiz.get_nowait()
        self.assertIn('[Background Codex Task Result]', notice)

    async def test_stream_ending_without_completion_notifies_user(self):
        self.handle.stream = lambda: self.stream()
        await self.tool.checking_task(self.task(), 'turn-1')
        self.assertFalse(self.module.Queues.text_analiz.empty())

    async def test_start_failure_releases_reservations(self):
        self.thread.turn.side_effect = RuntimeError('unavailable')
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            await self.tool.start_task('inspect', '/project', 'thread-1')
        self.assertFalse(self.tool.starting_directories)
        self.assertFalse(self.tool.starting_threads)
        self.assertFalse(self.tool.tasks)
        self.assertFalse(self.tool.threads)

    async def test_cancel_interrupts_remote_turn_without_dropping_tracking(self):
        self.handle.interrupt = AsyncMock()
        task = self.task()
        self.tool.tasks['turn-1'] = task
        result = await self.tool.cancel_task('turn-1')
        self.handle.interrupt.assert_awaited_once()
        self.assertIn('Cancellation requested', result)
        self.assertIs(self.tool.tasks['turn-1'], task)
        self.assertIn('No running', await self.tool.cancel_task('missing'))

    async def test_unwritable_log_still_delivers_completion_and_cleans_state(self):
        turn = Turn(id='turn-1', items=[], status='completed')
        event = NS(payload=TurnCompletedNotification(thread_id='thread-1', turn=turn))
        self.handle.stream = lambda: self.stream(event)
        task = self.task()
        self.tool.tasks['turn-1'] = task
        self.tool.threads['thread-1'] = task.working_thread
        with patch.object(Path, 'open', side_effect=PermissionError('denied')):
            with self.assertLogs(self.module.logger, level='WARNING'):
                await self.tool.checking_task(task, 'turn-1')
        self.assertIn('[Background Codex Task Result]', self.module.Queues.text_analiz.get_nowait())
        self.assertFalse(self.tool.tasks)
        self.assertFalse(self.tool.threads)
        self.assertFalse(task.working_thread.busy)

    async def test_log_write_failure_still_delivers_final_message(self):
        from openai_codex.generated.v2_all import AgentMessageThreadItem, ThreadItem
        from openai_codex.models import ItemCompletedNotification
        item = ThreadItem(root=AgentMessageThreadItem(id='message-1', text='Done', type='agentMessage'))
        message = NS(payload=ItemCompletedNotification(thread_id='thread-1', turn_id='turn-1', item=item, completed_at_ms=0))
        turn = Turn(id='turn-1', items=[item], status='completed')
        completed = NS(payload=TurnCompletedNotification(thread_id='thread-1', turn=turn))
        self.handle.stream = lambda: self.stream(message, completed)
        log = MagicMock()
        log.write.side_effect = OSError('disk full')
        with patch.object(Path, 'open', return_value=log):
            with self.assertLogs(self.module.logger, level='WARNING'):
                await self.tool.checking_task(self.task(), 'turn-1')
        self.assertIn('Result:\nDone', self.module.Queues.text_analiz.get_nowait())

    async def test_shutdown_interrupts_turn_and_joins_monitor(self):
        self.handle.interrupt = AsyncMock()
        self.tool.codex.close = AsyncMock()
        waiting = asyncio.Event()

        async def stream():
            waiting.set()
            await asyncio.Event().wait()
            yield

        self.handle.stream = stream
        await self.tool.start_task('inspect', '/project')
        await waiting.wait()
        await self.tool.shutdown()
        self.handle.interrupt.assert_awaited_once()
        self.tool.codex.close.assert_awaited_once()
        self.assertFalse(self.tool.monitors)
        self.assertFalse(self.tool.tasks)
        self.assertFalse(self.tool.threads)

    async def test_threads_list_follows_pagination(self):
        def thread(identifier):
            return NS(id=identifier, name=identifier, cwd=NS(root='/project'), status=NS(root='idle'))
        self.tool.codex.thread_list = AsyncMock(side_effect=[
            NS(data=[thread('first')], next_cursor='page-2'),
            NS(data=[thread('second')], next_cursor=None),
        ])
        result = await self.tool.threads_list()
        self.assertIn('first', result)
        self.assertIn('second', result)


if __name__ == '__main__':
    unittest.main()
