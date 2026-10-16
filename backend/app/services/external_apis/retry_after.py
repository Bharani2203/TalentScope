"""Parse a provider Retry-After value into bounded seconds without retaining raw input."""

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def safe_retry_after_seconds(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if re.fullmatch(r"\d{1,8}", candidate):
        return str(min(int(candidate), 86400))
    try:
        retry_at = parsedate_to_datetime(candidate)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    seconds = max(0, math.ceil((retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds()))
    return str(min(seconds, 86400))
