"""Tables: one row per guest (upserted by email) and a log of every mocked HubSpot call."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_guest_id: Mapped[str] = mapped_column(String(40), unique=True)  # idempotency key sent to HubSpot
    optout_token: Mapped[str] = mapped_column(String(64), unique=True)       # for the one-click opt-out link

    first_name: Mapped[str] = mapped_column(String(60))
    last_name: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    zip: Mapped[str] = mapped_column(String(5))
    age_range: Mapped[str] = mapped_column(String(10))
    trip_type: Mapped[str] = mapped_column(String(20))
    party_size: Mapped[str] = mapped_column(String(5))
    budget_band: Mapped[str] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(20))

    # Consent audit trail
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_consent_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Mirrors HubSpot's hs_email_optout. HubSpot sets it when someone unsubscribes from all email; this app only
    # reads it (the seed marks a few guests as already unsubscribed to show the exclusion rule).
    email_optout: Mapped[bool] = mapped_column(Boolean, default=False)

    first_checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checkin_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checkin_count: Mapped[int] = mapped_column(Integer, default=1)

    @property
    def ad_eligible(self) -> bool:
        """The one rule every ad audience starts from."""
        return bool(self.marketing_consent) and not self.email_optout


class SyncLog(Base):
    """Every request the mocked HubSpot client would have sent. Nothing here ever leaves the app."""

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    guest_email: Mapped[str] = mapped_column(String(254), index=True)
    action: Mapped[str] = mapped_column(String(40))   # forms_submit | contacts_upsert | subscription_status
    method: Mapped[str] = mapped_column(String(8))
    url: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)            # the exact JSON body, pretty-printed
