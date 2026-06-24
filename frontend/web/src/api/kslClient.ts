export type LessonAsset = {
  asset_id: string;
  label: string;
  sample_count: number;
  source: string;
  landmark_path?: string | null;
  stickman_video_path?: string | null;
  stickman_video_url?: string | null;
  batch?: string | null;
  signer_id?: string | null;
  frame_count?: number | null;
  sample_flags?: string[];
  quality_score?: number | null;
  selected_from_flagged_sample?: boolean | null;
};

export type SpeechToTextRequest = {
  audio_url?: string;
  session_id?: string;
};

export type SpeechToTextResponse = {
  transcript: string;
  confidence?: number | null;
  provider?: string | null;
  model_id?: string | null;
  detected_language?: string | null;
  text_to_ksl?: TextToKslResponse | null;
  status: string;
};

export type TextToSpeechRequest = {
  text: string;
  include_ksl?: boolean;
  voice_id?: string | null;
  output_format?: string | null;
  session_id?: string | null;
};

export type TextToSpeechResponse = {
  text: string;
  audio_base64: string;
  audio_size_bytes: number;
  content_type: string;
  file_extension: string;
  provider?: string | null;
  model_id?: string | null;
  voice_id?: string | null;
  output_format?: string | null;
  text_to_ksl?: TextToKslResponse | null;
  status: string;
};

export type TextToKslRequest = {
  text: string;
};

export type TextToKslResponse = {
  original_text: string;
  normalized_text: string;
  gloss: string[];
  matched_terms: string[];
  unmatched_terms: string[];
  supported: boolean;
  dataset_backed: boolean;
  dataset_label_counts: Record<string, number>;
  lesson_assets: LessonAsset[];
  lesson_asset_id?: string | null;
  catalog_backed?: boolean | null;
  catalog_name?: string | null;
  catalog_generated_at?: string | null;
  status: string;
};

const importMetaEnv = (import.meta as ImportMeta & {
  env?: Record<string, string | undefined>;
}).env;

const runtimeConfigBase =
  (globalThis as { __KSL_API_BASE__?: string }).__KSL_API_BASE__?.trim() ||
  importMetaEnv?.VITE_API_BASE_URL?.trim() ||
  "";

function normalizeApiBase(base: string): string {
  const trimmed = base.replace(/\/+$/, "");
  if (!trimmed) {
    return "http://127.0.0.1:8000/api/v1";
  }

  if (trimmed.endsWith("/api/v1")) {
    return trimmed;
  }

  return `${trimmed}/api/v1`;
}

const API_BASE = normalizeApiBase(runtimeConfigBase);
const API_ORIGIN = API_BASE.replace(/\/api\/v1$/, "");

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

export function resolveBackendMediaUrl(urlPath?: string | null) {
  if (!urlPath) {
    return null;
  }

  if (urlPath.startsWith("http://") || urlPath.startsWith("https://")) {
    return urlPath;
  }

  return `${API_ORIGIN}${urlPath}`;
}

export function speechToText(request: SpeechToTextRequest) {
  return postJson<SpeechToTextResponse>("/speech-to-text", request);
}

export function textToKsl(request: TextToKslRequest) {
  return postJson<TextToKslResponse>("/text-to-ksl", request);
}

export function textToSpeech(request: TextToSpeechRequest) {
  return postJson<TextToSpeechResponse>("/text-to-speech", request);
}
