# Agora Conversational AI Example

This example is now primarily a browser demo client for the first-party
`agora-convoai` gateway module.

The reusable gateway backend logic lives under:

```text
src/synapse/gateways/agora_convoai/
```

The legacy example backend remains available for compatibility and local
experimentation, but it is no longer the preferred integration path.

It does three jobs:

- starts and stops Agora ConvoAI sessions directly through the Python SDK module `agora_agent`
- exposes a public OpenAI-compatible `/chat/completions` edge for Agora custom-LLM callbacks
- serves as the backend for the local React voice test client

This backend is now a bridge in front of a separate Synapse server. Run Synapse itself on
port `8000`, and run this Agora bridge on port `8010`.

## Flow

1. Start the normal Synapse server on `8000`.
2. Configure this example backend with Agora App Credentials plus the provider keys it needs.
3. Start the example backend on `8010`.
4. Start the example-local voice frontend.
5. The frontend calls `POST /gateway/agora-convoai/sessions/prepare`.
6. The browser initializes RTC and RTM, subscribes to the channel, and then calls `POST /gateway/agora-convoai/sessions/activate`.
7. The gateway host creates a Synapse session on `8000`, reserves a `binding_id`, starts the ConvoAI agent locally with that public `/gateway/agora-convoai/chat/completions` URL as its LLM endpoint, and forwards those callback turns into the bound external Synapse session.

## Run

Install Synapse first:

```bash
pip install -e '.[dev]'
```

The editable install now pulls the current Agora Python SDK package,
`agora-agent-server-sdk`, which provides the `agora_agent` module used by this example.

Run Synapse with the gateway host first:

```bash
./synapse setup
./synapse gateway setup
./synapse start
```

Run the example frontend:

```bash
cd exmaple-ui
npm install
npm run dev
```

The frontend dev server runs on `http://127.0.0.1:5174`.

If you have older notes that mention installing `agora-agent`, treat that package name as stale.
The supported package name is `agora-agent-server-sdk`.

## Environment

This example reads the shared Synapse home env:

```text
~/.synapse/.env
```

Required for the gateway host:

```bash
AGORA_APP_ID=...
AGORA_APP_CERTIFICATE=...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
SYNAPSE_GATEWAY_PUBLIC_BASE_URL=http://127.0.0.1:8010
SYNAPSE_GATEWAY_SYNAPSE_BASE_URL=http://127.0.0.1:8000
```

The Synapse server on `8000` keeps its runtime env in `~/.synapse/.env`.
If that Synapse server should call a different OpenAI-compatible backend, configure
`OPENAI_API_KEY` and optional `SYNAPSE_OPENAI_BASE_URL` there, not in this example env file.

```bash
OPENAI_API_KEY=...
SYNAPSE_OPENAI_BASE_URL=https://your-llm.example.com/v1
```

Recommended local default for this environment:

```bash
AGORA_CONVOAI_AREA=CN
```

Optional:

```bash
AGORA_CONVOAI_AREA=CN
AGORA_DEEPGRAM_LANGUAGE=en-US
AGORA_ELEVENLABS_MODEL_ID=eleven_flash_v2_5
AGORA_ELEVENLABS_SAMPLE_RATE=24000
AGORA_CONVOAI_AGENT_UID=9001
AGORA_CONVOAI_USER_UID=101
AGORA_CLIENT_TOKEN_TTL_SECONDS=3600
AGORA_CONVOAI_AGENT_INSTRUCTIONS=You are a helpful voice assistant.
AGORA_CONVOAI_AGENT_GREETING=Hello. How can I help you today?
AGORA_CONVOAI_SDK_DEBUG=false

AGORA_FRONTEND_DEFAULT_PROFILE=VOICE
AGORA_FRONTEND_DEFAULT_CHANNEL_NAME=synapse-voice-demo
AGORA_FRONTEND_DEFAULT_DISPLAY_NAME=Synapse Tester

The gateway host settings now live in `~/.synapse/config.yaml`.
```

For live Agora sessions, `SYNAPSE_GATEWAY_PUBLIC_BASE_URL` must be a public URL
that reaches the gateway host. The Agora SDK uses:

```text
${SYNAPSE_GATEWAY_PUBLIC_BASE_URL}/gateway/agora-convoai/chat/completions?binding_id=...
```

as the custom-LLM callback URL.

`SYNAPSE_GATEWAY_SYNAPSE_BASE_URL` is the separate Synapse server this gateway calls for:

- `POST /sessions`
- `POST /sessions/{session_id}/messages`
- `WS /sessions/{session_id}/stream`

## API

### `GET /gateway/agora-convoai/config`

Returns frontend bootstrap config and reports whether this backend has the env it needs.

### `POST /gateway/agora-convoai/sessions/prepare`

Prepares browser bootstrap data before the agent is started.

Returns:

- app id
- channel
- combined RTC/RTM client token
- numeric RTC user uid
- `user_rtm_uid`
- agent RTC uid
- `agent_rtm_uid`
- diagnostics

### `POST /gateway/agora-convoai/sessions/activate`

Activates the local Agora agent only after the browser has:

1. logged into RTM
2. subscribed to the RTM channel
3. joined RTC
4. published the microphone
5. subscribed toolkit messages on the channel

Returns:

- `binding_id`
- `synapse_session_id`
- runtime `agent_id`
- `chat_completions_url`
- diagnostics

### `POST /gateway/agora-convoai/sessions/stop`

Stops the local Agora session and unregisters the bridge binding.

### `POST /chat/completions`

This is the OpenAI-compatible custom-LLM endpoint the locally started ConvoAI agent uses.
The gateway resolves `binding_id`, submits the latest user turn into the bound
Synapse session on `8000`, and returns the Synapse reply in OpenAI-compatible format.

Example:

```bash
curl -X POST \
  'http://127.0.0.1:8010/gateway/agora-convoai/chat/completions?binding_id=binding-ab12cd34' \
  -H 'Content-Type: application/json' \
  --data '{
    "model": "synapse-agora-bridge",
    "messages": [
      {"role": "user", "content": "Check the build status."}
    ]
  }'
```

## Example Frontend

The example frontend is in the repo-root `exmaple-ui/`.

It is a small real voice client that mirrors the official Agora sample startup order:

- prepare bootstrap
- log into RTM with `user_rtm_uid`
- subscribe to the channel
- join RTC with a numeric uid
- publish the microphone
- subscribe toolkit messages
- activate the gateway-host session
- send text to `agent_rtm_uid`

The browser only talks to this repo's example backend routes.

## Call Chain

For a live user turn, the call chain is:

1. browser audio/text enters Agora RTC/RTM
2. Agora ConvoAI calls this backend's public `chat_completions_url`
3. `/gateway/agora-convoai/chat/completions` resolves `binding_id`
4. the bridge submits the latest user text into the Synapse server on `8000`
5. Synapse calls its configured upstream OpenAI-compatible backend
6. `/chat/completions` returns the reply back to Agora

## Connectivity Note

This backend uses the Agora Python SDK's regional endpoint pool. For this example, `AGORA_CONVOAI_AREA=CN` is the recommended default.

If `POST /gateway/agora-convoai/sessions/activate` still fails with a connectivity error, try overriding:

```bash
AGORA_CONVOAI_AREA=US
```

or `EU` / `AP` depending on which region can reach the Agora ConvoAI endpoint from your network.
