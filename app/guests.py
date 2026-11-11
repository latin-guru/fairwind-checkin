"""Saving check-ins and opt-outs. One guest per email; a repeat visit updates the same row."""

import secrets
import uuid

from sqlalchemy import select

from app.db import session
from app.models import Guest, utcnow
from app.schemas import CheckIn


def find_by_email(email: str) -> Guest | None:
    with session() as s:
        return s.scalar(select(Guest).where(Guest.email == email.strip().lower()))


def find_by_token(token: str) -> Guest | None:
    if not token or len(token) > 64:
        return None
    with session() as s:
        return s.scalar(select(Guest).where(Guest.optout_token == token))


def save_checkin(data: CheckIn) -> tuple[Guest, bool, bool]:
    """Upsert by email. Returns (guest, is_new, consent_changed).

    Consent rules:
    - Ticking the box opts the guest in (and stamps the consent date).
    - Leaving it unticked on a repeat visit does NOT silently withdraw an earlier opt-in; withdrawal is the
      explicit opt-out link. It also never opts anyone in.
    """
    now = utcnow()
    with session() as s:
        guest = s.scalar(select(Guest).where(Guest.email == data.email))
        is_new = guest is None
        if is_new:
            guest = Guest(
                external_guest_id="fw-" + uuid.uuid4().hex[:16],
                optout_token=secrets.token_urlsafe(24),
                email=data.email,
                first_checkin_at=now,
                checkin_count=0,
                marketing_consent=False,
            )
            s.add(guest)
        for field in ("first_name", "last_name", "zip", "age_range", "trip_type", "party_size",
                      "budget_band", "source"):
            setattr(guest, field, getattr(data, field))
        guest.last_checkin_at = now
        guest.checkin_count = (guest.checkin_count or 0) + 1

        consent_changed = False
        if data.marketing_consent and not guest.marketing_consent:
            guest.marketing_consent = True
            guest.marketing_consent_date = now
            guest.opted_out_at = None
            consent_changed = True
        s.flush()
        s.refresh(guest)
        return guest, is_new, consent_changed


def opt_out(guest_id: int) -> Guest | None:
    """Withdraw marketing consent. The guest stays a contact (check-in history), but leaves every ad audience."""
    now = utcnow()
    with session() as s:
        guest = s.get(Guest, guest_id)
        if guest is None:
            return None
        guest.marketing_consent = False
        guest.marketing_consent_date = now
        guest.opted_out_at = now
        s.flush()
        s.refresh(guest)
        return guest


def all_guests() -> list[Guest]:
    with session() as s:
        return list(s.scalars(select(Guest).order_by(Guest.last_checkin_at.desc())))
