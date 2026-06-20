# Service Layer

Keep business logic here, not inside route handlers.

Suggested modules:

- `speech_service.py`
- `text_to_ksl_service.py`
- `sign_to_text_service.py`
- `photo_explain_service.py`

Each service should hide model-specific details from the API layer.
