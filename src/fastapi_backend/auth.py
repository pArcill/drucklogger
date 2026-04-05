# auth.py
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, status

from sqlmodel import Session, select
from .models import User

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Password hashing - use bcrypt directly to avoid passlib compatibility issues
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False
    logger.warning("bcrypt not available, password hashing may be unavailable")


def hash_password(password: str) -> str:
    """Hash a password for storage"""
    try:
        if HAS_BCRYPT:
            # Use bcrypt directly instead of passlib to avoid compatibility issues
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
            logger.debug("Password hashed successfully with bcrypt")
            return hashed.decode('utf-8')
        else:
            logger.error("bcrypt not available for password hashing")
            raise ValueError("Password hashing not available")
    except ValueError as e:
        if "password cannot be longer than 72 bytes" in str(e):
            # Truncate password to 72 bytes if too long
            truncated_password = password[:72]
            salt = bcrypt.gensalt(rounds=12)
            hashed = bcrypt.hashpw(truncated_password.encode('utf-8'), salt)
            logger.warning("Password was longer than 72 bytes, truncated for bcrypt")
            return hashed.decode('utf-8')
        else:
            logger.error(f"Error hashing password: {e}")
            raise
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        if not HAS_BCRYPT:
            logger.error("bcrypt not available for password verification")
            return False
        
        # Truncate to 72 bytes if necessary, same as hash_password does
        plain_password = plain_password[:72]
        is_valid = bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        )
        if is_valid:
            logger.debug("Password verification successful")
        else:
            logger.debug("Password verification failed - invalid password")
        return is_valid
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False



def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        username = to_encode.get("sub", "unknown")
        logger.info(f"Access token created for user '{username}', expires in {(expire - datetime.now(timezone.utc)).total_seconds() / 60:.0f} minutes")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}", exc_info=True)
        raise


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub", "unknown")
        logger.debug(f"Token decoded successfully for user '{username}'")
        return payload
    except JWTError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error decoding token: {e}", exc_info=True)
        return None


def get_user_from_token(token: str, session: Session) -> User:
    """Get user from JWT token"""
    payload = decode_token(token)
    
    if payload is None:
        logger.warning("Token validation failed - invalid token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        logger.warning("Token validation failed - no username in token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    
    if user is None:
        logger.warning(f"User not found in database: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        logger.warning(f"Login attempt with inactive account: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )
    
    logger.debug(f"User '{username}' authenticated from token")
    return user


def register_user(session: Session, username: str, email: str, password: str) -> User:
    """Register a new user"""
    try:
        # Check if user already exists
        statement = select(User).where((User.username == username) | (User.email == email))
        existing_user = session.exec(statement).first()
        
        if existing_user:
            logger.warning(f"Registration failed - duplicate user/email: username={username}, email={email}")
            raise ValueError(f"User with username or email already exists")
        
        # Create new user with default role
        from .role_config import DEFAULT_USER_ROLE
        logger.info(f"Creating new user: username={username}, email={email}, role={DEFAULT_USER_ROLE}")
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=DEFAULT_USER_ROLE
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
        logger.info(f"New user registered successfully: {username} (id={user.id}, role={user.role})")
        return user
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error registering user {username}: {e}", exc_info=True)
        raise


def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password"""
    try:
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
        
        if not user:
            logger.warning(f"Login attempt with non-existent user: {username}")
            return None
        
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Login attempt with incorrect password for user: {username}")
            return None
        
        if not user.is_active:
            logger.warning(f"Login attempt with inactive account: {username}")
            return None
        
        logger.info(f"User authenticated successfully: {username} (role={user.role})")
        return user
    except Exception as e:
        logger.error(f"Error authenticating user {username}: {e}", exc_info=True)
        return None
