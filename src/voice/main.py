from fishaudio import AsyncFishAudio
from fishaudio.utils import play
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

SENKO_SAN_API_KEY = os.environ["SENKO_SAN_API_KEY"]



async def main():
    client = AsyncFishAudio(api_key=SENKO_SAN_API_KEY)

    audio = await client.tts.convert(
        text="Привіт! Я розмовляю українською.",
        model="s2.1-pro-free",  # type: ignore[arg-type]
    )

    play(audio)


if __name__ == '__main__':
    asyncio.run(main())

