import protobuf from "protobufjs/light";
import { ungzip } from "pako";

export type ExtractedSttTranscript = {
  text: string;
  final: boolean;
};

const sttRoot = protobuf.Root.fromJSON({
  nested: {
    agora: {
      nested: {
        audio2text: {
          nested: {
            Text: {
              fields: {
                vendor: { type: "int32", id: 1 },
                version: { type: "int32", id: 2 },
                seqnum: { type: "int32", id: 3 },
                uid: { type: "uint32", id: 4 },
                flag: { type: "int32", id: 5 },
                time: { type: "int64", id: 6 },
                lang: { type: "int32", id: 7 },
                starttime: { type: "int32", id: 8 },
                offtime: { type: "int32", id: 9 },
                words: { rule: "repeated", type: "Word", id: 10 },
                end_of_segment: { type: "bool", id: 11 },
                duration_ms: { type: "int32", id: 12 },
                data_type: { type: "string", id: 13 },
                trans: { rule: "repeated", type: "Translation", id: 14 },
              },
            },
            Word: {
              fields: {
                text: { type: "string", id: 1 },
                startMs: { type: "int32", id: 2 },
                durationMs: { type: "int32", id: 3 },
                isFinal: { type: "bool", id: 4 },
                confidence: { type: "double", id: 5 },
              },
            },
            Translation: {
              fields: {
                isFinal: { type: "bool", id: 1 },
                lang: { type: "string", id: 2 },
                texts: { rule: "repeated", type: "string", id: 3 },
              },
            },
          },
        },
      },
    },
  },
});

export const agoraSttTextMessage = sttRoot.lookupType("agora.audio2text.Text");

const textDecoder = new TextDecoder();

export function extractTranscriptText(payload: unknown): ExtractedSttTranscript | null {
  if (typeof payload === "string") {
    return extractStringTranscript(payload);
  }
  const bytes = payloadToBytes(payload);
  if (bytes) {
    return extractBytesTranscript(bytes);
  }
  if (!payload || typeof payload !== "object") return null;
  return extractRecordTranscript(payload as Record<string, any>);
}

function extractStringTranscript(payload: string): ExtractedSttTranscript | null {
  const trimmed = payload.trim();
  if (!trimmed) return null;
  try {
    return extractTranscriptText(JSON.parse(trimmed));
  } catch {
    return { text: trimmed, final: true };
  }
}

function extractBytesTranscript(bytes: Uint8Array): ExtractedSttTranscript | null {
  const inflated = inflateGzipPayload(bytes);
  if (inflated) {
    return extractBytesTranscript(inflated);
  }
  const decodedText = decodeUtf8Transcript(bytes);
  if (decodedText) return decodedText;
  return decodeProtobufTranscript(bytes);
}

function inflateGzipPayload(bytes: Uint8Array): Uint8Array | null {
  if (bytes.byteLength < 2 || bytes[0] !== 0x1f || bytes[1] !== 0x8b) return null;
  try {
    return ungzip(bytes);
  } catch {
    return null;
  }
}

function decodeUtf8Transcript(bytes: Uint8Array): ExtractedSttTranscript | null {
  try {
    const decoded = textDecoder.decode(bytes).trim();
    if (!decoded) return null;
    if (decoded.startsWith("{") || decoded.startsWith("[")) {
      const parsed = extractTranscriptText(JSON.parse(decoded));
      if (parsed) return parsed;
    }
    if (isMostlyPrintable(decoded)) {
      return { text: decoded, final: true };
    }
  } catch {}
  return null;
}

function decodeProtobufTranscript(bytes: Uint8Array): ExtractedSttTranscript | null {
  try {
    const decoded = agoraSttTextMessage.toObject(agoraSttTextMessage.decode(bytes), {
      defaults: false,
      longs: Number,
    }) as Record<string, any>;
    const words = Array.isArray(decoded.words) ? decoded.words : [];
    const wordText = words
      .map((word) => (typeof word?.text === "string" ? word.text.trim() : ""))
      .filter(Boolean)
      .join("")
      .trim();
    const translations = Array.isArray(decoded.trans) ? decoded.trans : [];
    const translationText = translations
      .flatMap((translation) => (Array.isArray(translation?.texts) ? translation.texts : []))
      .filter((text) => typeof text === "string" && text.trim())
      .join(" ")
      .trim();
    const text = wordText || translationText;
    if (!text) return null;
    const wordFinal = words.length > 0 && words.every((word) => word?.isFinal === true);
    const translationFinal = translations.length > 0 && translations.every((translation) => translation?.isFinal === true);
    return {
      text,
      final: decoded.end_of_segment === true || wordFinal || translationFinal,
    };
  } catch {
    return null;
  }
}

function extractRecordTranscript(record: Record<string, any>): ExtractedSttTranscript | null {
  const wrappedTranscript = extractWrappedTranscript(record.transcript);
  if (wrappedTranscript) return wrappedTranscript;
  const originalTranscript = extractWrappedTranscript(record.translation?.original_transcript);
  if (originalTranscript) return originalTranscript;
  const nested = [record.result, record.data, record.payload].find((item) => item != null);
  if (nested != null && nested !== record) {
    const parsed = extractTranscriptText(nested);
    if (parsed) return parsed;
  }
  const candidates = [
    record.text,
    record.transcript,
    record.message,
    extractWordsText(record.words),
  ];
  const text = candidates.find((item) => typeof item === "string" && item.trim());
  if (!text) return null;
  const final = isFinalRecord(record);
  return { text: text.trim(), final };
}

function extractWrappedTranscript(transcript: unknown): ExtractedSttTranscript | null {
  if (!transcript || typeof transcript !== "object") return null;
  const record = transcript as Record<string, any>;
  if (typeof record.text !== "string" || !record.text.trim()) return null;
  return { text: record.text.trim(), final: isFinalRecord(record) };
}

function extractWordsText(words: unknown): string | null {
  if (!Array.isArray(words)) return null;
  const text = words
    .map((word) => {
      if (typeof word === "string") return word;
      if (!word || typeof word !== "object") return "";
      const record = word as Record<string, any>;
      return record.text ?? record.word ?? "";
    })
    .filter((item) => typeof item === "string" && item.trim())
    .join(" ")
    .trim();
  return text || null;
}

function isFinalRecord(record: Record<string, any>): boolean {
  const status = String(record.status ?? record.type ?? record.state ?? "").toLowerCase();
  if (record.final === true || record.isFinal === true || record.end_of_segment === true || record.endOfSegment === true) return true;
  if (["final", "end", "complete", "completed"].includes(status)) return true;
  if (Array.isArray(record.words) && record.words.length > 0) {
    return record.words.every((word: any) => word?.isFinal === true || word?.final === true);
  }
  return false;
}

function payloadToBytes(payload: unknown): Uint8Array | null {
  if (payload instanceof Uint8Array) return payload;
  if (payload instanceof ArrayBuffer) return new Uint8Array(payload);
  if (ArrayBuffer.isView(payload)) {
    return new Uint8Array(payload.buffer, payload.byteOffset, payload.byteLength);
  }
  return null;
}

function isMostlyPrintable(value: string): boolean {
  if (!value) return false;
  let printable = 0;
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code === 9 || code === 10 || code === 13 || code >= 32) printable += 1;
  }
  return printable / value.length > 0.9;
}
