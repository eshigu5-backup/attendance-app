import os
import hashlib
from dotenv import load_dotenv

load_dotenv()


def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def check_login(username: str, password: str) -> bool:
    env_user = os.getenv("AUTH_USERNAME", "")
    env_hash = os.getenv("AUTH_PASSWORD_HASH", "")
    if not env_user or not env_hash:
        return False
    return username == env_user and hash_password(password) == env_hash
