from .transport import Connector
from .connection import create_connector


class Server:
    def __init__(self):
        self.connection: Connector = create_connector()

    def start(self):
        self.connection.start()

    async def close(self):
        await self.connection.close()
