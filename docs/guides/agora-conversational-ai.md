# Agora Conversational AI

This guide documents the supported Synapse integration path for the first-party
`agora-convoai` gateway module.

## Example Shape

The supported backend path is now the headless gateway host plus the first-party
Agora gateway module under:

- `src/synapse/gateway_host/`
- `src/synapse/gateways/agora_convoai/`

That gateway module owns:

- Agora ConvoAI lifecycle via the Python SDK module `agora_agent`
- Synapse gateway binding
- the public custom-LLM callback URL used by Agora
- proactive notification speech through the local ConvoAI session

The browser demo remains outside the gateway host under:

- `exmaple-ui/`

The gateway host runs separately from the main Synapse API server:

- Synapse server: `8000`
- Gateway host: `8010`

The `agora-convoai` module exposes headless routes:

- `GET /gateway/agora-convoai/config`
- `POST /gateway/agora-convoai/sessions/prepare`
- `POST /gateway/agora-convoai/sessions/activate`
- `POST /gateway/agora-convoai/sessions/stop`
- `POST /gateway/agora-convoai/chat/completions`

## Behavior

- one live Agora agent binds to one Synapse session
- duplicate runtime-agent bindings are rejected
- the bridge translates the latest Agora custom-LLM turn into a Synapse session on the external Synapse server
- Synapse owns conversational replies behind the bridge callback
- the gateway module owns Agora auth and calls Agora APIs on behalf of the integration
- proactive notification delivery is triggered only for Synapse notification events
- normal chat replies are not replayed through `/speak`
- any browser demo is a client of the gateway host and is not part of the gateway boundary

## LLM Path

For this module, Agora does not call OpenAI directly.

Instead, `POST /gateway/agora-convoai/sessions/activate` reserves a gateway
binding first and builds:

```text
${SYNAPSE_GATEWAY_PUBLIC_BASE_URL}/gateway/agora-convoai/chat/completions?binding_id=...
```

and passes that full URL into the Agora SDK as the OpenAI-compatible LLM endpoint.

When Agora calls that URL:

1. the gateway resolves `binding_id`
2. the latest user turn is submitted into the bound external Synapse session on `8000`
3. Synapse generates the reply through its configured OpenAI-compatible backend
4. the gateway returns an OpenAI-compatible `chat.completions` response to Agora

`OPENAI_API_KEY` and optional `SYNAPSE_OPENAI_BASE_URL` therefore belong to the
separate Synapse server on `8000`, not the gateway host on `8010`.

## Notification Delivery

The gateway watches the Synapse session stream and forwards only notification-origin
text to the live Agora session.

When such an event arrives, the gateway calls the local ConvoAI service `say()`
path for the started SDK session. This keeps Agora auth inside the gateway host
while sourcing notification text from the external Synapse server.

## Identity Model

This example now mirrors the official sample's split identity model:

- RTC user uid: numeric uid
- RTM user uid: `<user_uid>-<channel>`
- agent RTC uid: configured agent uid
- agent RTM uid: `<agent_uid>-<channel>`

The frontend uses the agent RTM uid for toolkit messaging calls and the agent RTC uid for media/transcript identity.

## Run

Configure `~/.synapse/.env` and `~/.synapse/config.yaml`, then run:

```bash
./synapse setup
./synapse gateway setup
./synapse start
```

For development with frontend + gateway together:

```bash
./synapse dev
```

For the example browser test client:

```bash
cd exmaple-ui
npm install
npm run dev
```

The gateway host reads its live config from `~/.synapse/config.yaml` and the shared
runtime env from `~/.synapse/.env`.

For live Agora sessions, `SYNAPSE_GATEWAY_PUBLIC_BASE_URL` must be a public URL
that can reach the gateway host.

For this example, Synapse fixes `gateways.agora-convoai.convoai_area` to `US`.

## Ownership Note

The browser demo under `exmaple-ui/` is an example
client only. It is not part of the gateway-host architecture boundary.
