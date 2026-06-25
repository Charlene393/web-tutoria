import { Upload, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  signSequenceToTextUpload,
  signToTextUpload,
  type SignSequenceToTextResponse,
  type SignToTextResponse,
} from "../../api/kslClient";

type UploadMode = "single" | "sequence";

function decodeAudioToUrl(audioBase64: string, contentType: string) {
  const binary = window.atob(audioBase64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return URL.createObjectURL(new Blob([bytes], { type: contentType }));
}

export function SignUploadStudio({
  onComplete,
}: {
  onComplete?: () => void;
}) {
  const [mode, setMode] = useState<UploadMode>("single");
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [sequenceFiles, setSequenceFiles] = useState<File[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [singleResult, setSingleResult] = useState<SignToTextResponse | null>(null);
  const [sequenceResult, setSequenceResult] = useState<SignSequenceToTextResponse | null>(null);
  const [speechUrl, setSpeechUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (speechUrl) {
        URL.revokeObjectURL(speechUrl);
      }
    };
  }, [speechUrl]);

  useEffect(() => {
    if (singleResult || sequenceResult) {
      onComplete?.();
    }
  }, [onComplete, sequenceResult, singleResult]);

  const canSubmit = useMemo(() => {
    return mode === "single" ? Boolean(singleFile) : sequenceFiles.length > 0;
  }, [mode, sequenceFiles.length, singleFile]);

  async function handleSubmit() {
    setErrorMessage(null);
    setIsSubmitting(true);
    setSingleResult(null);
    setSequenceResult(null);

    if (speechUrl) {
      URL.revokeObjectURL(speechUrl);
      setSpeechUrl(null);
    }

    try {
      if (mode === "single" && singleFile) {
        const result = await signToTextUpload({
          signFile: singleFile,
          filename: singleFile.name,
          includeSpeech: true,
        });
        setSingleResult(result);

        if (result.speech?.audio_base64 && result.speech.content_type) {
          setSpeechUrl(decodeAudioToUrl(result.speech.audio_base64, result.speech.content_type));
        }
      }

      if (mode === "sequence" && sequenceFiles.length > 0) {
        const result = await signSequenceToTextUpload({
          signFiles: sequenceFiles,
          includeKsl: true,
          includeSpeech: true,
        });
        setSequenceResult(result);

        if (result.speech?.audio_base64 && result.speech.content_type) {
          setSpeechUrl(decodeAudioToUrl(result.speech.audio_base64, result.speech.content_type));
        }
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not process the sign upload.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <p className="workspace-kicker">Sign Upload Check</p>
          <h2>Upload one sign or a full sign sequence.</h2>
        </div>
        <div className="studio-pill-group">
          <button
            type="button"
            className={mode === "single" ? "studio-pill is-active" : "studio-pill"}
            onClick={() => setMode("single")}
          >
            Single sign
          </button>
          <button
            type="button"
            className={mode === "sequence" ? "studio-pill is-active" : "studio-pill"}
            onClick={() => setMode("sequence")}
          >
            Sequence
          </button>
        </div>
      </div>

      <div className="workspace-grid workspace-grid-tight">
        <article className="workspace-card">
          <label className="upload-dropzone">
            <input
              type="file"
              accept={mode === "single" ? ".npy,video/*" : ".npy,video/*"}
              multiple={mode === "sequence"}
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (mode === "single") {
                  setSingleFile(files[0] ?? null);
                } else {
                  setSequenceFiles(files);
                }
              }}
            />
            <Upload size={20} />
            <strong>
              {mode === "single"
                ? singleFile?.name ?? "Choose one sign file"
                : sequenceFiles.length
                  ? `${sequenceFiles.length} sign files selected`
                  : "Choose multiple sign files"}
            </strong>
            <span>
              Works best with dataset-backed `.npy` landmark files. Short sign videos can also be
              tested where extraction is supported.
            </span>
          </label>

          <button
            type="button"
            className="action-button"
            disabled={!canSubmit || isSubmitting}
            onClick={() => {
              void handleSubmit();
            }}
          >
            {isSubmitting ? "Checking sign..." : "Run sign check"}
          </button>

          {errorMessage ? <p className="inline-error">{errorMessage}</p> : null}
        </article>

        <article className="workspace-card">
          <div className="result-stack">
            <div className="result-headline">
              <Sparkles size={18} />
              <strong>Backend reading</strong>
            </div>

            {mode === "single" && singleResult ? (
              <>
                <div className="metric-grid">
                  <div>
                    <span>Label</span>
                    <strong>{singleResult.label ?? "Unknown"}</strong>
                  </div>
                  <div>
                    <span>Confidence</span>
                    <strong>
                      {typeof singleResult.confidence === "number"
                        ? `${(singleResult.confidence * 100).toFixed(1)}%`
                        : "N/A"}
                    </strong>
                  </div>
                </div>
                <p className="result-copy">
                  Text output: <strong>{singleResult.text ?? "None"}</strong>
                </p>
                <div className="gloss-row">
                  {singleResult.top_matches.map((match) => (
                    <span key={`${match.label}-${match.landmark_path ?? "candidate"}`}>
                      {match.label}
                    </span>
                  ))}
                </div>
              </>
            ) : null}

            {mode === "sequence" && sequenceResult ? (
              <>
                <div className="metric-grid">
                  <div>
                    <span>Sequence text</span>
                    <strong>{sequenceResult.text || "No text yet"}</strong>
                  </div>
                  <div>
                    <span>Sign count</span>
                    <strong>{sequenceResult.sign_count}</strong>
                  </div>
                </div>
                <div className="gloss-row">
                  {(sequenceResult.text_to_ksl?.gloss ?? []).map((gloss) => (
                    <span key={gloss}>{gloss}</span>
                  ))}
                </div>
                <div className="result-list">
                  {sequenceResult.items.map((item) => (
                    <div className="result-list-item" key={`${item.index}-${item.label ?? "unknown"}`}>
                      <strong>
                        {item.index + 1}. {item.label ?? "Unknown"}
                      </strong>
                      <span>{item.text ?? "No text"}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : null}

            {!singleResult && !sequenceResult ? (
              <p className="result-placeholder">
                Upload a sign sample and the backend will return label confidence, text output, and
                sequence interpretation.
              </p>
            ) : null}

            {speechUrl ? <audio controls src={speechUrl} className="workspace-audio" /> : null}
          </div>
        </article>
      </div>
    </section>
  );
}
