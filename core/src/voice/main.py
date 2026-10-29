from fishaudio import AsyncFishAudio
from fishaudio.types import ReferenceAudio
from fishaudio.utils import play
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

SENKO_SAN_API_KEY = os.environ["SENKO_SAN_API_KEY"]
SENKO_SAN_VOICE_ID = os.environ["SENKO_SAN_VOICE_ID"]



async def main():
    client = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)

    audio = await client.tts.convert(
        text=(
            "Доброго ранку! Як твої справи? "
            "Я вже приготувала сніданок, тож давай потроху прокидайся."
        ),
        reference_id=SENKO_SAN_VOICE_ID,
        model="s2.1-pro-free",  # type: ignore[arg-type]
        format="mp3",
    )

    play(audio)


if __name__ == '__main__':
    asyncio.run(main())

