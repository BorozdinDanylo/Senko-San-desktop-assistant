import unittest
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner, Result
from senko_client.senko_cli import app
from senko_protocol.enum import DataType, MicrophoneActions, Version
from senko_protocol.model import Header, Response, ResponseBody


class SenkoCliTests(unittest.TestCase):
    def test_help_runs_without_core_credentials_from_another_directory(self) -> None:
        project: Path = Path(__file__).resolve().parents[1]
        environment: dict[str, str] = {
            key: value for key, value in os.environ.items()
            if key not in ('OPENAI_API_KEY', 'SENKO_SAN_API_KEY', 'SENKO_SAN_VOICE_ID', 'LOG_DIR')
        }
        environment['PYTHONPATH'] = os.pathsep.join(
            str(project / name) for name in ('client/src', 'protocol/src')
        )
        with tempfile.TemporaryDirectory() as directory:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                [sys.executable, '-B', '-m', 'senko_client.senko_cli', '--help'],
                cwd=directory, env=environment, capture_output=True, text=True, timeout=15,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('microphone', result.stdout)

    def test_status_checks_connection_and_releases_it(self) -> None:
        runner: CliRunner = CliRunner()
        with patch('senko_client.senko_cli.UnixSocket') as factory:
            factory.return_value.connect = AsyncMock()
            factory.return_value.wait_connected = AsyncMock()
            factory.return_value.disconnect = AsyncMock()
            result: Result = runner.invoke(app, ['status'])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('socket is reachable', result.output)
        factory.return_value.wait_connected.assert_awaited_once()
        factory.return_value.disconnect.assert_awaited_once()

    def test_status_reports_unavailable_core(self) -> None:
        runner: CliRunner = CliRunner()
        with patch('senko_client.senko_cli.UnixSocket') as factory:
            factory.return_value.connect = AsyncMock()
            factory.return_value.wait_connected = AsyncMock(side_effect=TimeoutError('offline'))
            factory.return_value.disconnect = AsyncMock()
            result: Result = runner.invoke(app, ['status'])

        self.assertEqual(result.exit_code, 1)
        self.assertIn('Cannot connect', result.output)
        factory.return_value.disconnect.assert_awaited_once()

    def test_microphone_actions_are_sent(self) -> None:
        runner: CliRunner = CliRunner()
        response: Response = Response(
            header=Header(version=Version.V2, type=DataType.RESPONSE, body_length=2),
            body=ResponseBody(status_code=200, message="Command forwarded"),
        )

        for action in MicrophoneActions:
            with self.subTest(action=action), patch(
                "senko_client.senko_cli.send_microphone_command",
                new_callable=AsyncMock,
                return_value=response,
            ) as send:
                result: Result = runner.invoke(app, ["microphone", action.name.lower()])
                self.assertEqual(result.exit_code, 0, result.output)
                send.assert_awaited_once_with(action)

    def test_unavailable_server_returns_error(self) -> None:
        runner: CliRunner = CliRunner()

        with patch(
            "senko_client.senko_cli.send_microphone_command",
            new_callable=AsyncMock,
            side_effect=TimeoutError("Server unavailable"),
        ):
            result: Result = runner.invoke(app, ["microphone", "off"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Cannot connect", result.output)
