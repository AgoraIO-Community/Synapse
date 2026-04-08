# Agora Conversational AI

This guide documents the supported Synopse integration path for `examples/agora_conversational_ai`.

## Example Shape

This specific example uses one backend only:

- `examples/agora_conversational_ai/app.py`

That backend owns:

- Agora ConvoAI lifecycle via the Python SDK `agora-agent`
- browser RTC/RTM token generation
- Synopse bridge binding
- proactive notification speech through the local ConvoAI session

It also exposes the browser-facing routes:

- `GET /frontend/config`
- `POST /frontend/session/prepare`
- `POST /frontend/session/activate`
- `POST /frontend/session/stop`
- `POST /chat/completions`

There is no separate sample-backend proxy in this example anymore.

## Behavior

- one live Agora agent binds to one Synopse session
- duplicate runtime-agent bindings are rejected
- the bridge translates the latest user turn into a Synopse session message
- Synopse owns normal conversational replies
- this example backend owns Agora auth and calls Agora APIs on behalf of this example
- the browser prepares and subscribes RTC/RTM before agent activation, matching the official sample
- proactive notification delivery is triggered only for Synopse notification events
- normal chat replies are not replayed through `/speak`
- the example frontend talks only to this repo's example backend

## Notification Delivery

The bridge subscribes to the Synopse session stream and watches for `conversation_appended` events with `source="notification"`.

When such an event arrives, the bridge calls the local ConvoAI service `say()` path for the started SDK session. This keeps Agora auth inside the example backend and out of the frontend.

## Identity Model

This example now mirrors the official sample's split identity model:

- RTC user uid: numeric uid
- RTM user uid: `<user_uid>-<channel>`
- agent RTC uid: configured agent uid
- agent RTM uid: `<agent_uid>-<channel>`

The frontend uses the agent RTM uid for toolkit messaging calls and the agent RTC uid for media/transcript identity.

## Run

Install Synopse in editable mode, then run:

```bash
uvicorn examples.agora_conversational_ai.app:app --reload --port 8010
```

For the browser test client:

```bash
cd examples/agora_conversational_ai/frontend
npm install
npm run dev
```

The example reads its env from `examples/agora_conversational_ai/.env.local`. Configure local App Credentials and provider keys there before starting live sessions.

For this example, `AGORA_CONVOAI_AREA=CN` is the recommended starting value. If live start still fails with connectivity errors, try `US`, `EU`, or `AP`.

## Ownership Note

This “single backend” rule applies only to `examples/agora_conversational_ai`.

Future examples in this repo may still use separate backend topologies when that better fits the example design.
