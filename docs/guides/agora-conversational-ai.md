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

The browser demo remains outside the connector host under:

- `example-ui/`

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
- any browser demo is a client of the connector host and is not part of the connector boundary

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
- recreates a fresh frontend-owned session on every mode switch
- starts voice mode in an idle shell state first, then rebinds the whole shell
  to the voice session's returned `synapse_session_id` only after the user
  presses `Start`
- returns to a fresh normal `POST /api/sessions` session when switching back to
  text mode
- uses browser-local transcript/state from the Agora toolkit for the left-pane
  voice transcript feed while the workbench follows the bound Synapse session

## Run

Configure `~/.synapse/.env` and `~/.synapse/config.yaml`, then run:

```bash
./synapse setup
./synapse connector setup
./synapse start
```

For development with frontend + connector together:

```bash
./synapse dev
```

For the example browser test client:

```bash
cd example-ui
npm install
npm run dev
```

The connector host reads its live config from the shared `~/.synapse/config.yaml`
file and shared runtime env from `~/.synapse/.env`.

For live Agora sessions, `SYNAPSE_CONNECTOR_PUBLIC_BASE_URL` must be a public URL
that can reach the connector host.

For this example, Synapse fixes `connectors.agora-convoai.convoai_area` to `US`.

## Ownership Note

The browser demo under `example-ui/` is an example
client only. It is not part of the connector-host architecture boundary.
