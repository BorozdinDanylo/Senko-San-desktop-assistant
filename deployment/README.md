# Production upgrade to 0.1.1

Run the administrator steps from an existing root shell. The repository stays
owned by root; Core runs as `Senka`, and desktop commands run as `caban`.
Do not run the desktop audio client as root or give it Core API credentials.

## Administrator steps

A local release bundle avoids requiring GitHub credentials on the production
account. Replace `/tmp/senko-0.1.1.bundle` if the bundle was saved elsewhere.
Check the bundle's SHA-256 against the checksum supplied with the release before
using it. Start with a clean production checkout on `master`.

```bash
cd /opt/senko
git status --short
git bundle verify /tmp/senko-0.1.1.bundle
git fetch /tmp/senko-0.1.1.bundle refs/heads/master:refs/remotes/release/master refs/tags/v0.1.1:refs/tags/v0.1.1
systemctl stop senka-core.service
git merge --ff-only refs/remotes/release/master
uv sync --locked --all-packages
```

Migrate credentials without printing them. The helper preserves an existing
`/etc/senka/core.env`; otherwise it converts `/opt/senko/.env` into systemd
EnvironmentFile syntax. It archives the old `.env` outside the checkout with
root-only access. It fails on missing required credentials, unsupported values,
symlinks, or an existing archive rather than overwriting it.

```bash
/opt/senko/.venv/bin/python -B deployment/migrate_environment.py
cp --no-clobber /etc/systemd/system/senka-core.service /etc/senka/senka-core.service.pre-0.1.1
install -d -m 0755 /etc/systemd/system
install -m 0644 deployment/senka-core.service /etc/systemd/system/senka-core.service
systemctl daemon-reload
systemctl restart senka-core.service
systemctl is-active senka-core.service
stat -c '%A %U:%G %n' /run/senko /run/senko/senko.sock
```

The service prepares `/run/senko` on every start and uses `/var/log/senka` for
Codex logs. Keep `/home/Senka/memory` and the model cache in place. The migration
does not change their permissions or the socket's group access.

If a step fails, resolve it before continuing; do not assume the service is up.
Keep a protected backup of the previous unit before replacing it. To roll back
application code without discarding commits, stop Core, detach the checkout at
`v0.1.0`, run `uv sync --locked --all-packages`, and restart. The new service and
EnvironmentFile work with 0.1.0, but that version does not contain the CLI.

## Desktop user steps

As `caban`, after the production upgrade:

```bash
mkdir -p "$HOME/.local/bin"
ln -sfn /opt/senko/scripts/senko "$HOME/.local/bin/senko"
senko --help
senko status
```

`status` checks socket reachability, not microphone readiness or API health.
Start the updated desktop client in the user's audio session:

```bash
/opt/senko/.venv/bin/python -m senko_client
```

In another terminal, `senko microphone on`, `off`, or `switch` forwards commands
to that client. A 503 response means no updated audio client is registered.
A successful reply confirms forwarding, not hardware activation.
