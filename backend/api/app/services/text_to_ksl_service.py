from ..schemas.requests import TextToKslRequest
from ..schemas.responses import TextToKslResponse


def map_text_to_ksl(request: TextToKslRequest) -> TextToKslResponse:
    gloss = [token.upper() for token in request.text.split()[:5]]
    return TextToKslResponse(
        gloss=gloss,
        lesson_asset_id=None,
        status="stub",
    )
