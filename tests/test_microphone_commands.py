import asyncio
import unittest
from unittest.mock import patch

from audio.input import Microphone
from senko_protocol.enum import MicrophoneActions


class MicrophoneCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_on_off_switch_release_stream_and_clear_audio(self) -> None:
        Microphone.singleton = None
        microphone: Microphone = Microphone()
        started: int = 0
        stopped: int = 0

        async def record() -> None:
            nonlocal started, stopped
            started += 1

            try:
                await asyncio.Event().wait()
            finally:
                stopped += 1

        with patch.object(microphone, "create_stream", side_effect=record):
            try:
                await microphone.set_status(MicrophoneActions.ON)
                await asyncio.sleep(0)
                first_stream: asyncio.Task[None] | None = microphone.stream
                await microphone.set_status(MicrophoneActions.ON)
                self.assertIs(microphone.stream, first_stream)
                self.assertTrue(microphone.status)

                await microphone.set_status(MicrophoneActions.SWITCH)
                self.assertFalse(microphone.status)
                self.assertIsNone(microphone.stream)
                self.assertEqual(stopped, 1)

                await microphone.set_status(MicrophoneActions.SWITCH)
                await asyncio.sleep(0)
                self.assertTrue(microphone.status)
                self.assertEqual(started, 2)

                await microphone.set_status(MicrophoneActions.OFF)
                await microphone.set_status(MicrophoneActions.OFF)
                self.assertFalse(microphone.status)
                self.assertEqual(stopped, 2)
                self.assertEqual(microphone.sound_buffer, [])
            finally:
                await microphone.stop_streaming()
                Microphone.singleton = None
