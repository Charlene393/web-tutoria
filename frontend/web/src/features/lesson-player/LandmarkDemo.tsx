import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { SignLandmarkClip } from "../../types/landmarks";
import loveClipData from "./data/love.sign.json";
import { getInterpolatedFrame } from "./landmarkPlayback";
import { ThreeAvatarPlayer } from "./ThreeAvatarPlayer";

const loveClip = loveClipData as unknown as SignLandmarkClip;
const END_HOLD_MS = 420;

export function LandmarkDemo() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasPlaybackBegun, setHasPlaybackBegun] = useState(false);
  const [framePosition, setFramePosition] = useState(0);
  const animationRef = useRef<number | null>(null);
  const lastTimestampRef = useRef<number | null>(null);
  const playheadMsRef = useRef(0);

  const totalFrames = loveClip.frames.length;
  const frameDuration = 1000 / loveClip.fps;
  const clipDuration = (totalFrames - 1) * frameDuration;
  const cycleDuration = clipDuration + END_HOLD_MS;

  const reset = useCallback(() => {
    setFramePosition(0);
    setIsPlaying(false);
    setHasPlaybackBegun(false);
    playheadMsRef.current = 0;
    lastTimestampRef.current = null;
  }, []);

  const togglePlayback = useCallback(() => {
    setIsPlaying((current) => {
      const next = !current;
      if (next) {
        setHasPlaybackBegun(true);
      }
      return next;
    });
  }, []);

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

  const visibleFrame = Math.min(Math.floor(framePosition) + 1, totalFrames);
  const progress = Math.min(framePosition / (totalFrames - 1), 1) * 100;
  const currentFrame = getInterpolatedFrame(loveClip, framePosition);

  return (
    <main className="app-shell">
      <section className="workspace" aria-labelledby="demo-title">
        <div className="workspace-copy">
          <p className="eyebrow">KSL 3D avatar rig</p>
          <h1 id="demo-title">LOVE Motion Test</h1>
          <div className="sign-meta" aria-label="Selected sign">
            <span>{loveClip.label}</span>
            <span>{totalFrames} frames</span>
            <span>{loveClip.fps} fps</span>
            <span>VRM ready</span>
          </div>
        </div>

        <div className="player-shell">
          <div className="stage-toolbar" aria-label="Animation controls">
            <button
              className="primary-button"
              type="button"
              onClick={togglePlayback}
              title={isPlaying ? "Pause animation" : "Play animation"}
            >
              {isPlaying ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
              <span>{isPlaying ? "Pause" : "Play LOVE"}</span>
            </button>
            <button
              className="icon-button"
              type="button"
              onClick={reset}
              title="Reset animation"
              aria-label="Reset animation"
            >
              <RotateCcw aria-hidden="true" />
            </button>
          </div>

          <ThreeAvatarPlayer
            frame={currentFrame}
            isPlaying={isPlaying}
            hasPlaybackBegun={hasPlaybackBegun}
          />

          <div className="timeline" aria-label="Animation progress">
            <div className="timeline-track">
              <div className="timeline-fill" style={{ width: `${progress}%` }} />
            </div>
            <span>
              {visibleFrame}/{totalFrames}
            </span>
          </div>
        </div>
      </section>
    </main>
  );
}
