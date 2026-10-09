from tools.types.tool import Tool
from pydantic import Field
from typing import Annotated, Literal
import pexpect
import pyte
import os

from dotenv import load_dotenv
load_dotenv()


@Tool.initialize_class
class TerminalTool(Tool):
    rows: int
    cols: int
    process: pexpect.pty_spawn.spawn
    screen_buffer: pyte.Screen
    stream: pyte.Stream
    prompt: Literal["__SENKO_PROMPT__"] = "__SENKO_PROMPT__"

    @classmethod
    def initialize(cls):
        cls.rows = 30
        cls.cols = 120

        env = os.environ.copy()
        sudo_password = env.pop("SUDO_PASSWORD")

        cls.process = pexpect.spawn(
            "/usr/bin/sudo",
            ["-u", "Senka", "-H", "/bin/bash"],
            encoding="utf-8",
            echo=False,
        )

        cls.process.setwinsize(
            cls.rows,
            cls.cols,
        )

        cls.screen_buffer = pyte.Screen(cls.rows, cls.cols)
        cls.stream = pyte.Stream(cls.screen_buffer)

        cls.process.expect(r"\[sudo\] password for .*:")
        cls.process.sendline(sudo_password)

        cls.prompt = "__SENKO_PROMPT__"

        cls.process.sendline(
            f"export PS1='{cls.prompt} '"
        )

        cls.process.expect(cls.prompt)

    @classmethod
    @Tool.tool
    async def command(
            cls,
            command: Annotated[
                str,
                Field(description="Command to execute."),
            ]
    ) -> str:
        """
        Execute a normal non-interactive shell command and wait until it finishes.

        Do NOT use this for interactive programs such as vim, nano, tmux,
        top, less, Python REPL, or other programs that take control of the terminal.
        Use write() and key() for interactive programs instead.
        """

        return await asyncio.to_thread(
            cls._command,
            command,
        )

    @classmethod
    def _command(cls, command: str) -> str:
        cls.process.sendline(command)
        cls.process.expect(cls.prompt)
        output = cls.process.before

        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        elif not output:
            output = ""

        return output.strip()

    @classmethod
    @Tool.tool
    async def read(cls) -> str:
        """
        Read currently available terminal output without waiting for a command to finish.
        """
        return await asyncio.to_thread(cls._read)

    @classmethod
    def _read(cls) -> str:
        output = ""
        while True:
            try:
                data = cls.process.read_nonblocking(
                    4096,
                    .5
                )

                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")

                output += data
            except (pexpect.TIMEOUT, pexpect.EOF):
                break

        cls.stream.feed(output)

        return "\n".join(cls.screen_buffer.display)

    @classmethod
    @Tool.tool
    async def write(
            cls,
            text: Annotated[
                str,
                Field(description="Text to write to the terminal"),
            ]
    ) -> str:
        """
        Write text directly into the current terminal session.

        Use this for interactive applications such as vim, nano, tmux,
        Python REPL, and similar terminal programs.
        """

        return await asyncio.to_thread(
            cls._write,
            text,
        )

    @classmethod
    def _write(cls, command: str) -> str:
        cls.process.send(command)

        return cls._read()


if __name__ == '__main__':
    import asyncio

    print(Tool.tools_shamas)
    print(Tool.tools)

