import { Mic, RotateCcw, Send, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { textToKsl } from "../../api/kslClient";
import type { LandmarkFrame, SignLandmarkClip } from "../../types/landmarks";
import { ThreeAvatarPlayer } from "../lesson-player/ThreeAvatarPlayer";
import loveClipData from "../lesson-player/data/love.sign.json";
import { getInterpolatedFrame } from "../lesson-player/landmarkPlayback";

type StudioStatus = "idle" | "listening" | "processing" | "ready" | "error";

type SpeechRecognitionCtor = new () => {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
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

function resolveClipFromGloss(gloss: string[]) {
  for (const token of normalizeTokens(gloss)) {
    const clip = LOCAL_CLIP_LIBRARY[token];
    if (clip) {
      return clip;
    }
  }
  return null;
}

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") {
    return null;
  }

  const maybeWindow = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };

  return maybeWindow.SpeechRecognition ?? maybeWindow.webkitSpeechRecognition ?? null;
}

export function SpeechToKslStudio() {
  const [status, setStatus] = useState<StudioStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [manualInput, setManualInput] = useState("");
  const [gloss, setGloss] = useState<string[]>([]);

  const [clip, setClip] = useState<SignLandmarkClip | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasPlaybackBegun, setHasPlaybackBegun] = useState(false);
  const [framePosition, setFramePosition] = useState(0);
  const [avatarRefreshKey, setAvatarRefreshKey] = useState(0);

  const recognitionRef = useRef<InstanceType<SpeechRecognitionCtor> | null>(null);
  const animationRef = useRef<number | null>(null);
  const thinkingPreviewTimeoutRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const playheadMsRef = useRef(0);
  const [isThinkingPreview, setIsThinkingPreview] = useState(false);

  const activeClip = clip ?? FALLBACK_CLIP;
  const hasResolvedClip = Boolean(clip);

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
    };
  }, []);

  const runPipeline = useCallback(async (text: string) => {
    const normalizedText = text.trim();
    if (!normalizedText) {
      return;
    }

    setStatus("processing");
    setErrorMessage(null);
    setTranscript(normalizedText);
    setInterimTranscript("");

    try {
      const mapped = await textToKsl({ text: normalizedText });
      const nextGloss = normalizeTokens(mapped.gloss);
      setGloss(nextGloss);

      const matchedClip = resolveClipFromGloss(nextGloss);
      if (!matchedClip) {
        setClip(null);
        setStatus("error");
        setErrorMessage(
          "No local animation asset was found for this gloss yet. Backend can return a lesson asset id to map this automatically.",
        );
        resetPlayback();
        return;
      }

      setClip(matchedClip);
      setStatus("ready");
      startPlayback();
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Could not map text to KSL.");
      resetPlayback();
    }
  }, [resetPlayback, startPlayback]);

  const startListening = useCallback(() => {
    const RecognitionCtor = getSpeechRecognitionCtor();
    if (!RecognitionCtor) {
      setStatus("error");
      setErrorMessage("Speech recognition is not supported in this browser. Use the text box below.");
      return;
    }

    const recognition = new RecognitionCtor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-KE";

    recognition.onstart = () => {
      setStatus("listening");
      setErrorMessage(null);
      setInterimTranscript("");
    };

    recognition.onresult = (event: any) => {
      let finalText = "";
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalText += text;
        } else {
          interim += text;
        }
      }

      if (interim) {
        setInterimTranscript(interim.trim());
      }

      if (finalText.trim()) {
        setInterimTranscript("");
        void runPipeline(finalText);
      }
    };

    recognition.onerror = (event: any) => {
      setStatus("error");
      setErrorMessage(event?.error ? `Speech error: ${event.error}` : "Speech recognition failed.");
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setStatus((current) => (current === "listening" ? "idle" : current));
      setInterimTranscript("");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [runPipeline]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setStatus((current) => (current === "listening" ? "idle" : current));
    setInterimTranscript("");
  }, []);

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

  const showVoiceAnimation = isBusy || isThinkingPreview;
  const showTranscript = !isThinkingPreview && status === "ready" && Boolean(transcript.trim());

  return (
    <main className="voice-shell">
      <section className="voice-layout" aria-labelledby="voice-title">
        <div className="voice-copy">
          <p className="voice-kicker">Tutoria</p>
          <h1 id="voice-title">Speak naturally. See KSL instantly.</h1>
          <p className="voice-subtitle">
            This frontend is designed for easy backend integration. Audio input becomes transcript,
            transcript maps to KSL gloss, and gloss resolves to signer animation.
          </p>

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
              <p>{showTranscript ? transcript : ""}</p>
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
              title={isListening ? "Stop listening" : "Start listening"}
            >
              {isListening ? <Square aria-hidden="true" /> : <Mic aria-hidden="true" />}
              <span>{isListening ? "Listening... tap to stop" : "Tap to speak"}</span>
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
        </div>
      </section>
    </main>
  );
}
