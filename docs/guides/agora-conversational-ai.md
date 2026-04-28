# Agora Conversational AI

This guide documents the supported Synapse integration path for the first-party
`agora-convoai` connector module.

## Example Shape

The supported backend path is now the headless connector host plus the first-party
Agora connector module under:

- `src/synapse/connectors/host/`
- `src/synapse/connectors/voice/agora_convoai/`

That connector module owns:

- Agora ConvoAI lifecycle via the Python SDK module `agora_agent`
- Synapse connector binding
- the public custom-LLM callback URL used by Agora
- proactive notification speech through the local ConvoAI session

The active browser UI lives under:

- `src/synapse/ui/`

The connector host runs separately from the main Synapse API server:

- Synapse server: `8000`
- Connector host: `8010`

The `agora-convoai` module exposes headless routes:

- `GET /api/connectors/agora-convoai/config`
- `POST /api/connectors/agora-convoai/sessions/prepare`
- `POST /api/connectors/agora-convoai/sessions/activate`
- `POST /api/connectors/agora-convoai/sessions/stop`
- `POST /api/connectors/agora-convoai/chat/completions`

## Behavior

- one live Agora agent binds to one Synapse session
- duplicate runtime-agent bindings are rejected
- the bridge translates the latest Agora custom-LLM turn into a Synapse session on the external Synapse server
- Synapse owns conversational replies behind the bridge callback
- the connector module owns Agora auth and calls Agora APIs on behalf of the integration
- proactive notification delivery is triggered only for Synapse notification events
- normal chat replies are not replayed through `/speak`
- the browser UI is a client of the connector host and is not part of the connector boundary

## LLM Path

For this module, Agora does not call OpenAI directly.

Instead, `POST /api/connectors/agora-convoai/sessions/activate` reserves a connector
binding first and builds:

```text
${SYNAPSE_CONNECTOR_PUBLIC_BASE_URL}/api/connectors/agora-convoai/chat/completions?binding_id=...
```

and passes that full URL into the Agora SDK as the OpenAI-compatible LLM endpoint.

When Agora calls that URL:

1. the connector resolves `binding_id`
2. the latest user turn is submitted into the bound external Synapse session on `8000`
3. Synapse generates the reply through its configured OpenAI-compatible backend
4. the connector returns an OpenAI-compatible `chat.completions` response to Agora

`OPENAI_API_KEY` and optional `SYNAPSE_OPENAI_BASE_URL` therefore belong to the
separate Synapse server on `8000`, not the connector host on `8010`.

## Notification Delivery

The connector watches the Synapse session stream and forwards only notification-origin
text to the live Agora session.

When such an event arrives, the connector calls the local ConvoAI service `say()`
path for the started SDK session. This keeps Agora auth inside the connector host
while sourcing notification text from the external Synapse server.

## Identity Model

This example now mirrors the official sample's split identity model:

- RTC user uid: numeric uid
- RTM user uid: `<user_uid>-<channel>`
- agent RTC uid: configured agent uid
- agent RTM uid: `<agent_uid>-<channel>`

The frontend uses the agent RTM uid for toolkit messaging calls and the agent RTC uid for media/transcript identity.

The main workbench under `src/synapse/ui/` now supports an explicit `Text` /
`Voice` mode switch. That UI path:

- calls the connector host through `/api/connectors/agora-convoai/*` when entering voice
  mode
- keeps the shell on its existing `POST /api/sessions` session before, during,
  and after voice mode
- sends that current `synapse_session_id` into connector session prepare so the
  voice binding attaches to the existing Synapse session
- defaults the Agora `channel_name` to that `synapse_session_id` when the
  browser does not provide an explicit channel override
- tears down only the live voice transport and connector binding on `Stop`
  without swapping the shell to a different Synapse session
- uses Synapse conversation history plus Synapse user/assistant stream events
  for the left-pane interaction memory while the Agora toolkit remains
  responsible for browser-local RTC/RTM/session behavior

## Run

Configure `~/.newbro/.env` and `~/.newbro/config.yaml`, then run:

```bash
./newbro setup
./newbro connector setup
./newbro start
```

For development with frontend + connector together:

```bash
./newbro dev
```

For frontend development, use the active shell under `src/synapse/ui/` through `./newbro dev`.

The connector host reads its live config from the shared `~/.newbro/config.yaml`
file and shared runtime env from `~/.newbro/.env`.

For live Agora sessions, `SYNAPSE_CONNECTOR_PUBLIC_BASE_URL` must be a public URL
that can reach the connector host.

For this example, Synapse fixes `connectors.agora-convoai.convoai_area` to `US`.

## Ownership Note

The active browser UI under `src/synapse/ui/` is the supported frontend. It is a
client of the connector host and is not part of the connector-host architecture
boundary.
