# Senko-san Desktop Assistant

A voice-driven desktop companion inspired by Senko-san, with Ukrainian speech
recognition, spoken replies, persistent conversation history, and background
coding tasks through Codex.

**Version 0.1.1 · Experimental · Linux · Python 3.14+**

## What it does

- Recognizes microphone audio with a local Faster Whisper model.
- Routes conversation and interruptions through Ollama.
- Generates replies with OpenAI and speech with Fish Audio.
- Stores conversation history in SQLite and loads optional startup memories.
- Runs terminal commands and monitors background Codex tasks.
- Connects the assistant and audio client over a local Unix socket.
- Controls the desktop microphone with `senko microphone on|off|switch`.

## Production deployment

For the root-owned `/opt/senko` installation, follow
[the production upgrade instructions](deployment/README.md). Core runs as
`Senka`, reads `/etc/senka/core.env` through systemd, and writes logs under
`/var/log/senka`. The desktop CLI runs as your regular user and needs no API keys.

## Requirements

This first release runs from a source checkout. It currently assumes a Linux
machine with an NVIDIA GPU, CUDA 12/cuDNN 9, working microphone/speaker devices,
and PortAudio and libsndfile system libraries.

You also need `uv`, Python 3.14 or newer, an Ollama service with `qwen3:14b`,
an authenticated Codex installation compatible with the pinned SDK, and OpenAI
and Fish Audio credentials. Whisper uses `large-v3` with CUDA/float16 and
`local_files_only=True`: download its model into the Hugging Face cache before
starting the assistant.

## Setup

From the repository root:

```bash
uv sync --locked --all-packages
cp .env.example .env
```

Fill in `.env` with your own credentials. Never commit that file.

The current runtime has fixed paths. Before starting, prepare these locations
for your own unprivileged account:

| Path | Purpose |
| --- | --- |
| `/run/senko/` | Writable socket directory; socket is `/run/senko/senko.sock` |
| `/home/Senka/memory/` | Writable directory for `history.db` |
| `/home/Senka/main_memories.md` | Optional long-term memory |
| `/home/Senka/notes_to_next_start.md` | Optional startup notes |
| `/home/Senka/skills/` | Copy of this checkout's `skills/` directory |

Provision these directories with appropriate ownership; `/run` is normally
recreated on boot. If those paths do not fit your machine, update
`protocol/src/senko_protocol/path.py`, `core/src/core/components/types.py`,
`senko_prompt.md`, and the skill instructions before running.
Do not run the assistant as root.

## Run

Start the assistant and audio client in separate terminals, from the repository
root:

```bash
uv run python -m pipeline.main
```

```bash
uv run python -m senko_client
```

Use `Ctrl+C` to stop each process. Keep the checkout in place: prompts and skills
are source files, and standalone wheel installation is not supported by this
release.

To install the CLI launcher for your source checkout, see
[the CLI instructions](client/README.md). `senko status` checks whether Core's
socket is reachable. Microphone commands require the updated desktop audio
client to be running and connected.

## Project layout

| Directory | Responsibility |
| --- | --- |
| `core/` | Assistant runtime, speech recognition, response generation, tools |
| `client/` | Microphone capture and audio playback |
| `protocol/` | Shared messages, framing, events, and shutdown helpers |
| `skills/` | Memory and task-management instructions and helpers |
| `tests/` | Offline behavior and integration tests |

## Privacy and permissions

Audio is transcribed locally. Conversation text and tool output can be sent to
OpenAI; reply text is sent to Fish Audio, and Codex uses its configured service.
Ollama handles the local conversation router.

The terminal tool executes commands with the assistant account's permissions.
Use an account with access only to files and services you intend it to control.
Prompt instructions are not an operating-system sandbox.

New history entries and Codex text logs mask some recognizable credential
formats. This is best-effort filtering: it does not sanitize every possible
secret, rewrite existing history/logs, or prevent data from reaching external
APIs. Review stored data before sharing it. Codex logs default to `logs/`;
`LOG_DIR` overrides that directory.

If a Codex event stream disconnects without confirmed completion, the task stays
reserved to prevent another task from editing the same directory concurrently.
Check the remote task's status and request cancellation as needed before
restarting the assistant.

## Development checks

```bash
uv run python -m unittest discover -s tests -v
uv lock --check
```

Tests mock remote services; a passing suite does not validate a live GPU,
microphone, paid API, or an authenticated Codex session.
