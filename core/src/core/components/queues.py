from senko_protocol.typing import AudioArray
import asyncio


class Queues:
    audio_queue: asyncio.Queue[AudioArray] = asyncio.Queue[AudioArray]()
    transcription_queue: asyncio.Queue[str] = asyncio.Queue[str]()
    text_queue: asyncio.Queue[str] = asyncio.Queue[str]()
    text_analiz: asyncio.Queue[str] = asyncio.Queue[str]()
    tts_queue: asyncio.Queue[str] = asyncio.Queue[str]()


