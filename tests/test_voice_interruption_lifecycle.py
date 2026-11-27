import asyncio
import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch

from core.components import Queues
from senko import NewMessage


class VoiceInterruptionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fish = types.ModuleType('fishaudio')
        client = types.ModuleType('fishaudio.client')
        client.AsyncFishAudio = object
        with patch.dict(sys.modules, {'fishaudio': fish, 'fishaudio.client': client}), patch.dict(os.environ, {'SENKO_SAN_API_KEY': 'test', 'SENKO_SAN_VOICE_ID': 'test'}):
            module = importlib.import_module('voice.model.senko')
        self.voice = module.SenkoVoice.__new__(module.SenkoVoice)
        self.voice.audio_queue = asyncio.Queue()
        self.queue = asyncio.Queue()
        self.queue_patch = patch.object(Queues, 'tts_queue', self.queue)
        self.queue_patch.start()
        NewMessage.clear()
        self.started = asyncio.Queue()
        self.releases = asyncio.Queue()

        async def convert(**kwargs):
            release = asyncio.Event()
            await self.releases.put(release)
            await self.started.put(kwargs['text'])
            await release.wait()
            return kwargs['text'].encode()

        self.voice.client = types.SimpleNamespace(tts=types.SimpleNamespace(convert=convert))
        self.worker = asyncio.create_task(self.voice.tts_worker())

    async def asyncTearDown(self):
        self.worker.cancel()
        await asyncio.gather(self.worker, return_exceptions=True)
        self.queue_patch.stop()
        NewMessage.clear()

    async def start_conversion(self, text):
        NewMessage.add_text(text)
        await self.queue.put(text)
        self.assertEqual(await asyncio.wait_for(self.started.get(), 1), text)
        return await self.releases.get()

    async def test_stop_during_conversion_clears_queues_and_allows_new_speech(self):
        release = await self.start_conversion('Старе.')
        await self.queue.put('Черга.')
        await self.voice.audio_queue.put({'text': 'Черга.', 'audio': b'old', 'generation': NewMessage.generation})
        await self.voice.stop_talking()
        self.assertTrue(self.queue.empty())
        self.assertTrue(self.voice.audio_queue.empty())
        release.set()
        new_release = await self.start_conversion('Нове.')
        self.assertTrue(self.voice.audio_queue.empty())
        new_release.set()
        audio = await asyncio.wait_for(self.voice.audio_queue.get(), 1)
        self.assertEqual(audio['audio'], 'Нове.'.encode())
        self.assertEqual(audio['generation'], NewMessage.generation)

    async def test_rapid_interruptions_invalidate_each_conversion(self):
        first = await self.start_conversion('Перше.')
        await self.voice.stop_talking()
        first.set()
        second = await self.start_conversion('Друге.')
        await self.voice.stop_talking()
        await self.voice.stop_talking()
        second.set()
        third = await self.start_conversion('Третє.')
        self.assertTrue(self.voice.audio_queue.empty())
        third.set()
        self.assertEqual((await asyncio.wait_for(self.voice.audio_queue.get(), 1))['text'], 'Третє.')

    async def test_text_completion_does_not_invalidate_conversion(self):
        release = await self.start_conversion('Відповідь.')
        generation = NewMessage.generation
        NewMessage.get_message()
        self.assertEqual(NewMessage.generation, generation)
        release.set()
        audio = await asyncio.wait_for(self.voice.audio_queue.get(), 1)
        self.assertEqual(audio['text'], 'Відповідь.')
        self.assertEqual(audio['generation'], generation)
