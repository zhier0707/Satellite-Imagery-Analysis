"""
密码哈希工具
============

- 算法：bcrypt
- 通过 passlib 抽象；未来可平滑切换 argon2 等
- 固定 bcrypt==4.0.1（避免新版 bcrypt 5.x 的 backend API 变更报错）
"""
from __future__ import annotations

from passlib.context import CryptContext

# bcrypt 方案；deprecated="auto" 让旧 hash 自动迁移
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """把明文密码哈希为不可逆字符串（含盐值）。"""
    if not plain:
        raise ValueError("password must be a non-empty string")
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文与哈希是否匹配。"""
    if not plain or not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        # 哈希格式异常（损坏/不识别）一律视为不通过
        return False
