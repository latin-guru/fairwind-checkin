from sqlalchemy import func, select

from app import db
from app.models import Guest
from tests.conftest import GOOD, checkin, csrf_of


def count_guests():
    with db.session() as s:
        return s.scalar(select(func.count()).select_from(Guest))


def test_form_renders_with_consent_unchecked_and_no_id_upload(client):
    html = client.get("/").text
    assert 'name="marketing_consent" type="checkbox" value="yes">' in html  # no "checked"
    assert 'type="file"' not in html and "capture" not in html
    assert "Sample-data demo" in html


def test_valid_checkin_saves_and_redirects(client):
    r = checkin(client)
    assert r.status_code == 303 and r.headers["location"].startswith("/thanks?g=")
    assert count_guests() == 1


def test_email_is_lowercased_and_trimmed(client):
    checkin(client, email="  Ana.Rivera@Example.COM ")
    with db.session() as s:
        assert s.scalar(select(Guest.email)) == "ana.rivera@example.com"


def test_invalid_email_rejected(client):
    r = checkin(client, email="not-an-email")
    assert r.status_code == 422 and "valid email" in r.text
    assert count_guests() == 0


def test_bad_zip_rejected(client):
    for bad in ("1234", "123456", "abcde"):
        r = checkin(client, zip=bad)
        assert r.status_code == 422 and "5-digit zip" in r.text


def test_unknown_choice_rejected(client):
    r = checkin(client, trip_type="space")
    assert r.status_code == 422 and "trip type" in r.text


def test_missing_name_rejected(client):
    r = checkin(client, first_name="  ")
    assert r.status_code == 422 and "first name" in r.text


def test_markup_in_name_rejected(client):
    r = checkin(client, last_name="<script>")
    assert r.status_code == 422


def test_missing_csrf_rejected(client):
    r = client.post("/check-in", data=GOOD, follow_redirects=False)
    assert r.status_code == 400 and count_guests() == 0


def test_honeypot_silently_drops(client):
    data = {**GOOD, "csrf": csrf_of(client), "website": "spam.example"}
    r = client.post("/check-in", data=data, follow_redirects=False)
    assert r.status_code == 303 and count_guests() == 0


def test_repeat_email_updates_same_guest(client):
    checkin(client)
    checkin(client, trip_type="cruise", email="ANA.RIVERA@example.com")
    assert count_guests() == 1
    with db.session() as s:
        g = s.scalar(select(Guest))
        assert g.trip_type == "cruise" and g.checkin_count == 2
