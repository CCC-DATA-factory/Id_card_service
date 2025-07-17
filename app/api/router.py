from fastapi import APIRouter

from api import transcript, extract_front, extract_back

router = APIRouter()
router.include_router(transcript.router)
router.include_router(extract_front.router)
router.include_router(extract_back.router)
