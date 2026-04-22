# Gateway Host

Synapse supports a separate, headless gateway host for vendor-facing gateway modules.

The standalone gateway host is now an optional deployment path. In the default
service-hosted runtime, the main Synapse service mounts enabled `/gateway/...`
routes directly and serves them on the same public origin as the rest of the
app.

The gateway host:

- runs as a separate process
- mounts first-party gateway modules from `src/synapse/gateways/`
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
./synapse gateway setup
```

Run the gateway host only:

```bash
./synapse gateway run
```

`./synapse dev` and `./synapse start` do not auto-start the standalone gateway
host anymore. Use `./synapse gateway run` only when you want a separate gateway
process.

Reload behavior:

- `./synapse dev` is the local iteration path and uses reload-capable processes
- `./synapse start` does not reload Python code changes

If you edit Python gateway code while using `./synapse start`, stop it and
start the main Synapse service again before retesting. If you are using
`./synapse gateway run` directly, restart that standalone process instead.

## Health and Debugging

Useful health endpoints:

```bash
curl -i http://127.0.0.1:8010/health
curl -i http://127.0.0.1:8010/gateway/agora-convoai/health
```

The responses include:

- enabled modules
- implementation version markers
- the effective `synapse_base_url`
- `upstream_transport_mode`

If the gateway cannot create Synapse sessions, first verify:

```bash
curl -i -X POST http://127.0.0.1:8000/sessions
```

from the same machine running the gateway host.

## Config

Gateway host config now uses the shared runtime-plus-gateway YAML file in the
user config home:

```text
~/.synapse/config.yaml
```

The YAML file contains:

- `runtime` for shared runtime settings such as `codex_command`
- `host` for gateway-host listener settings
- `gateways` for per-gateway module config

Scalar values written as `$VAR_NAME` are resolved from environment variables
after `~/.synapse/.env` is loaded.

The gateway host only consumes the `host` and `gateways` sections. The main
Synapse runtime also reads the shared `runtime` section.

For deployed browser voice-mode access, `host` may also include
`cors_allowed_origins`, which is the list of browser origins allowed to call
`/gateway/...` routes cross-origin.

`host.public_base_url` should be the public base URL where `/gateway/...` is
reachable:

- in the default service-hosted path, set it to the public main Synapse
  service origin
- in the standalone gateway-host path, set it to the public standalone gateway
  origin

The tracked template is:

```text
config/gateway.example.yaml
```

Current first-party gateway:

- `agora-convoai`
