from senko_client.client import Client
import asyncio


async def main():
    client = Client()
    await client.start()

    try:
        await asyncio.Event().wait()
    finally:
        await client.stop()


def run():
    print("Starting client")
    asyncio.run(main())


if __name__ == '__main__':
    run()
