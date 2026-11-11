import json
import re

from sqlalchemy import select

from app import db, guests, segments
from app.models import SyncLog
from tests.conftest import checkin, csrf_of


def opt_in_ana(client):
    r = checkin(client, consent=True)
    return r.headers["location"].split("g=")[1]


def in_any_audience(email):
    return any(email in {g.email for g in l.members}
               for l in segments.suggested_lists(guests.all_guests()) if l.purpose == "audience")


def test_thanks_page_shows_optout_link(client):
    token = opt_in_ana(client)
    html = client.get(f"/thanks?g={token}").text
    assert f"/opt-out?g={token}" in html and "what would sync to HubSpot" in html


def test_one_click_link_opts_out_and_leaves_audiences(client):
    token = opt_in_ana(client)
    assert in_any_audience("ana.rivera@example.com")
    page = client.get(f"/opt-out?g={token}").text
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', page).group(1)
    r = client.post("/opt-out", data={"csrf": csrf, "token": token})
    assert r.status_code == 200 and "opted out" in r.text
    g = guests.find_by_email("ana.rivera@example.com")
    assert g.marketing_consent is False and g.opted_out_at is not None
    assert not in_any_audience("ana.rivera@example.com")


def test_optout_by_email_and_unsubscribe_payload(client):
    opt_in_ana(client)
    r = client.post("/opt-out", data={"csrf": csrf_of(client, "/opt-out"), "email": "ANA.RIVERA@example.com"})
    assert r.status_code == 200
    with db.session() as s:
        last = s.scalars(select(SyncLog).where(SyncLog.action == "subscription_status")
                         .order_by(SyncLog.id.desc())).first()
        upsert = s.scalars(select(SyncLog).where(SyncLog.action == "contacts_upsert")
                           .order_by(SyncLog.id.desc())).first()
    assert json.loads(last.body)["statusState"] == "UNSUBSCRIBED"
    props = json.loads(upsert.body)["inputs"][0]["properties"]
    assert props["marketing_consent"] == "false" and "hs_legal_basis" not in props


def test_unknown_email_gets_same_answer(client):
    r = client.post("/opt-out", data={"csrf": csrf_of(client, "/opt-out"), "email": "nobody@example.com"})
    assert r.status_code == 200 and "opted out" in r.text


def test_optout_needs_csrf(client):
    opt_in_ana(client)
    r = client.post("/opt-out", data={"email": "ana.rivera@example.com"})
    assert r.status_code == 400
    assert guests.find_by_email("ana.rivera@example.com").marketing_consent is True


def test_dashboard_optout_control(client):
    opt_in_ana(client)
    g = guests.find_by_email("ana.rivera@example.com")
    r = client.post(f"/dashboard/opt-out/{g.id}", data={"csrf": csrf_of(client, "/dashboard")},
                    follow_redirects=False)
    assert r.status_code == 303
    assert not in_any_audience("ana.rivera@example.com")


def test_opting_back_in_after_optout(client):
    token = opt_in_ana(client)
    client.post("/opt-out", data={"csrf": csrf_of(client, f"/opt-out?g={token}"), "token": token})
    checkin(client, consent=True)
    assert guests.find_by_email("ana.rivera@example.com").ad_eligible
