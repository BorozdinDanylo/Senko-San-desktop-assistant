from dotenv import load_dotenv
load_dotenv()

from listener.whisper.microphone_recording import microphone
import pipeline
import asyncio


async def worker():
    pipeline.initialize()
    await pipeline.text_input.run()
    await pipeline.voice.run()

    await asyncio.gather(
        microphone(pipeline.audio_queue),
        pipeline.stt.worker(),
        pipeline.text_input.hear(),
        pipeline.senko.live(),
        pipeline.voice.tts_worker(),
        pipeline.voice.speak(),
    )


def main():
    asyncio.run(worker())


if __name__ == '__main__':
    main()

