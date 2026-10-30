from senko_client.client import Client
from conection.unix_socket import test_listener
import asyncio


async def main():
    client = Client()
    await client.start()
    await test_listener()
    await client.stop()


def run():
    print("Starting client")
    asyncio.run(main())


if __name__ == '__main__':
    run()
