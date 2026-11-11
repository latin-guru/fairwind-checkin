"""Consent rules: non-consenting guests are stored but never reach an ad audience."""

from app import guests, profile, segments
from tests.conftest import checkin


def eligible_emails(lst):
    return {g.email for g in lst.members}


def test_unchecked_box_means_no_consent(client):
    checkin(client)
    g = guests.find_by_email("ana.rivera@example.com")
    assert g is not None and g.marketing_consent is False and not g.ad_eligible


def test_non_consenting_guest_is_in_no_ad_list(client):
    checkin(client, consent=False, email="no@example.com")
    checkin(client, consent=True, email="yes@example.com")
    for lst in segments.suggested_lists(guests.all_guests()):
        if lst.purpose == "audience":
            assert "no@example.com" not in eligible_emails(lst), lst.name
    base = segments.suggested_lists(guests.all_guests())[0]
    assert eligible_emails(base) == {"yes@example.com"}


def test_suppression_list_holds_the_non_consenting(client):
    checkin(client, consent=False, email="no@example.com")
    checkin(client, consent=True, email="yes@example.com")
    suppression = [l for l in segments.suggested_lists(guests.all_guests()) if l.purpose == "suppression"][0]
    assert eligible_emails(suppression) == {"no@example.com"}


def test_hubspot_email_optout_also_excludes(client):
    checkin(client, consent=True)
    from app import db
    from app.models import Guest

    with db.session() as s:
        s.query(Guest).update({Guest.email_optout: True})
    everyone = guests.all_guests()
    assert all("ana.rivera@example.com" not in eligible_emails(l)
               for l in segments.suggested_lists(everyone) if l.purpose == "audience")


def test_repeat_visit_without_box_does_not_withdraw_or_grant(client):
    checkin(client, consent=True)
    checkin(client, consent=False)  # unticked on the second visit
    assert guests.find_by_email("ana.rivera@example.com").marketing_consent is True
    checkin(client, consent=False, email="later@example.com")
    checkin(client, consent=False, email="later@example.com")
    assert guests.find_by_email("later@example.com").marketing_consent is False


def test_profile_counts_only_consented(client):
    checkin(client, consent=True, email="yes@example.com", trip_type="europe")
    checkin(client, consent=False, email="no@example.com", trip_type="cruise")
    p = profile.ideal_traveler(guests.all_guests())
    trips = dict(zip(p["trips"]["labels"], p["trips"]["counts"]))
    assert trips["Europe"] == 1 and trips["Cruise"] == 0 and p["size"] == 1


def test_example_list_rules(client):
    checkin(client, consent=True, email="match@example.com", age_range="45-54", trip_type="europe",
            budget_band="5k_10k")
    checkin(client, consent=True, email="wrongage@example.com", age_range="25-34", trip_type="europe",
            budget_band="5k_10k")
    lst = [l for l in segments.suggested_lists(guests.all_guests()) if "Europe" in l.name][0]
    assert eligible_emails(lst) == {"match@example.com"}
    assert lst.filter_lines[0] == "marketing_consent is equal to true"
    assert "AND budget_band is any of 5k_10k" in lst.filter_lines
