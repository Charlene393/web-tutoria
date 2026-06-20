from ..schemas.requests import SignToTextRequest
from ..schemas.responses import SignToTextResponse


def recognize_sign(_: SignToTextRequest) -> SignToTextResponse:
    return SignToTextResponse(
        label=None,
        confidence=None,
        text="Sign recognition pipeline not connected yet.",
        status="stub",
    )
