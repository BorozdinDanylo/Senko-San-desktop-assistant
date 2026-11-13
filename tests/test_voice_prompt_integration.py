import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

from senko import NewMessage


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_tool_continuation_and_history_order(self):
        fake_tool = types.SimpleNamespace(tools_shamas=[], execute=AsyncMock(return_value={
            'type': 'function_call_output', 'call_id': 'call', 'output': '{"success":true}'
        }))
        with patch.dict(sys.modules, {'tools': types.SimpleNamespace(Tool=fake_tool)}):
            from senko import Speaker
        from openai.types.responses import ResponseFunctionToolCall
        call = ResponseFunctionToolCall(type='function_call', call_id='call', name='terminal_command', arguments='{"command":"true"}')

        async def stream(events):
            for event in events:
                yield event

        client = AsyncMock(side_effect=[
            stream([types.SimpleNamespace(type='response.output_item.done', item=call)]),
            stream([types.SimpleNamespace(type='response.output_text.delta', delta='Готово.'),
                    types.SimpleNamespace(type='response.output_text.delta', delta=' Деталі')]),
            stream([]),
        ])
        speaker = Speaker.__new__(Speaker)
        speaker.text_analiz = asyncio.Queue()
        speaker.tts_queue = asyncio.Queue()
        speaker.history = []
        speaker.client = types.SimpleNamespace(responses=types.SimpleNamespace(create=client))
        NewMessage.clear()
        speaker.text_analiz.put_nowait('Перевір')
        task = asyncio.create_task(speaker.live())
        try:
            self.assertEqual(await asyncio.wait_for(speaker.tts_queue.get(), 1), 'Готово.')
            self.assertEqual(await asyncio.wait_for(speaker.tts_queue.get(), 1), ' Деталі')
            fake_tool.execute.assert_awaited_once()
            self.assertEqual(client.await_count, 2)
            NewMessage.spoken('Готово.')
            speaker.text_analiz.put_nowait('Що далі?')
            for _ in range(30):
                if client.await_count == 3:
                    break
                await asyncio.sleep(.01)
            history = client.call_args.kwargs['input']
            self.assertEqual(history[-1]['content'], 'Що далі?')
            annotation = history[-2]['content']
            self.assertIn('Готово.', annotation.split('Unspoken text:')[0])
            self.assertIn('Деталі', annotation.split('Unspoken text:')[1])
            self.assertTrue(any(item.get('type') == 'function_call_output' for item in history))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            NewMessage.clear()

    async def test_tts_discards_synthesis_from_previous_generation(self):
        fish = types.ModuleType('fishaudio')
        fish.AsyncFishAudio = object
        utils = types.ModuleType('fishaudio.utils')
        utils.play = lambda audio: None
        with patch.dict(sys.modules, {'fishaudio': fish, 'fishaudio.utils': utils}), patch.dict('os.environ', {'SENKO_SAN_API_KEY': 'test', 'SENKO_SAN_VOICE_ID': 'test'}):
            module = importlib.import_module('voice.model.senko')
        voice = module.SenkoVoice.__new__(module.SenkoVoice)
        voice.tts_queue = asyncio.Queue()
        voice.audio_queue = asyncio.Queue()
        started = asyncio.Event()
        release = asyncio.Event()

        async def convert(**kwargs):
            started.set()
            await release.wait()
            return b'audio'

        voice.client = types.SimpleNamespace(tts=types.SimpleNamespace(convert=convert))
        NewMessage.clear()
        NewMessage.add_text('Старе.')
        voice.tts_queue.put_nowait('Старе.')
        task = asyncio.create_task(voice.tts_worker())
        try:
            await asyncio.wait_for(started.wait(), 1)
            NewMessage.get_message()
            release.set()
            await asyncio.sleep(.01)
            self.assertTrue(voice.audio_queue.empty())
            NewMessage.add_text('Нове.')
            voice.tts_queue.put_nowait('Нове.')
            audio = await asyncio.wait_for(voice.audio_queue.get(), 1)
            self.assertEqual(audio['text'], 'Нове.')
            self.assertEqual(audio['generation'], NewMessage.generation)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            NewMessage.clear()
