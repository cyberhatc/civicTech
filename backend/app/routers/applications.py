"""Application status lookup endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.response import envelope
from app.db.database import get_db
from app.services import status

router = APIRouter(tags=["applications"])


@router.get("/applications/lookup")
def lookup(
    aadhaarLast4: str | None = Query(default=None, max_length=12),  # noqa: N815
    mobile: str | None = Query(default=None, max_length=15),
    schemeId: str | None = Query(default=None),  # noqa: N815
) -> dict[str, Any]:
    """Look up applications by Aadhaar last-4 digits or registered mobile number."""
    if not aadhaarLast4 and not mobile:
        return envelope(
            {
                "found": False,
                "message": "कृपया आधार के अंतिम 4 अंक या पंजीकृत मोबाइल नंबर दें।",
                "applications": [],
            }
        )
    result = status.lookup(
        get_db(), aadhaar_last4=aadhaarLast4, mobile=mobile, scheme_id=schemeId
    )
    return envelope(result)
