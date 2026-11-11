from app import guests, segments
from app.seed import build_guests


def test_seed_is_fifty_fake_guests_with_mixed_consent():
    gs = build_guests()
    assert len(gs) == 50
    assert all(g.email.endswith("@example.com") for g in gs)
    eligible = sum(g.ad_eligible for g in gs)
    assert 25 <= eligible <= 45 and eligible < len(gs)


def test_seed_is_repeatable():
    a, b = build_guests(), build_guests()
    assert [g.email for g in a] == [g.email for g in b]


def test_dashboard_renders_with_seed(seeded_client):
    html = seeded_client.get("/dashboard").text
    assert "Ideal Traveler Profile" in html and "Suggested HubSpot Active Lists" in html
    assert "Consented, 35–54, Europe, $5–10K" in html
    assert "LinkedIn 300" in html and "Google 1,000" in html
    assert 'id="profile-data"' in html


def test_every_audience_list_is_a_subset_of_the_base(seeded_client):
    lists = segments.suggested_lists(guests.all_guests())
    base = {g.id for g in lists[0].members}
    for lst in lists[1:]:
        ids = {g.id for g in lst.members}
        if lst.purpose == "audience":
            assert ids <= base, lst.name
        else:
            assert not ids & base


def test_pages_and_headers(seeded_client):
    for path in ("/", "/dashboard", "/mapping", "/sync-log", "/opt-out", "/healthz"):
        r = seeded_client.get(path)
        assert r.status_code == 200, path
    csp = seeded_client.get("/").headers["content-security-policy"]
    assert "script-src 'self';" in csp and "unsafe-inline" not in csp


def test_live_mode_refuses_to_start(monkeypatch):
    import pytest

    from app import config

    monkeypatch.setenv("CRM_MOCK", "false")
    with pytest.raises(RuntimeError):
        config.load()


def test_dashboard_polish(seeded_client):
    from tests.conftest import checkin

    html = seeded_client.get("/dashboard").text
    assert "checked in more than once" in html
    assert "No HubSpot calls yet" in html and 'href="/sync-log"' in html
    assert "How it reaches Meta and Google" in html
    checkin(seeded_client, consent=True, email="new@example.com")
    assert "Last mocked HubSpot sync:" in seeded_client.get("/dashboard").text
