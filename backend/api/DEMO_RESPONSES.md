# Backend Demo Responses

Use this file as the current backend contract reference for frontend work.

It gives you:

- one approved example request per stable endpoint
- one approved example response shape per stable endpoint
- the main fields the frontend should rely on

Important:

- audio fields like `audio_base64` are shortened here on purpose
- file upload endpoints are shown as `curl` examples plus JSON response bodies
- these examples are contract-oriented, not full raw payload dumps

## 1. `GET /api/v1/health`

Request:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Response:

```json
{
  "status": "ok",
  "app_name": "Web Tutoria API",
  "app_version": "0.1.0",
  "checks": {
    "lesson_catalog": {
      "ready": true,
      "required": true,
      "path": "app/data/ksl_lesson_catalog.json",
      "detail": null
    },
    "cleaned_manifest": {
      "ready": true,
      "required": true,
      "path": "backend/reports/ksl_cleanup/cleaned_sign_manifest.csv",
      "detail": null
    },
    "sign_recognizer_artifact": {
      "ready": true,
      "required": false,
      "path": "backend/models/ksl_sign_v1_recognizer.npz",
      "detail": null
    },
    "sign_label_set": {
      "ready": true,
      "required": true,
      "path": "app/data/ksl_sign_v1_labels.json",
      "detail": null
    },
    "kokoro": {
      "ready": true,
      "required": true,
      "path": null,
      "detail": null
    },
    "faster_whisper": {
      "ready": true,
      "required": true,
      "path": null,
      "detail": null
    }
  }
}
```

Frontend-safe fields:

- `status`
- `app_name`
- `app_version`
- `checks`

## 2. `POST /api/v1/text-to-ksl`

Request:

```json
{
  "text": "I want food"
}
```

Response:

```json
{
  "original_text": "I want food",
  "normalized_text": "i want food",
  "gloss": ["ME", "WANT", "FOOD"],
  "matched_terms": ["i want food"],
  "unmatched_terms": [],
  "supported": true,
  "dataset_backed": true,
  "dataset_label_counts": {
    "ME": 30,
    "WANT": 5,
    "FOOD": 6
  },
  "lesson_assets": [
    {
      "asset_id": "lesson-sign:me",
      "label": "ME",
      "sample_count": 30,
      "source": "cleaned_lesson_catalog",
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "stickman_video_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Stickmans/ME.mp4",
      "batch": "Batch 2",
      "signer_id": "65",
      "frame_count": 31,
      "sample_flags": [],
      "quality_score": 160.85,
      "selected_from_flagged_sample": false
    },
    {
      "asset_id": "lesson-sign:want",
      "label": "WANT",
      "sample_count": 5,
      "source": "cleaned_lesson_catalog",
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy",
      "stickman_video_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Stickmans/WANT.mp4",
      "batch": "Batch 2",
      "signer_id": "76",
      "frame_count": 29,
      "sample_flags": [],
      "quality_score": 160.15,
      "selected_from_flagged_sample": false
    },
    {
      "asset_id": "lesson-sign:food",
      "label": "FOOD",
      "sample_count": 6,
      "source": "cleaned_lesson_catalog",
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy",
      "stickman_video_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Stickmans/FOOD.mp4",
      "batch": "Batch 2",
      "signer_id": "162",
      "frame_count": 37,
      "sample_flags": [],
      "quality_score": 160.52,
      "selected_from_flagged_sample": false
    }
  ],
  "lesson_asset_id": "dataset-sequence:me__want__food",
  "catalog_backed": true,
  "catalog_name": "ksl_cleaned_lesson_catalog",
  "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
  "status": "ok"
}
```

Frontend-safe fields:

- `gloss`
- `lesson_assets`
- `lesson_asset_id`
- `status`

## 3. `POST /api/v1/text-to-speech`

Request:

```json
{
  "text": "I want food",
  "include_ksl": true
}
```

Response:

```json
{
  "text": "I want food",
  "audio_base64": "<base64-audio-truncated>",
  "audio_size_bytes": 76844,
  "content_type": "audio/wav",
  "file_extension": "wav",
  "provider": "kokoro",
  "model_id": "Kokoro-82M",
  "voice_id": "af_heart",
  "output_format": "wav_24000",
  "text_to_ksl": {
    "original_text": "I want food",
    "normalized_text": "i want food",
    "gloss": ["ME", "WANT", "FOOD"],
    "matched_terms": ["i want food"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "ME": 30,
      "WANT": 5,
      "FOOD": 6
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:me__want__food",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "status": "ok"
}
```

Frontend-safe fields:

- `audio_base64`
- `content_type`
- `voice_id`
- `text_to_ksl`
- `status`

## 4. `POST /api/v1/speech-to-text`

Request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/speech-to-text \
  -F "audio=@/absolute/path/to/real-audio-file.m4a" \
  -F "include_ksl=true"
```

Response:

```json
{
  "transcript": "I want food",
  "confidence": null,
  "provider": "faster_whisper",
  "model_id": "small",
  "detected_language": "en",
  "text_to_ksl": {
    "original_text": "I want food",
    "normalized_text": "i want food",
    "gloss": ["ME", "WANT", "FOOD"],
    "matched_terms": ["i want food"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "ME": 30,
      "WANT": 5,
      "FOOD": 6
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:me__want__food",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "status": "ok"
}
```

Frontend-safe fields:

- `transcript`
- `detected_language`
- `text_to_ksl`
- `status`

## 5. `POST /api/v1/sign-to-text`

Request:

```json
{
  "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
  "top_k": 3
}
```

Response:

```json
{
  "label": "ME",
  "confidence": 1.0,
  "text": "ME",
  "provider": "dataset_knn",
  "model_id": "dataset-sign-knn-v1",
  "source_kind": "landmark_path",
  "source_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
  "source_upload_filename": null,
  "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
  "extracted_frame_count": null,
  "lesson_asset_id": "lesson-sign:me",
  "dataset_backed": true,
  "top_matches": [
    {
      "label": "ME",
      "confidence": 1.0,
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "lesson_asset_id": "lesson-sign:me"
    },
    {
      "label": "HER",
      "confidence": 0.9889,
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/HER.npy",
      "lesson_asset_id": "lesson-sign:her"
    },
    {
      "label": "THIS",
      "confidence": 0.9888,
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/119/Extract/Landmarks/THIS.npy",
      "lesson_asset_id": "lesson-sign:this"
    }
  ],
  "speech": null,
  "status": "ok"
}
```

Frontend-safe fields:

- `label`
- `confidence`
- `top_matches`
- `lesson_asset_id`
- `status`

## 6. `POST /api/v1/sign-to-text-upload`

Request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-to-text-upload \
  -F "sign_file=@KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" \
  -F "include_speech=true" \
  -F "top_k=3"
```

Response:

```json
{
  "label": "ME",
  "confidence": 1.0,
  "text": "ME",
  "provider": "dataset_knn",
  "model_id": "dataset-sign-knn-v1",
  "source_kind": "uploaded_landmark_file",
  "source_landmark_path": null,
  "source_upload_filename": "ME.npy",
  "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
  "extracted_frame_count": 31,
  "lesson_asset_id": "lesson-sign:me",
  "dataset_backed": true,
  "top_matches": [
    {
      "label": "ME",
      "confidence": 1.0,
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "lesson_asset_id": "lesson-sign:me"
    },
    {
      "label": "HER",
      "confidence": 0.9889,
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/HER.npy",
      "lesson_asset_id": "lesson-sign:her"
    }
  ],
  "speech": {
    "text": "ME",
    "audio_base64": "<base64-audio-truncated>",
    "audio_size_bytes": 60044,
    "content_type": "audio/wav",
    "file_extension": "wav",
    "provider": "kokoro",
    "model_id": "Kokoro-82M",
    "voice_id": "af_heart",
    "output_format": "wav_24000",
    "text_to_ksl": null,
    "status": "ok"
  },
  "status": "ok"
}
```

Frontend-safe fields:

- `label`
- `source_kind`
- `source_upload_filename`
- `speech`
- `status`

## 7. `POST /api/v1/sign-sequence-to-text`

Request:

```json
{
  "items": [
    {
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy"
    },
    {
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy"
    },
    {
      "landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy"
    }
  ],
  "top_k": 3,
  "include_ksl": true
}
```

Response:

```json
{
  "text": "ME WANT FOOD",
  "normalized_text": "me want food",
  "sign_count": 3,
  "items": [
    {
      "index": 0,
      "label": "ME",
      "confidence": 1.0,
      "text": "ME",
      "source_kind": "landmark_path",
      "source_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "lesson_asset_id": "lesson-sign:me",
      "top_matches": [],
      "status": "ok"
    },
    {
      "index": 1,
      "label": "WANT",
      "confidence": 1.0,
      "text": "WANT",
      "source_kind": "landmark_path",
      "source_landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy",
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy",
      "lesson_asset_id": "lesson-sign:want",
      "top_matches": [],
      "status": "ok"
    },
    {
      "index": 2,
      "label": "FOOD",
      "confidence": 1.0,
      "text": "FOOD",
      "source_kind": "landmark_path",
      "source_landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy",
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy",
      "lesson_asset_id": "lesson-sign:food",
      "top_matches": [],
      "status": "ok"
    }
  ],
  "provider": "dataset_knn",
  "model_id": "dataset-sign-sequence-v1",
  "text_to_ksl": {
    "original_text": "ME WANT FOOD",
    "normalized_text": "me want food",
    "gloss": ["ME", "WANT", "FOOD"],
    "matched_terms": ["me", "want", "food"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "ME": 30,
      "WANT": 5,
      "FOOD": 6
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:me__want__food",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "speech": null,
  "status": "ok"
}
```

Frontend-safe fields:

- `text`
- `sign_count`
- `items`
- `text_to_ksl`
- `status`

## 8. `POST /api/v1/sign-sequence-to-text-upload`

Request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/sign-sequence-to-text-upload \
  -F "sign_files=@KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy" \
  -F "sign_files=@KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy" \
  -F "sign_files=@KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy" \
  -F "include_ksl=true" \
  -F "include_speech=true"
```

Response:

```json
{
  "text": "ME WANT FOOD",
  "normalized_text": "me want food",
  "sign_count": 3,
  "items": [
    {
      "index": 0,
      "label": "ME",
      "confidence": 1.0,
      "text": "ME",
      "source_kind": "uploaded_landmark_file",
      "source_landmark_path": null,
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/65/Extract/Landmarks/ME.npy",
      "lesson_asset_id": "lesson-sign:me",
      "top_matches": [],
      "status": "ok"
    },
    {
      "index": 1,
      "label": "WANT",
      "confidence": 1.0,
      "text": "WANT",
      "source_kind": "uploaded_landmark_file",
      "source_landmark_path": null,
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/76/Extract/Landmarks/WANT.npy",
      "lesson_asset_id": "lesson-sign:want",
      "top_matches": [],
      "status": "ok"
    },
    {
      "index": 2,
      "label": "FOOD",
      "confidence": 1.0,
      "text": "FOOD",
      "source_kind": "uploaded_landmark_file",
      "source_landmark_path": null,
      "matched_landmark_path": "KSL-Dataset/Pose Data/Batch 2/162/Extract/Landmarks/FOOD.npy",
      "lesson_asset_id": "lesson-sign:food",
      "top_matches": [],
      "status": "ok"
    }
  ],
  "provider": "dataset_knn",
  "model_id": "dataset-sign-sequence-v1",
  "text_to_ksl": {
    "original_text": "ME WANT FOOD",
    "normalized_text": "me want food",
    "gloss": ["ME", "WANT", "FOOD"],
    "matched_terms": ["me", "want", "food"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "ME": 30,
      "WANT": 5,
      "FOOD": 6
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:me__want__food",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "speech": {
    "text": "ME WANT FOOD",
    "audio_base64": "<base64-audio-truncated>",
    "audio_size_bytes": 80444,
    "content_type": "audio/wav",
    "file_extension": "wav",
    "provider": "kokoro",
    "model_id": "Kokoro-82M",
    "voice_id": "af_heart",
    "output_format": "wav_24000",
    "text_to_ksl": null,
    "status": "ok"
  },
  "status": "ok"
}
```

Frontend-safe fields:

- `text`
- `items`
- `speech`
- `text_to_ksl`
- `status`

## 9. `POST /api/v1/photo-explain`

Request:

```json
{
  "object_name": "car",
  "include_ksl": true
}
```

Response:

```json
{
  "object_name": "car",
  "normalized_object_name": "car",
  "explanation": "This is a car. A car is used for transport on the road.",
  "suggested_sign": "CAR",
  "provider": "filename_or_prompt_v1",
  "source_kind": "json_request",
  "source_image_filename": null,
  "text_to_ksl": {
    "original_text": "car",
    "normalized_text": "car",
    "gloss": ["CAR"],
    "matched_terms": ["car"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "CAR": 5
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:car",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "speech": null,
  "status": "ok"
}
```

Frontend-safe fields:

- `object_name`
- `explanation`
- `suggested_sign`
- `text_to_ksl`
- `status`

## 10. `POST /api/v1/photo-explain-upload`

Request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/photo-explain-upload \
  -F "image=@/absolute/path/to/car.jpg" \
  -F "object_name=car" \
  -F "include_ksl=true" \
  -F "include_speech=true"
```

Response:

```json
{
  "object_name": "car",
  "normalized_object_name": "car",
  "explanation": "This is a car. A car is used for transport on the road.",
  "suggested_sign": "CAR",
  "provider": "filename_or_prompt_v1",
  "source_kind": "uploaded_image",
  "source_image_filename": "car.jpg",
  "text_to_ksl": {
    "original_text": "car",
    "normalized_text": "car",
    "gloss": ["CAR"],
    "matched_terms": ["car"],
    "unmatched_terms": [],
    "supported": true,
    "dataset_backed": true,
    "dataset_label_counts": {
      "CAR": 5
    },
    "lesson_assets": [],
    "lesson_asset_id": "dataset-sequence:car",
    "catalog_backed": true,
    "catalog_name": "ksl_cleaned_lesson_catalog",
    "catalog_generated_at": "2026-06-21T06:39:33.826216+00:00",
    "status": "ok"
  },
  "speech": {
    "text": "This is a car. A car is used for transport on the road.",
    "audio_base64": "<base64-audio-truncated>",
    "audio_size_bytes": 70244,
    "content_type": "audio/wav",
    "file_extension": "wav",
    "provider": "kokoro",
    "model_id": "Kokoro-82M",
    "voice_id": "af_heart",
    "output_format": "wav_24000",
    "text_to_ksl": null,
    "status": "ok"
  },
  "status": "ok"
}
```

Frontend-safe fields:

- `object_name`
- `source_image_filename`
- `explanation`
- `speech`
- `status`

## Frontend integration note

If you are starting the frontend next, the most important response fields to standardize around are:

- `status`
- `text_to_ksl`
- `lesson_asset_id`
- `lesson_assets`
- `speech.audio_base64`
- `speech.content_type`

For v1 frontend work, treat these flows as the safest:

- text to KSL
- text to speech
- speech to text
- sign to text using `.npy`
- sign sequence using `.npy`
- photo explain using explicit `object_name`

Treat raw sign-video extraction on macOS as optional for now.
