function readOptionalEnv(name: string): string | null {
  const raw = import.meta.env[name as keyof ImportMetaEnv];
  if (typeof raw !== "string") {
    return null;
  }
  const trimmed = raw.trim();
  return trimmed || null;
}

const configuredApiBearerToken = readOptionalEnv("VITE_API_BEARER_TOKEN");

export function buildApiRequestInit(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers ?? undefined);
  if (configuredApiBearerToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${configuredApiBearerToken}`);
  }
  return {
    ...init,
    headers,
    credentials: "include",
  };
}
