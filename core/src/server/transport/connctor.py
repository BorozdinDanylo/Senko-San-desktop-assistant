import asyncio
from abc import ABC, abstractmethod

from senko_protocol.enum import Version


class Connector(ABC):
    @abstractmethod
    async def handle_client(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        pass

    @staticmethod
    @abstractmethod
    async def response(response_message: str, writer: asyncio.StreamWriter, version: Version = Version.V1):
        pass

    @abstractmethod
    async def run(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    async def close(self):
        pass
