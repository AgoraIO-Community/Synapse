import { afterEach, describe, expect, it, vi } from "vitest";

function okJsonResponse(payload: object): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("gateway-client transport base URL handling", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses relative gateway paths by default", async () => {
    const fetchMock = vi.fn(async () =>
      okJsonResponse({
        ready: true,
        service_base_url: "http://127.0.0.1:8010",
        defaults: {},
        missing_requirements: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = await import("./gateway-client");

    await client.getGatewayConfig();

    expect(fetchMock).toHaveBeenCalledWith("/gateway/agora-convoai/config");
  });

  it("uses the configured gateway base URL for fetches", async () => {
    vi.stubEnv("VITE_GATEWAY_BASE_URL", "https://gateway.example.com");
    const fetchMock = vi.fn(async () =>
      okJsonResponse({
        ready: true,
        service_base_url: "https://gateway.example.com",
        defaults: {},
        missing_requirements: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = await import("./gateway-client");

    await client.getGatewayConfig();
    await client.stopGatewaySession("binding-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://gateway.example.com/gateway/agora-convoai/config",
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://gateway.example.com/gateway/agora-convoai/sessions/stop",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binding_id: "binding-1" }),
      },
    );
  });

  it("normalizes trailing slashes on the configured gateway base URL", async () => {
    vi.stubEnv("VITE_GATEWAY_BASE_URL", "https://gateway.example.com/runtime/");
    const fetchMock = vi.fn(async () =>
      okJsonResponse({
        prepared_session_id: "prepared-1",
        app_id: "agora-app",
        channel_name: "voice-room",
        token: "voice-token",
        uid: 101,
        user_rtm_uid: "101-voice-room",
        agent: { uid: "9001" },
        agent_rtm_uid: "9001-voice-room",
        enable_string_uid: false,
        profile: "VOICE",
        display_name: "Synapse Tester",
        diagnostics: {
          convoai_area: "US",
          selected_url: "https://agora.example.com",
          runtime_session_id: null,
          asr_vendor: "deepgram",
          asr_credential_mode: "managed",
          asr_model: "nova-3",
          tts_vendor: "minimax",
          tts_credential_mode: "managed",
          tts_model: "speech_2_6_turbo",
          agent_uid: "9001",
          agent_rtm_uid: "9001-voice-room",
          rtc_uid: 101,
          rtm_user_id: "101-voice-room",
          enable_string_uid: false,
          enable_rtm: true,
          data_channel: "rtm",
          enable_metrics: true,
          enable_error_message: true,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const client = await import("./gateway-client");

    await client.prepareGatewaySession();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://gateway.example.com/runtime/gateway/agora-convoai/sessions/prepare",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      },
    );
  });
});
