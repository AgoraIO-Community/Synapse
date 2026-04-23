# Connector Host

Synapse supports a separate, headless connector host for vendor-facing connector modules.

The standalone connector host is now an optional deployment path. In the default
service-hosted runtime, the main Synapse service mounts enabled `/api/connectors/...`
routes directly and serves them on the same public origin as the rest of the
app.

The connector host:

- runs as a separate process
- mounts first-party connector modules from `src/synapse/connectors/`
- owns vendor callback endpoints
- talks back to the main Synapse service through public session APIs
- uses direct upstream connections to the configured Synapse service origin rather
  than environment-derived HTTP / HTTPS proxy settings

It does not:

- serve browser UI
- replace the main Synapse API
- change the Communication Brain / Execution Brain split

## CLI

Interactive setup:

```bash
./synapse setup
./synapse connector setup
```

Run the connector host only:

```bash
./synapse connector run
```

`./synapse dev` and `./synapse start` do not auto-start the standalone connector
host anymore. Use `./synapse connector run` only when you want a separate connector
process.

Reload behavior:

- `./synapse dev` is the local iteration path and uses reload-capable processes
- `./synapse start` does not reload Python code changes

If you edit Python connector code while using `./synapse start`, stop it and
start the main Synapse service again before retesting. If you are using
`./synapse connector run` directly, restart that standalone process instead.

## Health and Debugging

Useful health endpoints:

```bash
curl -i http://127.0.0.1:8010/api/health
curl -i http://127.0.0.1:8010/api/connectors/agora-convoai/health
```

The responses include:

- enabled modules
- implementation version markers
- the effective `synapse_base_url`
- `upstream_transport_mode`

If the connector cannot create Synapse sessions, first verify:

```bash
curl -i -X POST http://127.0.0.1:8000/api/sessions
```

from the same machine running the connector host.

## Config

Connector host config now uses the shared runtime-plus-connector YAML file in the
user config home:

```text
~/.synapse/config.yaml
```

The YAML file contains:

- `runtime` for shared runtime settings such as `codex_command`
- `connector_host` for connector-host listener settings
- `connectors` for per-connector module config

Scalar values written as `$VAR_NAME` are resolved from environment variables
after `~/.synapse/.env` is loaded.

The connector host only consumes the `connector_host` and `connectors` sections. The main
Synapse runtime also reads the shared `runtime` section.

For deployed browser voice-mode access, `connector_host` may also include
`cors_allowed_origins`, which is the list of browser origins allowed to call
`/api/connectors/...` routes cross-origin.

`connector_host.public_base_url` should be the public base URL where `/api/connectors/...` is
reachable:

- in the default service-hosted path, set it to the public main Synapse
  service origin
- in the standalone connector-host path, set it to the public standalone connector
  origin

Upgrade note:

- older standalone gateway/connector setups often pointed `public_base_url` at
  `http://127.0.0.1:8010`
- the tracked example now defaults it to `http://127.0.0.1:8000` because the
  unified-service path exposes `/api/connectors/...` from the main Synapse service

The tracked template is:

```text
config/connector.example.yaml
```

Current first-party connector:

- `agora-convoai`
