from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
import os

SECRET = os.getenv("JWT_SECRET", "dev-secret")
ALG = "HS256"

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(p: str) -> str:
    """Hash a plaintext password."""
    return pwd.hash(p)

def verify_password(p: str, h: str) -> bool:
    """Verify a plaintext password against a hash."""
    return pwd.verify(p, h)

def create_token(user_id: int) -> str:
    """Create a JWT token for a given user ID."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=24)).timestamp()),
        },
        SECRET,
        algorithm=ALG,
    )

def decode_token(token: str) -> int:
    """Decode a JWT token and return the user ID."""
    payload = jwt.decode(token, SECRET, algorithms=[ALG])
    return int(payload["sub"])
