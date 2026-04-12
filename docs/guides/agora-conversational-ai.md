# Agora Conversational AI

This guide documents the supported Synapse integration path for `examples/agora_conversational_ai`.

## Example Shape

This specific example uses one backend only:

- `examples/agora_conversational_ai/app.py`

That backend owns:

- Agora ConvoAI lifecycle via the Python SDK module `agora_agent`
- browser RTC/RTM token generation
- Synapse bridge binding
- the public custom-LLM callback URL used by Agora
- proactive notification speech through the local ConvoAI session

The example bridge runs separately from the main Synapse API server:

- Synapse server: `8000`
- Agora bridge: `8010`

It also exposes the browser-facing routes:

- `GET /frontend/config`
- `POST /frontend/session/prepare`
- `POST /frontend/session/activate`
- `POST /frontend/session/stop`
- `POST /chat/completions`

There is no separate sample-backend proxy in this example anymore.

## Behavior

- one live Agora agent binds to one Synapse session
- duplicate runtime-agent bindings are rejected
- the bridge translates the latest Agora custom-LLM turn into a Synapse session on the external Synapse server
- Synapse owns conversational replies behind the bridge callback
- this example backend owns Agora auth and calls Agora APIs on behalf of this example
- the browser prepares and subscribes RTC/RTM before agent activation, matching the official sample
- proactive notification delivery is triggered only for Synapse notification events
- normal chat replies are not replayed through `/speak`
- the example frontend talks only to this repo's example backend

## LLM Path

For this example, Agora does not call OpenAI directly.

Instead, `POST /frontend/session/activate` reserves a bridge session first, builds:

```text
${AGORA_BRIDGE_SERVICE_BASE_URL}/chat/completions?bridge_session_id=...
```

and passes that full URL into the Agora SDK as the OpenAI-compatible LLM endpoint.

When Agora calls that URL:

1. the bridge resolves `bridge_session_id`
2. the latest user turn is submitted into the bound external Synapse session on `8000`
3. Synapse generates the reply through its configured OpenAI-compatible backend
4. the bridge returns an OpenAI-compatible `chat.completions` response to Agora

`OPENAI_API_KEY` and optional `SYNAPSE_OPENAI_BASE_URL` therefore belong to the
separate Synapse server on `8000`, not the Agora bridge process on `8010`.

## Notification Delivery

The bridge subscribes to the Synapse session stream and watches for `conversation_appended` events with `source="notification"`.

When such an event arrives, the bridge calls the local ConvoAI service `say()` path for the started SDK session. This keeps Agora auth inside the example backend and out of the frontend while sourcing notification text from the external Synapse server.

## Identity Model

This example now mirrors the official sample's split identity model:

- RTC user uid: numeric uid
- RTM user uid: `<user_uid>-<channel>`
- agent RTC uid: configured agent uid
- agent RTM uid: `<agent_uid>-<channel>`

The frontend uses the agent RTM uid for toolkit messaging calls and the agent RTC uid for media/transcript identity.

## Run

Install Synapse in editable mode, then run:

```bash
pip install -e '.[dev]'
uvicorn synapse.api.app:app --reload --port 8000
uvicorn examples.agora_conversational_ai.app:app --reload --port 8010
```

The editable install should resolve the current SDK package `agora-agent-server-sdk`,
which exports the `agora_agent` module used by the example backend.

For the browser test client:

```bash
cd examples/agora_conversational_ai/frontend
npm install
npm run dev
```

The example reads its env from `examples/agora_conversational_ai/.env.local`. Configure App Credentials, provider keys, and `AGORA_BRIDGE_SYNAPSE_BASE_URL` there before starting live sessions.

For live Agora sessions, `AGORA_BRIDGE_SERVICE_BASE_URL` must be a public URL that can
reach this backend.

For this example, `AGORA_CONVOAI_AREA=CN` is the recommended starting value. If live start still fails with connectivity errors, try `US`, `EU`, or `AP`.

## Ownership Note

This “single backend” rule applies only to `examples/agora_conversational_ai`.

Future examples in this repo may still use separate backend topologies when that better fits the example design.
