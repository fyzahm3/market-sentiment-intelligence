from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import create_access_token

router = APIRouter(prefix="/api/v1")


class TokenRequest(BaseModel):
    username: str


@router.post("/token")
def create_token(payload: TokenRequest):
    return {"access_token": create_access_token(payload.username), "token_type": "bearer"}
