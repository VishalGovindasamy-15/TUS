from __future__ import annotations
import secrets


def uid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def unit_id() -> str:
    return f"TU{secrets.token_hex(5).upper()}"


def invite_code() -> str:
    return f"TU-{secrets.token_hex(3).upper()}"
