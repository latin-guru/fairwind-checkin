"""Seed ~50 clearly fake Fairwind guests (Faker, example.com emails) with a realistic mix.

Run on boot when DEMO_MODE=1, or by hand: python -m app.seed
The mix is weighted so the dashboard tells a story (North Jersey zips, Europe and beach trips lead, ~70% opt in),
and is deterministic, so screenshots and tests stay stable.
"""

import random
import secrets
import uuid
from datetime import timedelta

from faker import Faker

from app import db
from app.models import Guest, utcnow

SEED = 2026
COUNT = 50

ZIPS = [("07065", 9), ("07090", 7), ("07901", 6), ("07030", 5), ("07302", 4), ("07102", 3), ("08830", 3),
        ("10001", 3), ("07960", 2), ("08540", 2)]
AGES = [("18-24", 3), ("25-34", 10), ("35-44", 13), ("45-54", 11), ("55-64", 8), ("65+", 5)]
TRIPS = [("europe", 12), ("beach", 11), ("cruise", 8), ("family", 7), ("honeymoon", 5), ("adventure", 4),
         ("group_event", 3)]
PARTY = [("1", 4), ("2", 22), ("3-4", 14), ("5-8", 7), ("9+", 3)]
BUDGETS = [("under_2k", 7), ("2k_5k", 16), ("5k_10k", 17), ("10k_plus", 10)]
SOURCES = [("instagram", 14), ("facebook", 9), ("google", 11), ("referral", 10), ("event", 4), ("other", 2)]


def _pick(rng, weighted):
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]


def build_guests(count: int = COUNT, seed: int = SEED) -> list[Guest]:
    rng = random.Random(seed)
    fake = Faker("en_US")
    Faker.seed(seed)
    now = utcnow()
    guests, used = [], set()
    while len(guests) < count:
        first, last = fake.first_name(), fake.last_name()
        email = f"{first}.{last}{rng.randint(1, 99)}@example.com".lower()
        if email in used:
            continue
        used.add(email)
        first_seen = now - timedelta(days=rng.randint(1, 120), hours=rng.randint(0, 23))
        visits = rng.choices([1, 2, 3], weights=[7, 2, 1])[0]
        last_seen = min(now, first_seen + timedelta(days=rng.randint(0, 30) * (visits - 1)))
        consent = rng.random() < 0.7
        g = Guest(
            external_guest_id="fw-" + uuid.UUID(int=rng.getrandbits(128)).hex[:16],
            optout_token=secrets.token_urlsafe(24),
            first_name=first, last_name=last, email=email,
            zip=_pick(rng, ZIPS), age_range=_pick(rng, AGES), trip_type=_pick(rng, TRIPS),
            party_size=_pick(rng, PARTY), budget_band=_pick(rng, BUDGETS), source=_pick(rng, SOURCES),
            marketing_consent=consent,
            marketing_consent_date=first_seen if consent else None,
            first_checkin_at=first_seen, last_checkin_at=last_seen, checkin_count=visits,
        )
        guests.append(g)
    # A few realistic edge cases: two who opted out later, one who unsubscribed from all email in HubSpot.
    opted_in = [g for g in guests if g.marketing_consent]
    for g in opted_in[:2]:
        g.marketing_consent = False
        g.opted_out_at = g.marketing_consent_date = g.last_checkin_at
    opted_in[2].email_optout = True
    return guests


def seed() -> int:
    db.reset()
    guests = build_guests()
    with db.session() as s:
        s.add_all(guests)
    return len(guests)


if __name__ == "__main__":
    from app import config

    db.init(config.load().database_url)
    print(f"Seeded {seed()} fake guests.")
