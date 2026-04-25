import { describe, expect, it } from "vitest";
import { gzip } from "pako";
import { agoraSttTextMessage, extractTranscriptText } from "./stt-transcript";

function encodeAgoraSttMessage(payload: Record<string, unknown>): Uint8Array {
  return agoraSttTextMessage.encode(agoraSttTextMessage.create(payload)).finish();
}

describe("extractTranscriptText", () => {
  it("extracts plain string transcripts", () => {
    expect(extractTranscriptText("hello there")).toEqual({ text: "hello there", final: true, source: "plain-text" });
  });

  it("extracts JSON byte transcripts", () => {
    const bytes = new TextEncoder().encode(JSON.stringify({ text: "json bytes", final: true }));
    expect(extractTranscriptText(bytes)).toMatchObject({ text: "json bytes", final: true });
  });

  it("extracts gzipped JSON byte transcripts", () => {
    const bytes = gzip(new TextEncoder().encode(JSON.stringify({ text: "gzipped json", final: true })));
    expect(extractTranscriptText(bytes)).toMatchObject({ text: "gzipped json", final: true });
  });

  it("extracts plain object transcripts", () => {
    expect(extractTranscriptText({ words: [{ text: "plain" }, { text: "object" }], isFinal: true })).toMatchObject({
      text: "plain object",
      final: true,
      source: "object-words",
    });
  });

  it("extracts nested result transcripts", () => {
    expect(extractTranscriptText({ result: { text: "nested interim", isFinal: false } })).toMatchObject({
      text: "nested interim",
      final: false,
    });
    expect(extractTranscriptText({ result: { text: "nested final", isFinal: true } })).toMatchObject({
      text: "nested final",
      final: true,
    });
  });

  it("extracts nested data transcripts", () => {
    expect(extractTranscriptText({ data: JSON.stringify({ text: "json data", final: true }) })).toMatchObject({
      text: "json data",
      final: true,
    });
    expect(extractTranscriptText({ data: { words: [{ word: "word" }, { word: "data", final: true }], final: true } })).toMatchObject({
      text: "word data",
      final: true,
    });
  });

  it("extracts official JSON transcript wrappers", () => {
    expect(extractTranscriptText({ transcript: { language: "zh-CN", text: "你好", isFinal: false } })).toEqual({
      text: "你好",
      final: false,
      language: "zh-CN",
      source: "transcript-wrapper",
    });
    expect(extractTranscriptText({ transcript: { language: "zh-CN", text: "你好世界", isFinal: true } })).toEqual({
      text: "你好世界",
      final: true,
      language: "zh-CN",
      source: "transcript-wrapper",
    });
  });

  it("extracts original transcript from translation wrappers", () => {
    expect(extractTranscriptText({
      translation: {
        original_transcript: { language: "zh-CN", text: "原始中文", isFinal: true },
        translated_transcript: { language: "en-US", text: "original Chinese", isFinal: true },
      },
    })).toEqual({ text: "原始中文", final: true, language: "zh-CN", source: "translation-original" });
  });

  it("extracts interim Agora protobuf transcripts", () => {
    const bytes = encodeAgoraSttMessage({
      data_type: "transcribe",
      words: [{ text: "interim text", isFinal: false }],
      end_of_segment: false,
    });
    expect(extractTranscriptText(bytes)).toEqual({ text: "interim text", final: false, source: "protobuf-words" });
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
    expect(extractTranscriptText(bytes)).toEqual({ text: "finaltext", final: true, source: "protobuf-words" });
  });

  it("extracts gzipped Agora protobuf transcripts", () => {
    const bytes = gzip(encodeAgoraSttMessage({
      data_type: "transcribe",
      words: [{ text: "gzipped", isFinal: true }],
      end_of_segment: true,
    }));
    expect(extractTranscriptText(bytes)).toEqual({ text: "gzipped", final: true, source: "protobuf-words" });
  });

  it("returns null for empty or unrecognized payloads", () => {
    expect(extractTranscriptText("")).toBeNull();
    expect(extractTranscriptText({ nope: true })).toBeNull();
    expect(extractTranscriptText(new Uint8Array([0]))).toBeNull();
    expect(extractTranscriptText(new Uint8Array([0x1f, 0x8b, 0]))).toBeNull();
  });
});
