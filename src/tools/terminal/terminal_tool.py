from tools import tool, Tool
import pexpect
import pyte
import asyncio
import os


class TerminalTool(Tool):
    def __init__(self):
        super().__init__()

        self.rows = 30
        self.cols = 120

        env = os.environ.copy()
        sudo_password = env.pop("SUDO_PASSWORD")

        self.process = pexpect.spawn(
             "/usr/bin/sudo",
            ["-u", "Senka", "-H", "/bin/bash"],
            encoding="utf-8",
            echo=False,
        )

        self.process.setwinsize(
            self.rows,
            self.cols,
        )

        self.screen_buffer = pyte.Screen(self.rows, self.cols)
        self.stream = pyte.Stream(self.screen_buffer)

        self.process.expect(r"\[sudo\] password for .*:")
        self.process.sendline(sudo_password)

        self.prompt = "__SENKO_PROMPT__"

        self.process.sendline(
            f"export PS1='{self.prompt} '"
        )

        self.process.expect(self.prompt)

    @tool
    async def command(self, command: str) -> str:
        """
        Execute a normal non-interactive shell command and wait until it finishes.

        Do NOT use this for interactive programs such as vim, nano, tmux,
        top, less, Python REPL, or other programs that take control of the terminal.
        Use write() and key() for interactive programs instead.
        """

        return await asyncio.to_thread(
            self._command,
            command,
        )

    def _command(self, command: str) -> str:
        self.process.sendline(command)
        self.process.expect(self.prompt)
        output = self.process.before

        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        elif not output:
            output = ""

        return output.strip()

    @tool
    async def read(self) -> str:
        """
        Read currently available terminal output without waiting for a command to finish.
        """
        return await asyncio.to_thread(self._read)

    def _read(self) -> str:
        output = ""
        while True:
            try:
                data = self.process.read_nonblocking(
                    4096,
                    .5
                )

                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")

                output += data
            except (pexpect.TIMEOUT, pexpect.EOF):
                break

        self.stream.feed(output)

        return "\n".join(self.screen_buffer.display)

    @tool
    async def write(self, command: str) -> str:
        """
        Write text directly into the current terminal session.

        Use this for interactive applications such as vim, nano, tmux,
        Python REPL, and similar terminal programs.
        """

        return await asyncio.to_thread(
            self._write,
            command,
        )

    def _write(self, command: str) -> str:
        self.process.send(command)

        return self._read()


if __name__ == '__main__':
    from dotenv import load_dotenv
    import asyncio
    load_dotenv()

    test_tool = TerminalTool()
    print(asyncio.run(test_tool.tools["command"]("ls -lh")))
