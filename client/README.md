# Senko CLI

To use this checkout's CLI from any directory on Linux, prepare the project
environment and add the launcher to your user command directory:

```bash
uv sync --all-packages
mkdir -p "$HOME/.local/bin"
ln -sfn "$(pwd)/scripts/senko" "$HOME/.local/bin/senko"
```

Run these installation commands from the repository root. Ensure
`$HOME/.local/bin` is on your `PATH`; if needed, add
`export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc` and open a new terminal.
The launcher uses this checkout's `.venv` without requiring activation.
Keep the checkout in place; recreate the symlink if you move it.

From any directory:

```bash
senko --help
senko status
senko microphone on
senko microphone off
senko microphone switch
```

Microphone commands require a running Senko server and connected audio client.
A successful response confirms command forwarding. The `status` command checks
socket reachability; it does not validate API credentials or microphone hardware.

For production, install the launcher from `/opt/senko/scripts/senko` after the
upgrade described in [the deployment guide](../deployment/README.md). The CLI
uses the production virtual environment and needs no Core environment file or
API keys. The desktop user needs write access to `/run/senko/senko.sock`, normally
through membership in the `senka` group. Core and the audio client must both use
the updated command protocol.
