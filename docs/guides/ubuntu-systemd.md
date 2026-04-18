# Ubuntu Systemd

Synapse now supports a repo-checkout Ubuntu deployment path through the CLI:

```bash
./synapse service install
./synapse service start
```

`synapse service install` is the server bootstrap path for a single combined
systemd service:

- creates or updates the repo `.venv`
- installs runtime dependencies with `pip install -e .`
- bootstraps `~/.synapse/.env` and `~/.synapse/config.yaml` if they are missing
- installs `/etc/systemd/system/synapse.service`
- runs `systemctl daemon-reload`
- runs `systemctl enable synapse.service`

The installed service runs:

```bash
.venv/bin/python -m synapse start --host 0.0.0.0 --port 8000
```

That means:

- the main Synapse API always starts
- the gateway host also starts automatically when `~/.synapse/config.yaml`
  enables gateways
- the service stays on the current combined backend-plus-optional-gateway shape

## Deployment Notes

- You can run `./synapse service install` either as a non-root deploy user or
  directly as `root`.
- When a non-root user runs the install, the CLI uses `sudo` only for writing
  the unit and calling `systemctl`.
- The installed systemd unit always runs as the user who ran
  `./synapse service install`, and it reads the shared runtime-plus-gateway
  config from that user’s home directory.
- This path is backend/gateway only. It does not install or serve the Vite
  frontend.
- If the Codex executor is enabled, set an absolute `runtime.codex_command` in
  `~/.synapse/config.yaml`.
- If a separately deployed browser UI uses voice mode against this server, add
  the frontend origin to `host.cors_allowed_origins` in `~/.synapse/config.yaml`
  so the gateway host can answer cross-origin `/gateway/...` requests.

Runtime config lives in:

```text
~/.synapse/.env
~/.synapse/config.yaml
```

If you install as `root`, that means:

```text
/root/.synapse/.env
/root/.synapse/config.yaml
```

## Health Checks

After starting the service:

```bash
curl -i http://127.0.0.1:8000/health
```

If gateway modules are enabled:

```bash
curl -i http://127.0.0.1:8010/health
```

## Logs And Control

Use the CLI wrappers:

```bash
./synapse service start
./synapse service stop
./synapse service restart
```

For logs and live service state:

```bash
sudo systemctl status synapse.service
sudo journalctl -u synapse.service -n 200
sudo journalctl -u synapse.service -f
```
