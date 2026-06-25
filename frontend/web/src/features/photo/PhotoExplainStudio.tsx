import { ImagePlus, Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";
import { photoExplainUpload, type PhotoExplainResponse } from "../../api/kslClient";

function decodeAudioToUrl(audioBase64: string, contentType: string) {
  const binary = window.atob(audioBase64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return URL.createObjectURL(new Blob([bytes], { type: contentType }));
}

export function PhotoExplainStudio({
  onComplete,
}: {
  onComplete?: () => void;
}) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [objectName, setObjectName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<PhotoExplainResponse | null>(null);
  const [speechUrl, setSpeechUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (speechUrl) {
        URL.revokeObjectURL(speechUrl);
      }
    };
  }, [speechUrl]);

  useEffect(() => {
    if (result) {
      onComplete?.();
    }
  }, [onComplete, result]);

  async function handleSubmit() {
    if (!imageFile) {
      return;
    }

    if (speechUrl) {
      URL.revokeObjectURL(speechUrl);
      setSpeechUrl(null);
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setResult(null);

    try {
      const payload = await photoExplainUpload({
        imageFile,
        objectName,
        prompt,
        includeKsl: true,
        includeSpeech: true,
      });
      setResult(payload);

      if (payload.speech?.audio_base64 && payload.speech.content_type) {
        setSpeechUrl(decodeAudioToUrl(payload.speech.audio_base64, payload.speech.content_type));
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Could not explain this image.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <p className="workspace-kicker">Photo Explain</p>
          <h2>Upload an object photo and turn it into a teachable lesson.</h2>
        </div>
      </div>

      <div className="workspace-grid">
        <article className="workspace-card">
          <label className="upload-dropzone">
            <input
              type="file"
              accept="image/*"
              onChange={(event) => {
                setImageFile(event.target.files?.[0] ?? null);
              }}
            />
            <ImagePlus size={20} />
            <strong>{imageFile?.name ?? "Choose an image"}</strong>
            <span>Upload something a learner wants explained and signed.</span>
          </label>

          <label className="workspace-field">
            <span>Object name</span>
            <input
              value={objectName}
              onChange={(event) => setObjectName(event.target.value)}
              placeholder="Optional, for example: apple"
            />
          </label>

          <label className="workspace-field">
            <span>Teaching prompt</span>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Optional, for example: explain this for a 10-year-old learner"
              rows={4}
            />
          </label>

          <button
            type="button"
            className="action-button"
            disabled={!imageFile || isSubmitting}
            onClick={() => {
              void handleSubmit();
            }}
          >
            {isSubmitting ? "Explaining photo..." : "Explain photo"}
          </button>

          {errorMessage ? <p className="inline-error">{errorMessage}</p> : null}
        </article>

        <article className="workspace-card workspace-card-emphasis">
          <div className="result-headline">
            <Lightbulb size={18} />
            <strong>Learning output</strong>
          </div>

          {result ? (
            <div className="result-stack">
              <div className="metric-grid">
                <div>
                  <span>Object</span>
                  <strong>{result.object_name ?? "Unknown"}</strong>
                </div>
                <div>
                  <span>Suggested sign</span>
                  <strong>{result.suggested_sign ?? "Not provided"}</strong>
                </div>
              </div>

              <p className="result-copy">{result.explanation}</p>

              {result.text_to_ksl?.gloss?.length ? (
                <div className="gloss-row">
                  {result.text_to_ksl.gloss.map((gloss) => (
                    <span key={gloss}>{gloss}</span>
                  ))}
                </div>
              ) : null}

              {speechUrl ? <audio controls src={speechUrl} className="workspace-audio" /> : null}
            </div>
          ) : (
            <p className="result-placeholder">
              The backend will explain the object, suggest the sign to teach, and return any
              glossary-backed lesson mapping.
            </p>
          )}
        </article>
      </div>
    </section>
  );
}
