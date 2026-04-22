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
.venv/bin/python -m synapse start --host 0.0.0.0 --port 8000 --backend-port 8001
```

That means:

- the in-repo `synapse.edge` transport listens on the public port and becomes
  the single browser-facing origin
- the main Synapse API starts on an internal port behind `synapse.edge`
- the production frontend build is served from the same origin at `/`
- the gateway host also starts automatically when `~/.synapse/config.yaml`
  enables gateways
- same-origin `/gateway/...` browser requests are routed by `synapse.edge` to
  the gateway host when gateways are enabled
- same-origin session-stream websocket requests are routed by `synapse.edge` to
  the internal backend

## Deployment Notes

- You can run `./synapse service install` either as a non-root deploy user or
  directly as `root`.
- When a non-root user runs the install, the CLI uses `sudo` only for writing
  the unit and calling `systemctl`.
- The installed systemd unit always runs as the user who ran
  `./synapse service install`, and it reads the shared runtime-plus-gateway
  config from that user’s home directory.
- This path builds the production frontend during `synapse service install` and
  serves the built UI through the in-repo `synapse.edge` transport layer rather
  than through the FastAPI app directly.
- If the Codex executor is enabled, set an absolute `runtime.codex_command` in
  `~/.synapse/config.yaml`.
- Same-origin voice mode now works through the `synapse.edge` `/gateway/...`
  route when
  the gateway host is enabled, so a separate `VITE_GATEWAY_BASE_URL` is not
  required for this service-hosted UI path.
- If Agora or another external caller must reach
  `/gateway/agora-convoai/chat/completions`, set `host.public_base_url` in
  `~/.synapse/config.yaml` to the public edge origin instead of the internal
  gateway listener address.

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

Verify the served UI shell:

```bash
curl -i http://127.0.0.1:8000/
```

Verify the internal backend directly when needed:

```bash
curl -i http://127.0.0.1:8001/health
```

If gateway modules are enabled:

```bash
curl -i http://127.0.0.1:8010/health
curl -i http://127.0.0.1:8000/gateway/agora-convoai/config
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
