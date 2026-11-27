import asyncio
import struct

from conection.unix_socket import UnixSocket
from senko_protocol.enum import DataType
from senko_protocol.model import Response
from senko_protocol.enum import Commands, MicrophoneActions
from enum import Enum
import typer


app: typer.Typer = typer.Typer(
    name="senko",
    help="Senko-San desktop assistant CLI",
    no_args_is_help=True,
)

microphone_app: typer.Typer = typer.Typer(help="Control microphone")

app.add_typer(microphone_app, name="microphone")


class MicrophoneState(str, Enum):
    ON = "on"
    OFF = "off"
    SWITCH = "switch"


async def send_microphone_command(action: MicrophoneActions) -> Response:
    connection: UnixSocket = UnixSocket()
    body: bytes = struct.pack("!BB", Commands.MICROPHONE, action)

    try:
        await connection.connect()
        await connection.wait_connected()
        return await connection.fetch(body, DataType.COMMAND)
    finally:
        await connection.disconnect()


@microphone_app.callback(invoke_without_command=True)
def microphone(
    ctx: typer.Context,
    state: MicrophoneState | None = typer.Argument(None),
) -> None:
    if state is None:
        if ctx.invoked_subcommand is None:
            typer.echo("Use: senko microphone [on|off|switch]")
        return

    try:
        response: Response = asyncio.run(send_microphone_command(MicrophoneActions[state.name]))
    except (OSError, RuntimeError, TimeoutError) as error:
        typer.echo(f"Cannot connect to Senko server: {error}", err=True)
        raise typer.Exit(code=1) from error

    if response.body.status_code != 200:
        typer.echo(response.body.message, err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Microphone command sent: {state.value}")


@app.command()
def status() -> None:
    """Check whether the Core socket accepts connections."""
    async def probe() -> None:
        connection: UnixSocket = UnixSocket()
        try:
            await connection.connect()
            await connection.wait_connected()
        finally:
            await connection.disconnect()

    try:
        asyncio.run(probe())
    except (OSError, RuntimeError, TimeoutError) as error:
        typer.echo(f"Cannot connect to Senko server: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo("Senko Core socket is reachable")


if __name__ == "__main__":
    app()
