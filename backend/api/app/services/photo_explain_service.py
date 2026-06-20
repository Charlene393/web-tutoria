from ..schemas.requests import PhotoExplainRequest
from ..schemas.responses import PhotoExplainResponse


def explain_photo(_: PhotoExplainRequest) -> PhotoExplainResponse:
    return PhotoExplainResponse(
        object_name=None,
        explanation="Photo explanation pipeline not connected yet.",
        suggested_sign=None,
        status="stub",
    )
