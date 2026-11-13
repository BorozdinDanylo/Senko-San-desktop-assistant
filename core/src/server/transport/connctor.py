from senko_protocol.enum import Version, DataType
from abc import ABC, abstractmethod, abstractproperty
import uuid
import asyncio


class Connector(ABC):
    writer: asyncio.StreamWriter | None
    reader: asyncio.StreamReader | None

    @abstractproperty
    def reader(self) -> asyncio.StreamReader:
        pass

    @abstractproperty
    def writer(self) -> asyncio.StreamWriter:
        pass

    @abstractmethod
    async def handle_client(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        pass

    @abstractmethod
    async def response(self, response_message: str, request_id: uuid.UUID, version: Version = Version.V1):
        pass

    @abstractmethod
    async def send(self, body_message: bytes, dtype: DataType, version: Version = Version.V1):
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
