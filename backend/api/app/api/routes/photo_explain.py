from fastapi import APIRouter

from ...schemas.requests import PhotoExplainRequest
from ...schemas.responses import PhotoExplainResponse
from ...services.photo_explain_service import explain_photo

router = APIRouter(tags=["photo-explain"])


@router.post("/photo-explain", response_model=PhotoExplainResponse)
def photo_explain(request: PhotoExplainRequest) -> PhotoExplainResponse:
    return explain_photo(request)
