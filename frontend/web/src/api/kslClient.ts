export type SpeechToTextRequest = {
  audio_url?: string;
  session_id?: string;
};

export type SpeechToTextResponse = {
  transcript: string;
  confidence?: number | null;
  status: string;
};

export type TextToKslRequest = {
  text: string;
};

export type TextToKslResponse = {
  gloss: string[];
  lesson_asset_id?: string | null;
  status: string;
};

const runtimeConfigBase =
  (globalThis as { __KSL_API_BASE__?: string }).__KSL_API_BASE__?.trim() || "";

const API_BASE = runtimeConfigBase || "http://localhost:8000/api/v1";

async function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed (${response.status})`);
  }

  return (await response.json()) as TResponse;
}

export function speechToText(request: SpeechToTextRequest) {
  return postJson<SpeechToTextResponse>("/speech-to-text", request);
}

export function textToKsl(request: TextToKslRequest) {
  return postJson<TextToKslResponse>("/text-to-ksl", request);
}
