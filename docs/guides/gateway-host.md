# Gateway Host

Synapse supports a separate, headless gateway host for vendor-facing gateway modules.

The gateway host:

- runs as a separate process
- mounts first-party gateway modules from `src/synapse/gateways/`
- owns vendor callback endpoints
- talks back to the main Synapse API through public session APIs
- uses direct upstream connections to the configured Synapse backend rather
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

When gateway config is enabled in `~/.synapse/config.yaml`, these commands also start the
gateway host automatically:

```bash
./synapse dev
./synapse start
```

Reload behavior:

- `./synapse dev` is the local iteration path and uses reload-capable processes
- `./synapse start` does not reload Python code changes

If you edit Python gateway code while using `./synapse start`, stop it and
start it again before retesting.

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

The tracked template is:

```text
config/gateway.example.yaml
```

Current first-party gateway:

- `agora-convoai`
