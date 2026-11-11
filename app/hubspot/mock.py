"""A mocked HubSpot client.

It builds the exact request a real integration would send and writes it to the sync log, so the demo can show
the payload. It never opens a network connection and holds no token.

Production path (documented, not executed):
1. Preferred: Forms API submit, because HubSpot forms already record notice, consent and subscriptions.
   POST https://api.hsforms.com/submissions/v3/integration/submit/{portalId}/{formGuid}
2. Fallback: CRM batch upsert by email, then the Communication Preferences API for the subscription.
   POST https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert
   POST https://api.hubapi.com/communication-preferences/2026-09/statuses/{email}
"""

import json

from app.db import session
from app.mapping import contact_properties
from app.models import Guest, SyncLog

CONSENT_TEXT = (
    "Yes, Fairwind Travel Advisors may email me travel updates and offers, and use my details to show me "
    "relevant ads. I can opt out any time."
)
SUBSCRIPTION_ID = 999  # placeholder id of the "Fairwind travel updates and offers" email subscription type
FORMS_HOST = "https://api.hsforms.com"
API_HOST = "https://api.hubapi.com"


class MockHubSpotClient:
    def __init__(self, *, portal_id: str, form_guid: str, consent_source: str):
        self.portal_id = portal_id
        self.form_guid = form_guid
        self.consent_source = consent_source

    # ---- request builders (pure: easy to test and to show on screen) ----

    def forms_submit_request(self, guest: Guest, props: dict) -> tuple[str, str, dict]:
        url = f"{FORMS_HOST}/submissions/v3/integration/submit/{self.portal_id}/{self.form_guid}"
        body = {
            "fields": [{"objectTypeId": "0-1", "name": k, "value": v} for k, v in props.items()],
            "context": {"pageUri": "https://fairwind.example.com/check-in", "pageName": "Guest check-in"},
        }
        # consentToProcess covers storing the check-in. The marketing subscription is added only for a ticked box;
        # an unticked box sends no communications at all (never "legitimate interest" as a stand-in).
        body["legalConsentOptions"] = {
            "consent": {
                "consentToProcess": True,
                "text": "I agree to Fairwind Travel Advisors storing my details to manage my check-in.",
                "communications": (
                    [{"value": True, "subscriptionTypeId": SUBSCRIPTION_ID, "text": CONSENT_TEXT}]
                    if guest.marketing_consent else []
                ),
            }
        }
        return "POST", url, body

    def contacts_upsert_request(self, guest: Guest, props: dict) -> tuple[str, str, dict]:
        url = f"{API_HOST}/crm/v3/objects/contacts/batch/upsert"
        body = {"inputs": [{"idProperty": "email", "id": guest.email, "properties": props}]}
        return "POST", url, body

    def subscription_request(self, guest: Guest, subscribed: bool) -> tuple[str, str, dict]:
        url = f"{API_HOST}/communication-preferences/2026-09/statuses/{guest.email}"
        body = {
            "subscriptionId": SUBSCRIPTION_ID,
            "statusState": "SUBSCRIBED" if subscribed else "UNSUBSCRIBED",
            "channel": "EMAIL",
            "legalBasis": "CONSENT_WITH_NOTICE" if subscribed else None,
            "legalBasisExplanation": (
                f"Ticked the marketing box on the guest check-in form ({self.consent_source})."
                if subscribed else None
            ),
        }
        return "POST", url, {k: v for k, v in body.items() if v is not None}

    # ---- "send" = log it ----

    def _log(self, email: str, action: str, method: str, url: str, body: dict) -> None:
        with session() as s:
            s.add(SyncLog(guest_email=email, action=action, method=method, url=url,
                          body=json.dumps(body, indent=2, sort_keys=False)))

    def sync_checkin(self, guest: Guest, *, is_new: bool, consent_changed: bool) -> None:
        """What a real sync would send after one check-in: the form submit, the CRM upsert it falls back to,
        and a subscription update only when the consent choice changed."""
        props = contact_properties(guest, consent_source=self.consent_source, is_new=is_new)
        self._log(guest.email, "forms_submit", *self.forms_submit_request(guest, props))
        self._log(guest.email, "contacts_upsert", *self.contacts_upsert_request(guest, props))
        if consent_changed and guest.marketing_consent:
            self._log(guest.email, "subscription_status", *self.subscription_request(guest, True))

    def sync_optout(self, guest: Guest) -> None:
        props = contact_properties(guest, consent_source=self.consent_source, is_new=False)
        self._log(guest.email, "contacts_upsert", *self.contacts_upsert_request(guest, props))
        self._log(guest.email, "subscription_status", *self.subscription_request(guest, False))
