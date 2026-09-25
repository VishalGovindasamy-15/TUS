from __future__ import annotations
import httpx

from app.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
log = get_logger("sms")


async def send_otp(phone: str, otp: str) -> bool:
    provider = settings.SMS_PROVIDER.lower()
    if provider == "dummy":
        log.info("otp_issued", phone=phone, otp=otp)
        return True
    try:
        if provider == "msg91":
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    "https://control.msg91.com/api/v5/otp",
                    params={"authkey": settings.MSG91_API_KEY, "mobile": phone, "otp": otp,
                            "sender": settings.MSG91_SENDER},
                )
            return True
        if provider == "twilio":
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_SID}/Messages.json",
                    auth=(settings.TWILIO_SID, settings.TWILIO_TOKEN),
                    data={"From": settings.TWILIO_FROM, "To": phone,
                          "Body": f"Your TrustUs code is {otp}"},
                )
            return True
    except Exception as exc:  # noqa: BLE001
        log.error("sms_failed", provider=provider, error=str(exc))
        return False
    log.error("sms_unknown_provider", provider=provider)
    return False
