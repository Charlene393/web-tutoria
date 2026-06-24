import { Mic, RotateCcw, Send, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  lessonAssetLandmarkClip,
  resolveBackendMediaUrl,
  speechToTextUpload,
  textToKsl,
  textToSpeech,
  type LessonAsset,
  type LessonLandmarkClipResponse,
  type SpeechToTextResponse,
  type TextToKslResponse,
} from "../../api/kslClient";
import type { LandmarkFrame, SignLandmarkClip } from "../../types/landmarks";
import { ThreeAvatarPlayer } from "../lesson-player/ThreeAvatarPlayer";
import loveClipData from "../lesson-player/data/love.sign.json";
import { getInterpolatedFrame } from "../lesson-player/landmarkPlayback";

type StudioStatus = "idle" | "listening" | "processing" | "ready" | "error";

const EMPTY_FRAME: LandmarkFrame = {
  pose: [],
  leftHand: [],
  rightHand: [],
};

const FALLBACK_CLIP = loveClipData as unknown as SignLandmarkClip;
const END_HOLD_MS = 420;

const LOCAL_CLIP_LIBRARY: Record<string, SignLandmarkClip> = {
  LOVE: FALLBACK_CLIP,
};

function normalizeTokens(tokens: string[]) {
  return tokens.map((token) => token.trim().toUpperCase()).filter(Boolean);
}

function decodeAudioToUrl(audioBase64: string, contentType: string) {
  const binary = window.atob(audioBase64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return URL.createObjectURL(new Blob([bytes], { type: contentType }));
}

function resolveClipFromGloss(gloss: string[]) {
  for (const token of normalizeTokens(gloss)) {
    const clip = LOCAL_CLIP_LIBRARY[token];
    if (clip) {
      return clip;
    }
  }
  return null;
}

function getPreferredAudioFormat() {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
    return {
      mimeType: "",
      extension: "webm",
    };
  }

  const candidates = [
    { mimeType: "audio/webm;codecs=opus", extension: "webm" },
    { mimeType: "audio/webm", extension: "webm" },
    { mimeType: "audio/mp4", extension: "m4a" },
  ];

  for (const candidate of candidates) {
    if (MediaRecorder.isTypeSupported(candidate.mimeType)) {
      return candidate;
    }
  }

  return {
    mimeType: "",
    extension: "webm",
  };
}

export function SpeechToKslStudio() {
  const [status, setStatus] = useState<StudioStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [manualInput, setManualInput] = useState("");
  const [gloss, setGloss] = useState<string[]>([]);
  const [backendMapping, setBackendMapping] = useState<TextToKslResponse | null>(null);
  const [activeLessonIndex, setActiveLessonIndex] = useState(0);
  const [isBackendSequencePlaying, setIsBackendSequencePlaying] = useState(false);
  const [isSpeechGenerating, setIsSpeechGenerating] = useState(false);
  const [speechPlaybackUrl, setSpeechPlaybackUrl] = useState<string | null>(null);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [recordingHint, setRecordingHint] = useState("");
  const [isAvatarClipLoading, setIsAvatarClipLoading] = useState(false);
  const [avatarClipError, setAvatarClipError] = useState<string | null>(null);

  const [clip, setClip] = useState<SignLandmarkClip | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasPlaybackBegun, setHasPlaybackBegun] = useState(false);
  const [framePosition, setFramePosition] = useState(0);
  const [avatarRefreshKey, setAvatarRefreshKey] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const clipCacheRef = useRef<Record<string, SignLandmarkClip>>({});
  const animationRef = useRef<number | null>(null);
  const thinkingPreviewTimeoutRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const playheadMsRef = useRef(0);
  const [isThinkingPreview, setIsThinkingPreview] = useState(false);
  const lessonAudioRef = useRef<HTMLAudioElement | null>(null);
  const backendVideoRef = useRef<HTMLVideoElement | null>(null);

  const activeClip = clip ?? FALLBACK_CLIP;
  const hasResolvedClip = Boolean(clip);
  const backendLessons = backendMapping?.lesson_assets ?? [];
  const activeLesson = backendLessons[activeLessonIndex] ?? null;
  const activeLessonVideoUrl = resolveBackendMediaUrl(activeLesson?.stickman_video_url);
  const activeMatchedTerm = backendMapping?.matched_terms[activeLessonIndex] ?? null;
  const avatarCapabilityLabel = hasResolvedClip
    ? "3D avatar is now consuming real backend landmark frames for the selected lesson step."
    : "Avatar clip is not loaded yet, so the backend stickman video remains the source of truth.";

  const totalFrames = activeClip.frames.length;
  const frameDuration = 1000 / activeClip.fps;
  const clipDuration = (totalFrames - 1) * frameDuration;
  const cycleDuration = clipDuration + END_HOLD_MS;

  const currentFrame = useMemo(() => {
    if (!hasResolvedClip && !hasPlaybackBegun) {
      return EMPTY_FRAME;
    }
    return getInterpolatedFrame(activeClip, framePosition);
  }, [activeClip, framePosition, hasPlaybackBegun, hasResolvedClip]);

  const progress = Math.min(framePosition / Math.max(totalFrames - 1, 1), 1) * 100;

  const resetPlayback = useCallback(() => {
    setIsPlaying(false);
    setHasPlaybackBegun(false);
    setFramePosition(0);
    playheadMsRef.current = 0;
    lastTimestampRef.current = null;
  }, []);

  const startPlayback = useCallback(() => {
    if (!hasResolvedClip) {
      return;
    }
    setFramePosition(0);
    playheadMsRef.current = 0;
    lastTimestampRef.current = null;
    setHasPlaybackBegun(true);
    setIsPlaying(true);
  }, [hasResolvedClip]);

  useEffect(() => {
    if (!isPlaying) {
      if (animationRef.current) {
        window.cancelAnimationFrame(animationRef.current);
      }
      animationRef.current = null;
      lastTimestampRef.current = null;
      return;
    }

    const tick = (timestamp: number) => {
      if (lastTimestampRef.current === null) {
        lastTimestampRef.current = timestamp;
      }

      const elapsed = timestamp - lastTimestampRef.current;
      lastTimestampRef.current = timestamp;
      playheadMsRef.current = (playheadMsRef.current + elapsed) % cycleDuration;

      const activeMs = Math.min(playheadMsRef.current, clipDuration);
      setFramePosition(activeMs / frameDuration);
      animationRef.current = window.requestAnimationFrame(tick);
    };

    animationRef.current = window.requestAnimationFrame(tick);

    return () => {
      if (animationRef.current) {
        window.cancelAnimationFrame(animationRef.current);
      }
    };
  }, [clipDuration, cycleDuration, frameDuration, isPlaying]);

  useEffect(() => {
    return () => {
      if (thinkingPreviewTimeoutRef.current !== null) {
        window.clearTimeout(thinkingPreviewTimeoutRef.current);
      }
      if (speechPlaybackUrl) {
        URL.revokeObjectURL(speechPlaybackUrl);
      }
      mediaRecorderRef.current?.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [speechPlaybackUrl]);

  useEffect(() => {
    if (!speechPlaybackUrl || !lessonAudioRef.current) {
      return;
    }

    lessonAudioRef.current.currentTime = 0;
    void lessonAudioRef.current.play().catch(() => {});
  }, [speechPlaybackUrl]);

  useEffect(() => {
    const assetId = activeLesson?.asset_id;
    if (!assetId) {
      setClip(null);
      setAvatarClipError(null);
      resetPlayback();
      return;
    }

    const cached = clipCacheRef.current[assetId];
    if (cached) {
      setClip(cached);
      setAvatarClipError(null);
      if (status === "ready") {
        startPlayback();
      }
      return;
    }

    let isCancelled = false;
    setIsAvatarClipLoading(true);
    setAvatarClipError(null);

    void lessonAssetLandmarkClip(assetId)
      .then((payload: LessonLandmarkClipResponse) => {
        if (isCancelled) {
          return;
        }

        const nextClip: SignLandmarkClip = {
          label: payload.label,
          fps: payload.fps,
          source: payload.source,
          frames: payload.frames as LandmarkFrame[],
        };

        clipCacheRef.current[assetId] = nextClip;
        setClip(nextClip);
        if (status === "ready") {
          startPlayback();
        }
      })
      .catch((error) => {
        if (isCancelled) {
          return;
        }
        setClip(null);
        setAvatarClipError(
          error instanceof Error ? error.message : "Could not load backend landmark clip.",
        );
        resetPlayback();
      })
      .finally(() => {
        if (!isCancelled) {
          setIsAvatarClipLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [activeLesson?.asset_id, resetPlayback, startPlayback, status]);

  useEffect(() => {
    if (!isBackendSequencePlaying || !activeLessonVideoUrl || !backendVideoRef.current) {
      return;
    }

    backendVideoRef.current.currentTime = 0;
    void backendVideoRef.current.play().catch(() => {});
  }, [activeLessonIndex, activeLessonVideoUrl, isBackendSequencePlaying]);

  const runPipeline = useCallback(async (text: string) => {
    const normalizedText = text.trim();
    if (!normalizedText) {
      return;
    }

    setStatus("processing");
    setErrorMessage(null);
    setSpeechError(null);
    setTranscript(normalizedText);
    setInterimTranscript("");
    setActiveLessonIndex(0);

    try {
      const mapped = await textToKsl({ text: normalizedText });
      setBackendMapping(mapped);
      setIsBackendSequencePlaying(mapped.lesson_assets.length > 0);
      const nextGloss = normalizeTokens(mapped.gloss);
      setGloss(nextGloss);
      setStatus("ready");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Could not map text to KSL.");
      setBackendMapping(null);
      setClip(null);
      resetPlayback();
    }
  }, [resetPlayback]);

  const applyBackendSpeechMapping = useCallback(
    (payload: SpeechToTextResponse, fallbackText: string) => {
      const backendText = payload.transcript?.trim() || fallbackText.trim();
      const mapped = payload.text_to_ksl ?? null;

      setTranscript(backendText);
      setInterimTranscript("");
      setActiveLessonIndex(0);
      setIsBackendSequencePlaying(Boolean(mapped?.lesson_assets?.length));

      if (!mapped) {
        void runPipeline(backendText);
        return;
      }

      setBackendMapping(mapped);
      const nextGloss = normalizeTokens(mapped.gloss);
      setGloss(nextGloss);
      setStatus("ready");
    },
    [runPipeline],
  );

  const speakTranscript = useCallback(async () => {
    const text = transcript.trim() || manualInput.trim();
    if (!text) {
      setSpeechError("No transcript available yet for speech output.");
      return;
    }

    setIsSpeechGenerating(true);
    setSpeechError(null);

    try {
      const payload = await textToSpeech({
        text,
        include_ksl: false,
      });

      if (speechPlaybackUrl) {
        URL.revokeObjectURL(speechPlaybackUrl);
      }

      setSpeechPlaybackUrl(decodeAudioToUrl(payload.audio_base64, payload.content_type));
    } catch (error) {
      setSpeechError(error instanceof Error ? error.message : "Could not generate backend speech.");
    } finally {
      setIsSpeechGenerating(false);
    }
  }, [manualInput, speechPlaybackUrl, transcript]);

  const startListening = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setStatus("error");
      setErrorMessage("Microphone recording is not supported in this browser. Use the text box below.");
      return;
    }

    if (typeof MediaRecorder === "undefined") {
      setStatus("error");
      setErrorMessage("MediaRecorder is not available in this browser. Use the text box below.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const { mimeType, extension } = getPreferredAudioFormat();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.onstart = () => {
        setStatus("listening");
        setErrorMessage(null);
        setSpeechError(null);
        setRecordingHint("Recording from microphone...");
        setInterimTranscript("Recording...");
      };

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setStatus("error");
        setErrorMessage("Microphone recording failed.");
        setRecordingHint("");
        setInterimTranscript("");
      };

      recorder.onstop = async () => {
        const chunks = audioChunksRef.current;
        const blobMimeType = mimeType || recorder.mimeType || "audio/webm";
        const audioBlob = new Blob(chunks, { type: blobMimeType });
        audioChunksRef.current = [];
        mediaRecorderRef.current = null;
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;

        if (!audioBlob.size) {
          setStatus("error");
          setErrorMessage("No microphone audio was captured. Please try again.");
          setRecordingHint("");
          setInterimTranscript("");
          return;
        }

        setStatus("processing");
        setRecordingHint("Uploading audio to backend...");
        setInterimTranscript("Uploading audio...");

        try {
          const payload = await speechToTextUpload({
            audioBlob,
            filename: `speech-input.${extension}`,
            includeKsl: true,
          });
          applyBackendSpeechMapping(payload, payload.transcript ?? "");
          setRecordingHint("Backend transcription complete.");
        } catch (error) {
          setStatus("error");
          setErrorMessage(
            error instanceof Error ? error.message : "Could not upload microphone audio to backend.",
          );
        } finally {
          setInterimTranscript("");
        }
      };

      recorder.start();
    } catch (error) {
      setStatus("error");
      setErrorMessage(
        error instanceof Error ? error.message : "Could not access the microphone for recording.",
      );
      setRecordingHint("");
    }
  }, [applyBackendSpeechMapping]);

  const stopListening = useCallback(() => {
    if (!mediaRecorderRef.current) {
      return;
    }

    if (mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const handleBackendSequenceRestart = useCallback(() => {
    if (!backendLessons.length) {
      return;
    }

    setActiveLessonIndex(0);
    setIsBackendSequencePlaying(true);
  }, [backendLessons.length]);

  const handleBackendVideoEnded = useCallback(() => {
    if (!isBackendSequencePlaying) {
      return;
    }

    if (activeLessonIndex < backendLessons.length - 1) {
      setActiveLessonIndex((index) => index + 1);
      return;
    }

    setIsBackendSequencePlaying(false);
  }, [activeLessonIndex, backendLessons.length, isBackendSequencePlaying]);

  const submitManual = useCallback((event: FormEvent) => {
    event.preventDefault();
    void runPipeline(manualInput);
  }, [manualInput, runPipeline]);

  const testThinkingAnimation = useCallback(() => {
    if (thinkingPreviewTimeoutRef.current !== null) {
      window.clearTimeout(thinkingPreviewTimeoutRef.current);
    }

    setIsThinkingPreview(true);
    thinkingPreviewTimeoutRef.current = window.setTimeout(() => {
      setIsThinkingPreview(false);
      thinkingPreviewTimeoutRef.current = null;
    }, 2200);
  }, []);

  const isBusy = status === "processing";
  const isListening = status === "listening";
  const hasSpeechInput = Boolean((transcript || interimTranscript).trim());
  const glossPlaceholder = hasSpeechInput ? ["Waiting for KSL"] : [];
  const backendStatusSummary = backendMapping
    ? `${backendMapping.status.toUpperCase()} · ${backendLessons.length} lesson assets`
    : "Waiting for backend mapping";

  const showVoiceAnimation = isBusy || isThinkingPreview;
  const showTranscript = !isThinkingPreview && status === "ready" && Boolean(transcript.trim());

  return (
    <main className="voice-shell">
      <section className="voice-layout" aria-labelledby="voice-title">
        <div className="voice-copy">
          <h1 id="voice-title">Tutoria.</h1>
          <div className="voice-readout" aria-live="polite">
            <span className="voice-label">Transcript</span>
            {showVoiceAnimation ? (
              <div className="voice-thinking" role="status" aria-label="Thinking indicator">
                <span className="voice-thinking-label">Thinking</span>
                <span className="voice-wave" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            ) : (
              <p>{showTranscript ? transcript : recordingHint || ""}</p>
            )}
          </div>

          <div className="gloss-row" aria-label="KSL gloss output">
            {(gloss.length ? gloss : glossPlaceholder).map((token, index) => (
              <span key={`${token}-${index}`} className={gloss.length ? "is-live" : ""}>
                {token}
              </span>
            ))}
          </div>

          <div className="voice-controls" aria-label="Speech controls">
            <button
              type="button"
              className="orb-button"
              onClick={isListening ? stopListening : startListening}
              disabled={isBusy}
              title={isListening ? "Stop recording" : "Start microphone recording"}
            >
              {isListening ? <Square aria-hidden="true" /> : <Mic aria-hidden="true" />}
              <span>{isListening ? "Recording... tap to stop" : "Tap to record"}</span>
            </button>

            <form className="manual-input" onSubmit={submitManual}>
              <input
                value={manualInput}
                onChange={(event) => setManualInput(event.target.value)}
                placeholder="Type text if microphone is unavailable"
                aria-label="Manual text input"
              />
              <button type="submit" disabled={isBusy || !manualInput.trim()}>
                <Send aria-hidden="true" />
                <span>Convert</span>
              </button>
            </form>

            <button
              type="button"
              className="primary-button"
              onClick={testThinkingAnimation}
              disabled={isBusy || isListening || isThinkingPreview}
            >
              <span>Test Thinking Animation</span>
            </button>
          </div>

          <div className="pipeline-state" role={status === "error" ? "alert" : "status"}>
            <strong>{status.toUpperCase()}</strong>
            <span>
              {errorMessage ||
                (status === "processing"
                  ? "Mapping speech to KSL..."
                  : "Ready for your next phrase.")}
            </span>
          </div>

          <div className="backend-proof">
            <div className="backend-proof-header">
             
              <div className="backend-proof-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void speakTranscript()}
                  disabled={isBusy || isSpeechGenerating || !transcript.trim()}
                >
                  <span>{isSpeechGenerating ? "Generating speech..." : "Speak backend output"}</span>
                </button>
                <button
                  type="button"
                  className="primary-button secondary-surface"
                  onClick={handleBackendSequenceRestart}
                  disabled={!backendLessons.length}
                >
                  <span>{isBackendSequencePlaying ? "Sequence playing" : "Play lesson sequence"}</span>
                </button>
              </div>
            </div>

            <div className="lesson-asset-grid">
              
            </div>

            {backendLessons.length ? (
              <div className="lesson-asset-sequence" aria-label="Backend lesson assets">
                {backendLessons.map((lesson: LessonAsset, index) => (
                  <button
                    key={`${lesson.asset_id}-${index}`}
                    type="button"
                    className={`lesson-asset-chip${index === activeLessonIndex ? " is-active" : ""}`}
                    onClick={() => {
                      setActiveLessonIndex(index);
                      setIsBackendSequencePlaying(false);
                    }}
                  >
                    <span>{index + 1}</span>
                    <strong>{lesson.label}</strong>
                  </button>
                ))}
              </div>
            ) : null}

            {speechPlaybackUrl ? (
              <div className="speech-output-bar">
                <span className="voice-label">Backend speech output</span>
                <audio ref={lessonAudioRef} controls src={speechPlaybackUrl} className="voice-audio" />
              </div>
            ) : null}

            {speechError ? (
              <div className="pipeline-state" role="alert">
                <strong>Speech error</strong>
                <span>{speechError}</span>
              </div>
            ) : null}

            {avatarClipError ? (
              <div className="pipeline-state" role="alert">
                <strong>Avatar clip error</strong>
                <span>{avatarClipError}</span>
              </div>
            ) : null}
          </div>
        </div>

        <div className="avatar-panel">
          <div className="stage-toolbar" aria-label="Avatar animation controls">
            <button
              className="icon-button"
              type="button"
              onClick={() => {
                resetPlayback();
                setAvatarRefreshKey((current) => current + 1);
              }}
              title="Refresh character model"
              aria-label="Refresh character model"
            >
              <RotateCcw aria-hidden="true" />
            </button>
          </div>

          <ThreeAvatarPlayer
            key={avatarRefreshKey}
            frame={currentFrame}
            isPlaying={isPlaying}
            hasPlaybackBegun={hasPlaybackBegun}
          />

          <div className="timeline" aria-label="Animation progress">
            <div className="timeline-track">
              <div className="timeline-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <div className="stickman-panel">
            <div className="stickman-copy">
              <span className="voice-label">Backend stickman lesson proof</span>
              <strong>{activeLesson?.label ?? "No lesson asset selected"}</strong>
              <p>{avatarCapabilityLabel}</p>
              <span className="stickman-sequence-badge">
                {isAvatarClipLoading ? "Loading avatar landmark clip" : "Avatar clip synced to lesson"}
              </span>
              <span className="stickman-sequence-badge">
                {isBackendSequencePlaying ? "Auto-stepping lesson sequence" : "Manual lesson step"}
              </span>
            </div>

            <div className="stickman-stage">
              {activeLessonVideoUrl ? (
                <video
                  ref={backendVideoRef}
                  key={activeLessonVideoUrl}
                  src={activeLessonVideoUrl}
                  controls
                  playsInline
                  preload="metadata"
                  muted
                  className="stickman-video"
                  onEnded={handleBackendVideoEnded}
                />
              ) : (
                <div className="three-stage three-stage-error">
                  <strong>No backend stickman lesson clip yet.</strong>
                  <span>Run the mapping pipeline with a supported phrase to load the dataset sign preview.</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
