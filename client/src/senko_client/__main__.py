from senko_client.client import Client
from senko_protocol.lifecycle import run_until_stopped
import asyncio


async def main() -> None:
    client: Client = Client()

    try:
        await client.start()
        await asyncio.Event().wait()

    finally:
        await client.stop()


def run() -> None:
    print("Starting client")
    asyncio.run(run_until_stopped(main))


if __name__ == '__main__':
    run()
