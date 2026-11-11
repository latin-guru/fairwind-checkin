"""Turn a guest into HubSpot contact properties.

Standard properties use HubSpot's default internal names. Everything marked "custom" would be created once in
the portal (Settings > Properties, or POST /crm/v3/properties/contacts) before the first sync.
"""

from datetime import datetime

from app.models import Guest

LEGAL_BASIS_CONSENT = "Freely given consent from contact"

# (internal name, label, standard/custom, type) — also rendered in the README and on the mapping page.
PROPERTY_TABLE = [
    ("firstname", "First name", "standard", "string"),
    ("lastname", "Last name", "standard", "string"),
    ("email", "Email", "standard", "string (upsert key)"),
    ("zip", "Postal code", "standard", "string"),
    ("hs_legal_basis", "Legal basis for processing contact's data", "standard", "enumeration (only when consented)"),
    ("lifecyclestage", "Lifecycle stage", "standard", "enumeration (set to lead on first check-in only)"),
    ("age_range", "Age range", "custom", "enumeration"),
    ("trip_type", "Trip type", "custom", "enumeration"),
    ("party_size", "Party size", "custom", "enumeration"),
    ("budget_band", "Budget band", "custom", "enumeration"),
    ("lead_source_detail", "How they heard about us", "custom", "enumeration"),
    ("marketing_consent", "Marketing consent", "custom", "boolean checkbox"),
    ("marketing_consent_date", "Marketing consent date", "custom", "datetime"),
    ("marketing_consent_source", "Marketing consent source", "custom", "string"),
    ("last_checkin_date", "Last check-in date", "custom", "datetime"),
    ("external_guest_id", "External guest id", "custom", "string, unique"),
]


def _ms(dt: datetime | None) -> str | None:
    """HubSpot datetime properties take epoch milliseconds (as a string in the API)."""
    return str(int(dt.timestamp() * 1000)) if dt else None


def contact_properties(guest: Guest, *, consent_source: str, is_new: bool) -> dict[str, str]:
    """Every property this app writes for one guest. Values are strings, the way HubSpot's API takes them."""
    props = {
        "firstname": guest.first_name,
        "lastname": guest.last_name,
        "email": guest.email,
        "zip": guest.zip,
        "age_range": guest.age_range,
        "trip_type": guest.trip_type,
        "party_size": guest.party_size,
        "budget_band": guest.budget_band,
        "lead_source_detail": guest.source,
        "marketing_consent": "true" if guest.marketing_consent else "false",
        "last_checkin_date": _ms(guest.last_checkin_at),
        "external_guest_id": guest.external_guest_id,
    }
    if guest.marketing_consent_date:
        # Stamped on opt-in and again on opt-out, so the record shows when the choice last changed.
        props["marketing_consent_date"] = _ms(guest.marketing_consent_date)
        props["marketing_consent_source"] = consent_source
    if guest.marketing_consent:
        # Only a ticked box is a legal basis. A guest who didn't tick it gets no legal basis at all;
        # "Legitimate interest" or "Not applicable" are not stand-ins for a missing checkbox.
        props["hs_legal_basis"] = LEGAL_BASIS_CONSENT
    if is_new:
        # Never overwrite a later stage (opportunity, customer) on a repeat check-in.
        props["lifecyclestage"] = "lead"
    return {k: v for k, v in props.items() if v is not None}
