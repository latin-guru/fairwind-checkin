"""The fixed answer lists for the check-in form.

Each list is (value stored and sent to HubSpot, label shown to the guest). The values are the internal
option values a HubSpot admin would create on the matching custom enumeration property.
"""

AGE_RANGES = [
    ("18-24", "18–24"),
    ("25-34", "25–34"),
    ("35-44", "35–44"),
    ("45-54", "45–54"),
    ("55-64", "55–64"),
    ("65+", "65+"),
]

TRIP_TYPES = [
    ("beach", "Beach"),
    ("cruise", "Cruise"),
    ("europe", "Europe"),
    ("adventure", "Adventure"),
    ("family", "Family"),
    ("honeymoon", "Honeymoon"),
    ("group_event", "Group / event"),
]

PARTY_SIZES = [
    ("1", "Just me"),
    ("2", "2"),
    ("3-4", "3–4"),
    ("5-8", "5–8"),
    ("9+", "9 or more"),
]

BUDGET_BANDS = [
    ("under_2k", "Under $2K"),
    ("2k_5k", "$2K–$5K"),
    ("5k_10k", "$5K–$10K"),
    ("10k_plus", "$10K+"),
]

SOURCES = [
    ("instagram", "Instagram"),
    ("facebook", "Facebook"),
    ("google", "Google"),
    ("referral", "A friend or family member"),
    ("event", "An event"),
    ("other", "Other"),
]


def values(options):
    return [v for v, _ in options]


def label(options, value):
    return dict(options).get(value, value)
