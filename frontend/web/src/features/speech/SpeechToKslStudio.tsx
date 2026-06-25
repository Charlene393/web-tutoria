import { Hand, ImagePlus, Mic, Play, RotateCcw, Send, Square, Volume2 } from "lucide-react";
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
export type ListenMapProgress = {
  capturedInput: boolean;
  mappedGloss: boolean;
  playedSequence: boolean;
  playedSpeech: boolean;
};

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

export function SpeechToKslStudio({
  onLessonReady,
  onProgressChange,
  onOpenSignStudio,
  onOpenPhotoStudio,
}: {
  onLessonReady?: () => void;
  onProgressChange?: (progress: ListenMapProgress) => void;
  onOpenSignStudio?: () => void;
  onOpenPhotoStudio?: () => void;
}) {
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
  const lastTimestampRef = useRef<number | null>(null);
  const playheadMsRef = useRef(0);
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
      if (speechPlaybackUrl) {
        URL.revokeObjectURL(speechPlaybackUrl);
      }
      mediaRecorderRef.current?.stop();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [speechPlaybackUrl]);

  useEffect(() => {
    if (backendMapping?.lesson_assets.length || transcript.trim()) {
      onLessonReady?.();
    }
  }, [backendMapping, onLessonReady, transcript]);

  useEffect(() => {
    onProgressChange?.({
      capturedInput: Boolean(transcript.trim()),
      mappedGloss: Boolean(backendMapping?.gloss.length),
      playedSequence:
        Boolean(backendLessons.length) &&
        (!isBackendSequencePlaying
          ? activeLessonIndex > 0
          : false),
      playedSpeech: Boolean(speechPlaybackUrl),
    });
  }, [
    activeLessonIndex,
    backendLessons.length,
    backendMapping?.gloss.length,
    isBackendSequencePlaying,
    onProgressChange,
    speechPlaybackUrl,
    transcript,
  ]);

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

  const isBusy = status === "processing";
  const isListening = status === "listening";
  const hasSpeechInput = Boolean((transcript || interimTranscript).trim());
  const glossPlaceholder = hasSpeechInput ? ["Waiting for KSL"] : [];
  const glossTokens = gloss.length ? gloss : glossPlaceholder;
  const backendStatusSummary = backendMapping
    ? `${backendMapping.status.toUpperCase()} · ${backendLessons.length} lesson assets`
    : "Waiting for backend mapping";

  const showVoiceAnimation = isBusy;
  const showTranscript = status === "ready" && Boolean(transcript.trim());
  const shouldShowReadout = showVoiceAnimation || showTranscript || Boolean(recordingHint);
  const shouldShowGloss = glossTokens.length > 0;

  return (
    <section className="voice-shell lesson-hero-shell">
      <section className="voice-layout" aria-labelledby="voice-title">
        <div className="voice-copy">
          <div className="lesson-headline">
            <h1 id="voice-title">Learn KSL</h1>
            <p className="voice-subtitle">
              Speak or type, map it to gloss, then preview the signed sequence.
            </p>
          </div>
          {shouldShowReadout ? (
            <div className="voice-readout" aria-live="polite">
              <span className="voice-label">Live input</span>
              {showVoiceAnimation ? (
                <div className="voice-thinking" role="status" aria-label="Thinking indicator">
                  <span className="voice-thinking-label">Preparing</span>
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
                <p>{showTranscript ? transcript : recordingHint}</p>
              )}
            </div>
          ) : null}

          {shouldShowGloss ? (
            <div className="gloss-row" aria-label="KSL gloss output">
              {glossTokens.map((token, index) => (
                <span key={`${token}-${index}`} className={gloss.length ? "is-live" : ""}>
                  {token}
                </span>
              ))}
            </div>
          ) : null}

          <div className="voice-controls" aria-label="Speech controls">
            <form className="manual-input manual-input-chat" onSubmit={submitManual}>
              <input
                value={manualInput}
                onChange={(event) => setManualInput(event.target.value)}
                placeholder="Type a phrase"
                aria-label="Manual text input"
              />
              <div className="composer-actions">
                <button
                  type="button"
                  className={`composer-icon-button composer-record-button${isListening ? " is-active" : ""}`}
                  onClick={isListening ? stopListening : startListening}
                  disabled={isBusy}
                  title={isListening ? "Stop recording" : "Start microphone recording"}
                  aria-label={isListening ? "Stop recording" : "Record speech"}
                >
                  {isListening ? <Square aria-hidden="true" /> : <Mic aria-hidden="true" />}
                </button>
                <button
                  type="button"
                  className="composer-icon-button"
                  onClick={onOpenSignStudio}
                  title="Open sign upload"
                  aria-label="Open sign upload"
                >
                  <Hand aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="composer-icon-button"
                  onClick={onOpenPhotoStudio}
                  title="Open image explain"
                  aria-label="Open image explain"
                >
                  <ImagePlus aria-hidden="true" />
                </button>
                <button
                  type="submit"
                  className="composer-send-button"
                  disabled={isBusy || !manualInput.trim()}
                  aria-label="Map typed text"
                  title="Map typed text"
                >
                  <Send aria-hidden="true" />
                </button>
              </div>
            </form>
            <div className="composer-helper">
              <span>
                {isListening
                  ? "Recording live. Tap the square to stop."
                  : "Type, record, or jump to sign and image upload."}
              </span>
            </div>
          </div>

          <div className="backend-proof">
            <div className="backend-proof-header">
              <div className="backend-proof-copy">
                <span className="voice-label">Playback</span>
                <p>Listen back or step through the mapped signs.</p>
              </div>
              <div className="backend-proof-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void speakTranscript()}
                  disabled={isBusy || isSpeechGenerating || !transcript.trim()}
                >
                  <Volume2 aria-hidden="true" />
                  <span>{isSpeechGenerating ? "Generating..." : "Speak"}</span>
                </button>
                <button
                  type="button"
                  className="primary-button secondary-surface"
                  onClick={handleBackendSequenceRestart}
                  disabled={!backendLessons.length}
                >
                  <Play aria-hidden="true" />
                  <span>{isBackendSequencePlaying ? "Playing" : "Play signs"}</span>
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
          <div className="stickman-panel">
            <div className="stickman-copy">
              <strong>{activeLesson?.label ?? "No lesson selected"}</strong>
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
                </div>
              )}
            </div>
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

         
        </div>
      </section>
    </section>
  );
}
