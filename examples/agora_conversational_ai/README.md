# Agora Conversational AI Example

This example makes `examples/agora_conversational_ai/app.py` the only backend for this example.

It does three jobs:

- starts and stops Agora ConvoAI sessions directly through the Python SDK module `agora_agent`
- exposes a public OpenAI-compatible `/chat/completions` edge for Agora custom-LLM callbacks
- serves as the backend for the local React voice test client

This backend is now a bridge in front of a separate Synopse server. Run Synopse itself on
port `8000`, and run this Agora bridge on port `8010`.

## Flow

1. Start the normal Synopse server on `8000`.
2. Configure this example backend with Agora App Credentials plus the provider keys it needs.
3. Start the example backend on `8010`.
4. Start the example-local voice frontend.
5. The frontend calls `POST /frontend/session/prepare`.
6. The browser initializes RTC and RTM, subscribes to the channel, and then calls `POST /frontend/session/activate`.
7. This backend creates a Synopse session on `8000`, reserves a `bridge_session_id`, starts the ConvoAI agent locally with that public `/chat/completions` URL as its LLM endpoint, and forwards those callback turns into the bound external Synopse session.

## Run

Install Synopse first:

```bash
pip install -e '.[dev]'
```

The editable install now pulls the current Agora Python SDK package,
`agora-agent-server-sdk`, which provides the `agora_agent` module used by this example.

Create the example-local env file:

```bash
cp examples/agora_conversational_ai/.env.example examples/agora_conversational_ai/.env.local
```

Run Synopse itself first:

```bash
uvicorn synopse.api.app:app --reload --port 8000
```

Run the Agora bridge backend:

```bash
uvicorn examples.agora_conversational_ai.app:app --reload --port 8010
```

Run the example frontend:

```bash
cd examples/agora_conversational_ai/frontend
npm install
npm run dev
```

The frontend dev server runs on `http://127.0.0.1:5174` and proxies `/frontend/*` to the local backend on port `8010`.

If you have older notes that mention installing `agora-agent`, treat that package name as stale.
The supported package name is `agora-agent-server-sdk`.

## Environment

This example reads:

```text
examples/agora_conversational_ai/.env.local
```

Required for the bridge on `8010`:

```bash
AGORA_APP_ID=...
AGORA_APP_CERTIFICATE=...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
AGORA_BRIDGE_SYNOPSE_BASE_URL=http://127.0.0.1:8000
```

The Synopse server on `8000` keeps its own runtime env in the repo-root `.env.local`.
If that Synopse server should call a different OpenAI-compatible backend, configure
`OPENAI_API_KEY` and optional `SYNOPSE_OPENAI_BASE_URL` there, not in this example env file.

```bash
OPENAI_API_KEY=...
SYNOPSE_OPENAI_BASE_URL=https://your-llm.example.com/v1
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
AGORA_FRONTEND_DEFAULT_CHANNEL_NAME=synopse-voice-demo
AGORA_FRONTEND_DEFAULT_DISPLAY_NAME=Synopse Tester

AGORA_BRIDGE_SYNOPSE_BASE_URL=http://127.0.0.1:8000
AGORA_BRIDGE_SERVICE_BASE_URL=http://127.0.0.1:8010
AGORA_BRIDGE_MODEL=synopse-agora-bridge
AGORA_BRIDGE_SPEAK_PRIORITY=APPEND
AGORA_BRIDGE_SPEAK_INTERRUPTABLE=true
AGORA_BRIDGE_REQUEST_TIMEOUT_SECONDS=10
```

For live Agora sessions, `AGORA_BRIDGE_SERVICE_BASE_URL` must be a public URL that
reaches this backend. The Agora SDK uses:

```text
${AGORA_BRIDGE_SERVICE_BASE_URL}/chat/completions?bridge_session_id=...
```

as the custom-LLM callback URL.

`AGORA_BRIDGE_SYNOPSE_BASE_URL` is the separate Synopse server this bridge calls for:

- `POST /sessions`
- `POST /sessions/{session_id}/messages`
- `WS /sessions/{session_id}/stream`

## API

### `GET /frontend/config`

Returns frontend bootstrap config and reports whether this backend has the env it needs.

### `POST /frontend/session/prepare`

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

### `POST /frontend/session/activate`

Activates the local Agora agent only after the browser has:

1. logged into RTM
2. subscribed to the RTM channel
3. joined RTC
4. published the microphone
5. subscribed toolkit messages on the channel

Returns:

- `bridge_session_id`
- `synopse_session_id`
- runtime `agent_id`
- `chat_completions_url`
- diagnostics

### `POST /frontend/session/stop`

Stops the local Agora session and unregisters the bridge binding.

### `POST /chat/completions`

This is the OpenAI-compatible custom-LLM endpoint the locally started ConvoAI agent uses.
The bridge resolves `bridge_session_id`, submits the latest user turn into the bound
Synopse session on `8000`, and returns the Synopse reply in OpenAI-compatible format.

Example:

```bash
curl -X POST \
  'http://127.0.0.1:8010/chat/completions?bridge_session_id=bridge-ab12cd34' \
  -H 'Content-Type: application/json' \
  --data '{
    "model": "synopse-agora-bridge",
    "messages": [
      {"role": "user", "content": "Check the build status."}
    ]
  }'
```

## Example Frontend

The example frontend is in `examples/agora_conversational_ai/frontend/`.

It is a small real voice client that mirrors the official Agora sample startup order:

- prepare bootstrap
- log into RTM with `user_rtm_uid`
- subscribe to the channel
- join RTC with a numeric uid
- publish the microphone
- subscribe toolkit messages
- activate the backend agent
- send text to `agent_rtm_uid`

The browser only talks to this repo's example backend routes.

## Call Chain

For a live user turn, the call chain is:

1. browser audio/text enters Agora RTC/RTM
2. Agora ConvoAI calls this backend's public `chat_completions_url`
3. `/chat/completions` resolves `bridge_session_id`
4. the bridge submits the latest user text into the Synopse server on `8000`
5. Synopse calls its configured upstream OpenAI-compatible backend
6. `/chat/completions` returns the reply back to Agora

## Connectivity Note

This backend uses the Agora Python SDK's regional endpoint pool. For this example, `AGORA_CONVOAI_AREA=CN` is the recommended default.

If `POST /frontend/session/activate` still fails with a connectivity error, try overriding:

```bash
AGORA_CONVOAI_AREA=US
```

or `EU` / `AP` depending on which region can reach the Agora ConvoAI endpoint from your network.
