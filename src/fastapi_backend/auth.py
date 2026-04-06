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
    """Hash a password for storage using bcrypt"""
    try:
        if not HAS_BCRYPT:
            logger.error("bcrypt not available for password hashing")
            raise ValueError("Password hashing not available - bcrypt not installed")
        
        if not password:
            raise ValueError("Password cannot be empty")
        
        # Truncate password to 72 bytes (bcrypt limit)
        password_bytes = password[:72].encode('utf-8')
        if len(password) > 72:
            logger.warning(f"Password longer than 72 bytes - truncating for bcrypt compatibility")
        
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        logger.debug("Password hashed successfully with bcrypt")
        return hashed.decode('utf-8')
        
    except ValueError as e:
        logger.error(f"Invalid password for hashing: {e}")
        raise
    except Exception as e:
        logger.error(f"Error hashing password: {e}", exc_info=True)
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash
    
    Supports both bcrypt (new format) and handles gracefully if hash is invalid.
    """
    try:
        # Validate inputs
        if not hashed_password or not plain_password:
            logger.warning("Empty password or hash provided to verify_password")
            return False
            
        if not HAS_BCRYPT:
            logger.error("bcrypt not available for password verification")
            return False
        
        # Truncate password to 72 bytes (bcrypt limitation)
        plain_password_bytes = plain_password[:72].encode('utf-8')
        
        # Convert hash to bytes if it's a string
        if isinstance(hashed_password, str):
            try:
                hashed_bytes = hashed_password.encode('utf-8')
            except UnicodeEncodeError as e:
                logger.error(f"Failed to encode hashed password as UTF-8: {e}")
                return False
        else:
            hashed_bytes = hashed_password
        
        # Verify the password
        try:
            is_valid = bcrypt.checkpw(plain_password_bytes, hashed_bytes)
            if is_valid:
                logger.debug("Password verification successful")
            else:
                logger.debug("Password verification failed - invalid password")
            return is_valid
        except ValueError as e:
            # This commonly happens if the hash is not in valid bcrypt format
            # This could mean the hash was stored in an older format or is corrupted
            error_msg = str(e).lower()
            if "invalid salt" in error_msg or "invalid hash" in error_msg:
                logger.warning(f"Password hash is not in valid bcrypt format: {e}. This might be an old passlib hash that needs migration.")
                return False
            else:
                logger.error(f"bcrypt verification error: {e}")
                return False
    except Exception as e:
        logger.error(f"Unexpected error verifying password: {e}", exc_info=True)
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
        # Validate inputs
        if not username or not password:
            logger.warning("Empty username or password provided to authenticate_user")
            return None
        
        # Query for user
        statement = select(User).where(User.username == username)
        user = session.exec(statement).first()
        
        if not user:
            logger.warning(f"Login attempt with non-existent user: {username}")
            return None
        
        # Verify password
        if not user.hashed_password:
            logger.warning(f"User {username} has no password hash stored - password verification impossible")
            return None
        
        if not verify_password(password, user.hashed_password):
            logger.info(f"Login attempt with incorrect password for user: {username}")
            return None
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt with inactive account: {username}")
            return None
        
        logger.info(f"User authenticated successfully: {username} (role={user.role})")
        return user
        
    except Exception as e:
        logger.error(f"Error authenticating user {username}: {e}", exc_info=True)
        return None
