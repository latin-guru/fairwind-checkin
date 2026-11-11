import json

from sqlalchemy import select

from app import db
from app.mapping import LEGAL_BASIS_CONSENT, PROPERTY_TABLE
from app.models import Guest, SyncLog
from tests.conftest import checkin


def logs(action=None):
    with db.session() as s:
        q = select(SyncLog).order_by(SyncLog.id)
        if action:
            q = q.where(SyncLog.action == action)
        return list(s.scalars(q))


def upsert_props(row):
    return json.loads(row.body)["inputs"][0]["properties"]


def test_standard_and_custom_properties(client):
    checkin(client, consent=True)
    props = upsert_props(logs("contacts_upsert")[-1])
    assert props["firstname"] == "Ana" and props["lastname"] == "Rivera"
    assert props["email"] == "ana.rivera@example.com" and props["zip"] == "07065"
    assert props["age_range"] == "35-44" and props["trip_type"] == "europe"
    assert props["party_size"] == "2" and props["budget_band"] == "5k_10k"
    assert props["lead_source_detail"] == "instagram"
    assert props["marketing_consent"] == "true"
    assert props["hs_legal_basis"] == LEGAL_BASIS_CONSENT
    assert props["lifecyclestage"] == "lead"
    assert props["external_guest_id"].startswith("fw-")
    assert props["marketing_consent_source"] == "fairwind_guest_checkin"
    assert props["marketing_consent_date"].isdigit()  # epoch milliseconds


def test_no_consent_means_no_legal_basis(client):
    checkin(client, consent=False)
    props = upsert_props(logs("contacts_upsert")[-1])
    assert props["marketing_consent"] == "false"
    assert "hs_legal_basis" not in props and "marketing_consent_date" not in props


def test_upsert_is_by_email(client):
    checkin(client)
    row = logs("contacts_upsert")[-1]
    body = json.loads(row.body)
    assert row.url.endswith("/crm/v3/objects/contacts/batch/upsert")
    assert body["inputs"][0]["idProperty"] == "email" and body["inputs"][0]["id"] == "ana.rivera@example.com"


def test_repeat_checkin_does_not_reset_lifecycle_stage(client):
    checkin(client)
    checkin(client)
    assert "lifecyclestage" in upsert_props(logs("contacts_upsert")[0])
    assert "lifecyclestage" not in upsert_props(logs("contacts_upsert")[-1])


def test_forms_payload_carries_consent_only_when_ticked(client):
    checkin(client, consent=True)
    yes = json.loads(logs("forms_submit")[-1].body)
    assert yes["legalConsentOptions"]["consent"]["communications"][0]["value"] is True
    assert {"objectTypeId": "0-1", "name": "trip_type", "value": "europe"} in yes["fields"]
    checkin(client, consent=False, email="bo@example.com")
    no = json.loads(logs("forms_submit")[-1].body)
    assert no["legalConsentOptions"]["consent"]["communications"] == []
    assert "legitimateInterest" not in no["legalConsentOptions"]


def test_subscription_call_only_on_opt_in(client):
    checkin(client, consent=False)
    assert logs("subscription_status") == []
    checkin(client, consent=True)
    sub = json.loads(logs("subscription_status")[-1].body)
    assert sub["statusState"] == "SUBSCRIBED" and sub["legalBasis"] == "CONSENT_WITH_NOTICE"


def test_mock_never_holds_a_token():
    import app.hubspot.mock as mock

    src = open(mock.__file__).read()
    assert "Authorization" not in src and "httpx" not in src and "requests" not in src


def test_property_table_covers_every_written_property(client):
    checkin(client, consent=True)
    written = set(upsert_props(logs("contacts_upsert")[-1]))
    documented = {name for name, *_ in PROPERTY_TABLE}
    assert written <= documented


def test_guest_row_matches(client):
    checkin(client, consent=True)
    with db.session() as s:
        g = s.scalar(select(Guest))
        assert g.marketing_consent and g.marketing_consent_date is not None
