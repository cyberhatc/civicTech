"""Privacy guardrails: masking of PII and refusal of ungrounded claims.

These helpers are applied on **every** path where text can escape the process:
LLM prompts, LLM outputs, API responses, logs and stored tickets.
"""

from __future__ import annotations

import re

# --- Patterns -----------------------------------------------------------------

# Aadhaar: 12 digits, optionally space/dash separated in groups of 4.
_AADHAAR_GROUPED = re.compile(r"\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b")
# Bare 12-digit runs that are not obviously phone numbers.
# Aadhaar numbers never start with 0 or 1, and a leading "91" is the country code.
_AADHAAR_BARE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
# Indian mobile numbers: optional +91 / 0 prefix then 10 digits starting 6-9.
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?|0)?([6-9]\d{4}[\s\-]?\d{5})(?!\d)")
# Bank-ish account numbers.
_ACCOUNT = re.compile(r"(?<!\d)(\d{9,18})(?!\d)")


def _is_phone_like(digits: str) -> bool:
    """True when a bare digit run looks like a phone number, not an Aadhaar."""
    if digits.startswith("91") and len(digits) == 12:
        return True
    if digits.startswith("0") or digits.startswith("1"):
        return True
    return False


def mask_aadhaar(value: str) -> str:
    """Mask an Aadhaar-like number: `4123 5678 9012` -> `XXXX-XXXX-9012`."""
    if not value:
        return value

    def _grouped_sub(match: re.Match[str]) -> str:
        digits = "".join(match.groups())
        if _is_phone_like(digits):
            return match.group(0)
        return f"XXXX-XXXX-{match.group(3)}"

    out = _AADHAAR_GROUPED.sub(_grouped_sub, value)
    out = _AADHAAR_BARE.sub(
        lambda m: m.group(1) if _is_phone_like(m.group(1)) else f"XXXX-XXXX-{m.group(1)[-4:]}", out
    )
    return out


def mask_phone(value: str) -> str:
    """Mask an Indian mobile number: `98765 43210` -> `XXXXX-3210`."""
    if not value:
        return value
    return _PHONE.sub(lambda m: f"XXXXX-{m.group(1)[-4:]}", value)


def mask_all(value: str) -> str:
    """Apply every masking rule. Use before logging or calling an LLM."""
    if not value:
        return value
    value = mask_aadhaar(value)
    value = mask_phone(value)
    return value


def sanitize_for_log(value: str) -> str:
    """Mask PII and truncate long payloads so logs stay readable."""
    cleaned = mask_all(value or "")
    if len(cleaned) > 500:
        cleaned = cleaned[:497] + "..."
    return cleaned


# --- Grounding ---------------------------------------------------------------

# Amounts / monetary claims. The LLM must not invent these.
_MONEY = re.compile(r"(?:rs\.?|₹|rupees)\s?[\d,]+(?:\.\d+)?\s?(?:lakh|lakhs|crore|crores)?", re.I)

# Phrases that indicate the model is about to make an unsourced promise.
_UNGROUNDED_PHRASES = (
    "pakka milega",
    "pakka milenge",
    "guaranteed",
    "aapko zarur milega",
    "hum 100%",
    "definitely eligible",
    "you will definitely receive",
)


def strip_ungrounded_claims(text: str, allowed_amounts: list[str] | None = None) -> str:
    """Remove monetary figures and promissory phrases that are not grounded.

    `allowed_amounts` holds amount strings that appeared in the retrieved context;
    anything else the model produced is stripped.
    """
    if not text:
        return text

    allowed = {a.strip().lower() for a in (allowed_amounts or [])}

    def _money_sub(match: re.Match[str]) -> str:
        token = match.group(0).strip()
        # Keep the figure only when the same number appears in the grounding.
        digits = re.sub(r"[^\d]", "", token)
        if digits and any(digits == re.sub(r"[^\d]", "", a) for a in allowed):
            return token
        return "[राशि सत्यापित हेतु योजना दस्तावेज़ देखें]"

    text = _MONEY.sub(_money_sub, text)

    for phrase in _UNGROUNDED_PHRASES:
        text = re.sub(re.escape(phrase), "योग्यता योजना के नियमों के अनुसार तय होगी", text, flags=re.IGNORECASE)
    return text


# --- Prompt hygiene ----------------------------------------------------------

_INSTRUCTION_INJECTION = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+instructions|"
    r"disregard\s+(all\s+)?(previous|prior)\s+|"
    r"you\s+are\s+now\s+|system\s*prompt\s*:)",
    re.I,
)


def contains_injection(text: str) -> bool:
    """Detect prompt-injection attempts inside user speech transcripts."""
    return bool(_INSTRUCTION_INJECTION.search(text or ""))


def safe_user_text(text: str, max_len: int = 800) -> str:
    """Prepare untrusted user text for inclusion in a prompt."""
    cleaned = mask_all(text or "")[:max_len]
    return cleaned.replace("\x00", "")
