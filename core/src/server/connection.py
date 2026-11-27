from .transport import Connector, UnixSocket


def create_connector() -> Connector:
    """In future must be realized connection for all Connectors"""

    return UnixSocket()


