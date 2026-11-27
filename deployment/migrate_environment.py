"""Move checkout credentials to a root-only systemd EnvironmentFile."""

import os
from pathlib import Path
import re

from dotenv import dotenv_values


REQUIRED_KEYS: tuple[str, ...] = (
    "OPENAI_API_KEY", "SENKO_SAN_API_KEY", "SENKO_SAN_VOICE_ID",
)


def environment_text(source: Path) -> str:
    values: dict[str, str | None] = dict(dotenv_values(source, interpolate=False))
    if any(not values.get(key) for key in REQUIRED_KEYS):
        raise ValueError("Required Core credentials are missing; values were not printed")

    lines: list[str] = []
    for key, value in values.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or value is None:
            raise ValueError("Unsupported environment entry; values were not printed")
        if any(character in value for character in ("\n", "\r", "\0")) or "${" in value:
            raise ValueError("Multiline values and variable interpolation require manual migration")
        escaped: str = value.replace("\\", "\\\\").replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
        lines.append(f'{key}="{escaped}"\n')

    return "".join(lines)


def migrate_environment(source: Path, destination: Path, archive: Path) -> None:
    for path in (source, destination, archive, destination.parent, archive.parent):
        if path.is_symlink():
            raise ValueError("Refusing a symlink in the credential migration paths")
    for path in (source, destination, archive):
        if path.exists() and not path.is_file():
            raise ValueError("Credential paths must be regular files")
    if source.exists() and archive.exists():
        raise FileExistsError("Credential archive already exists; nothing was replaced")
    if not destination.exists() and not source.is_file():
        raise FileNotFoundError("No existing Core EnvironmentFile or checkout .env")

    # Validate before creating directories or changing any credential file.
    content: str = environment_text(destination if destination.exists() else source)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.parent.chmod(0o700)
    if not destination.exists():
        descriptor: int = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    destination.chmod(0o600)

    if source.exists():
        source.chmod(0o600)
        source.rename(archive)
        archive.chmod(0o600)


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("Run from an administrator root shell; no credentials were read")
    try:
        migrate_environment(
            Path("/opt/senko/.env"), Path("/etc/senka/core.env"), Path("/etc/senka/legacy.env"),
        )
        os.chown("/etc/senka", 0, 0)
        os.chown("/etc/senka/core.env", 0, 0)
        if Path("/etc/senka/legacy.env").exists():
            os.chown("/etc/senka/legacy.env", 0, 0)
    except (OSError, ValueError):
        raise SystemExit("Credential migration failed; no values were printed. Inspect paths and format privately.") from None
    print("Core credentials prepared; no values were printed")


if __name__ == "__main__":
    main()
