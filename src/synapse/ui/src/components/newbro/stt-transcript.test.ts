import { describe, expect, it } from "vitest";
import { gzip } from "pako";
import { agoraSttTextMessage, extractTranscriptText } from "./stt-transcript";

function encodeAgoraSttMessage(payload: Record<string, unknown>): Uint8Array {
  return agoraSttTextMessage.encode(agoraSttTextMessage.create(payload)).finish();
}

describe("extractTranscriptText", () => {
  it("extracts plain string transcripts", () => {
    expect(extractTranscriptText("hello there")).toEqual({ text: "hello there", final: true });
  });

  it("extracts JSON byte transcripts", () => {
    const bytes = new TextEncoder().encode(JSON.stringify({ text: "json bytes", final: true }));
    expect(extractTranscriptText(bytes)).toEqual({ text: "json bytes", final: true });
  });

  it("extracts gzipped JSON byte transcripts", () => {
    const bytes = gzip(new TextEncoder().encode(JSON.stringify({ text: "gzipped json", final: true })));
    expect(extractTranscriptText(bytes)).toEqual({ text: "gzipped json", final: true });
  });

  it("extracts plain object transcripts", () => {
    expect(extractTranscriptText({ words: [{ text: "plain" }, { text: "object" }], isFinal: true })).toEqual({
      text: "plain object",
      final: true,
    });
  });

  it("extracts interim Agora protobuf transcripts", () => {
    const bytes = encodeAgoraSttMessage({
      data_type: "transcribe",
      words: [{ text: "interim text", isFinal: false }],
      end_of_segment: false,
    });
    expect(extractTranscriptText(bytes)).toEqual({ text: "interim text", final: false });
  });

  it("extracts final Agora protobuf transcripts", () => {
    const bytes = encodeAgoraSttMessage({
      data_type: "transcribe",
      words: [
        { text: "final", isFinal: true },
        { text: "text", isFinal: true },
      ],
      end_of_segment: true,
    });
    expect(extractTranscriptText(bytes)).toEqual({ text: "finaltext", final: true });
  });

  it("extracts gzipped Agora protobuf transcripts", () => {
    const bytes = gzip(encodeAgoraSttMessage({
      data_type: "transcribe",
      words: [{ text: "gzipped", isFinal: true }],
      end_of_segment: true,
    }));
    expect(extractTranscriptText(bytes)).toEqual({ text: "gzipped", final: true });
  });

  it("returns null for empty or unrecognized payloads", () => {
    expect(extractTranscriptText("")).toBeNull();
    expect(extractTranscriptText({ nope: true })).toBeNull();
    expect(extractTranscriptText(new Uint8Array([0]))).toBeNull();
    expect(extractTranscriptText(new Uint8Array([0x1f, 0x8b, 0]))).toBeNull();
  });
});
