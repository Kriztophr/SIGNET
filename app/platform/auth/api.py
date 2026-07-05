import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.platform.auth.dependencies import get_current_user
from app.platform.auth.models import User
from app.platform.auth.schemas import LoginRequest, TokenResponse, UserOut
from app.platform.auth.service import AuthService
from app.platform.auth.throttle import get_login_throttle
from app.platform.auth.tokens import create_access_token
from app.platform.db.session import get_db

router = APIRouter(tags=["auth"])

security_log = structlog.get_logger("security")


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = body.email.strip().lower()
    throttle = get_login_throttle()
    throttle.check(email)

    user = AuthService(db).authenticate(email, body.password)
    if user is None:
        throttle.record_failure(email)
        security_log.warning("login_failed", email=email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    throttle.reset(email)
    security_log.info("login_succeeded", email=email, user_id=str(user.id))
    return TokenResponse(access_token=create_access_token(user))


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
