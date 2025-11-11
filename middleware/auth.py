from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from typing import Optional
import os
from database import get_db
from models import User
from schemas import Token, TokenRefresh
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
security = HTTPBearer()
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
def verify_token(token: str, token_type: str = "access"):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type, expected {token_type}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials
    payload = verify_token(token, "access")
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not hasattr(current_user, "is_active") or not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "")
    try:
        payload = verify_token(token, "access")
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except HTTPException:
        return None
def rotate_refresh_token(refresh_token: str, db: Session):
    payload = verify_token(refresh_token, "refresh")
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    new_refresh_token = create_refresh_token({"sub": user_id})
    return {
        "access_token": create_access_token({"sub": user_id}),
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
def setup_auth(app):
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.url.path in ["/login", "/register", "/docs", "/openapi.json", "/redoc"]:
            response = await call_next(request)
            return response
        request.state.user = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            try:
                payload = verify_token(token, "access")
                user_id = payload.get("sub")
                if user_id:
                    db = next(get_db())
                    try:
                        user = db.query(User).filter(User.id == user_id).first()
                        if user:
                            request.state.user = user
                    finally:
                        db.close()
            except HTTPException:
                pass
        response = await call_next(request)
        return response