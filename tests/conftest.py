import re

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app


def make_settings(tmp_path, demo_mode=False):
    return config.Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        demo_mode=demo_mode,
        crm_mock=True,
        secret_key="test-secret",
        consent_source="fairwind_guest_checkin",
        portal_id="12345",
        form_guid="form-guid",
    )


@pytest.fixture
def client(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_client(tmp_path):
    app = create_app(make_settings(tmp_path, demo_mode=True))
    with TestClient(app) as c:
        yield c


def csrf_of(client, path="/"):
    html = client.get(path).text
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


GOOD = {
    "first_name": "Ana",
    "last_name": "Rivera",
    "email": "Ana.Rivera@Example.com",
    "zip": "07065",
    "age_range": "35-44",
    "trip_type": "europe",
    "party_size": "2",
    "budget_band": "5k_10k",
    "source": "instagram",
}


def checkin(client, consent=False, **overrides):
    data = {**GOOD, **overrides, "csrf": csrf_of(client)}
    if consent:
        data["marketing_consent"] = "yes"
    return client.post("/check-in", data=data, follow_redirects=False)
