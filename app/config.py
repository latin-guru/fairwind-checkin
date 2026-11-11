"""Settings, read from the environment once at startup."""

import os
import secrets
from dataclasses import dataclass


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str
    demo_mode: bool       # reseed the sample guests on every boot
    crm_mock: bool        # must stay true: this demo never calls a live HubSpot portal
    secret_key: str       # signs the CSRF cookie
    consent_source: str   # written to marketing_consent_source
    portal_id: str        # fake portal / form ids, only used to show realistic request URLs
    form_guid: str


def load() -> Settings:
    s = Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./fairwind.db"),
        demo_mode=_flag("DEMO_MODE", "1"),
        crm_mock=_flag("CRM_MOCK", "true"),
        secret_key=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        consent_source=os.getenv("CONSENT_SOURCE", "fairwind_guest_checkin"),
        portal_id=os.getenv("HUBSPOT_PORTAL_ID", "00000000"),
        form_guid=os.getenv("HUBSPOT_FORM_GUID", "00000000-0000-0000-0000-000000000000"),
    )
    if not s.crm_mock:
        # The public demo has no live HubSpot client on purpose. Refuse to start instead of pretending.
        raise RuntimeError("CRM_MOCK must be true: this sample-data demo has no live HubSpot client.")
    return s
