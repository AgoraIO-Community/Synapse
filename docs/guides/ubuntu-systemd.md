# Ubuntu Systemd

Synapse now supports a repo-checkout Ubuntu deployment path through the CLI:

```bash
./newbro service install
```

`newbro service install` is the server bootstrap path for a single combined
systemd service:

- creates or updates the repo `.venv`
- installs runtime dependencies with `pip install -e .`
- bootstraps `~/.newbro/.env` and `~/.newbro/config.yaml` if they are missing
- installs `/etc/systemd/system/newbro.service`
- runs `systemctl daemon-reload`
- runs `systemctl enable newbro.service`
- runs `systemctl restart newbro.service`

The installed service runs:

```bash
.venv/bin/newbro start --host 0.0.0.0 --port 8000
```

That means:

- one main Synapse service listens on the public port and becomes the single
  browser-facing origin
- the production frontend build is served from the same origin at `/`
- the normal API and websocket routes live on that same service origin
- enabled `/api/connectors/...` routes are mounted directly into the main service
- the standalone connector host no longer auto-starts from `newbro start`

## Deployment Notes

- You can run `./newbro service install` either as a non-root deploy user or
  directly as `root`.
- When a non-root user runs the install, the CLI uses `sudo` only for writing
  the unit and calling `systemctl`.
- The installed systemd unit always runs as the user who ran
  `./newbro service install`, and it reads the shared runtime-plus-connector
  config from that user’s home directory.
- This path builds the production frontend during `newbro service install` and
  serves the built UI directly from the main Synapse service.
- `newbro service install` now starts or restarts the service automatically, so
  use it as the normal “deploy the current checkout” command.
- If the Codex executor is enabled, set an absolute `runtime.codex_command` in
  `~/.newbro/config.yaml`.
- Same-origin voice mode now works through the main service `/api/connectors/...`
  routes when connectors are enabled, so a separate `VITE_CONNECTOR_BASE_URL` is
  not required for this service-hosted UI path.
- If Agora or another external caller must reach
  `/api/connectors/agora-convoai/chat/completions`, set `connector_host.public_base_url` in
  `~/.newbro/config.yaml` to the public Synapse service origin.

Runtime config lives in:

```text
~/.newbro/.env
~/.newbro/config.yaml
```

If you install as `root`, that means:

```text
/root/.newbro/.env
/root/.newbro/config.yaml
```

## Health Checks

After `newbro service install` or any later start/restart:

```bash
curl -i http://127.0.0.1:8000/api/health
```

Verify the served UI shell:

```bash
curl -i http://127.0.0.1:8000/
```

If connector modules are enabled:

```bash
curl -i http://127.0.0.1:8000/api/connectors/agora-convoai/config
```

## Logs And Control

Use the CLI wrappers:

```bash
./newbro service start
./newbro service stop
./newbro service restart
```

For logs and live service state:

```bash
sudo systemctl status newbro.service
sudo journalctl -u newbro.service -n 200
sudo journalctl -u newbro.service -f
```
