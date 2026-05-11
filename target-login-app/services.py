import re
from datetime import datetime, timedelta
from typing import Tuple

import bcrypt

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_username(username: str) -> Tuple[bool, str]:
    if not username:
        return False, "用户名不能为空"
    if not USERNAME_PATTERN.match(username):
        return False, "用户名须为 3–20 位，仅含字母、数字、下划线"
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    if not password:
        return False, "密码不能为空"
    if len(password) < 8 or len(password) > 30:
        return False, "密码长度须为 8–30 位"
    if not re.search(r"[a-z]", password):
        return False, "密码须包含小写字母"
    if not re.search(r"[A-Z]", password):
        return False, "密码须包含大写字母"
    if not re.search(r"\d", password):
        return False, "密码须包含数字"
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    if not email or not EMAIL_PATTERN.match(email.strip()):
        return False, "邮箱格式不正确"
    return True, ""


def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain: str, stored: bytes) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored)
    except ValueError:
        return False


LOCK_MINUTES = 30
MAX_FAILED = 5


def lock_deadline():
    return datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)


def is_locked(locked_until) -> bool:
    if locked_until is None:
        return False
    return datetime.utcnow() < locked_until
