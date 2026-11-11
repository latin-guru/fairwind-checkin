"""Suggested HubSpot active lists (HubSpot now calls them active segments).

Each list is written the way a HubSpot PM would set its filters, and the same rules are evaluated here against
the local guests, so the member counts on the dashboard are real. Every ad-audience list starts from one base
rule: marketing_consent is true AND hs_email_optout is not true. A guest who didn't tick the box, or who opted
out, can never be a member.
"""

from collections import Counter
from dataclasses import dataclass, field

from app.models import Guest

# Published audience-size floors, so nobody expects a 50-guest demo to sync to an ad network.
AD_MINIMUMS = [("Meta (Facebook / Instagram)", 100), ("LinkedIn", 300), ("Google", 1000)]

BASE_RULES = [
    ("marketing_consent", "is equal to", "true"),
    ("hs_email_optout", "is not equal to", "true"),
]

GUEST_FIELD = {  # HubSpot property -> Guest attribute
    "age_range": "age_range",
    "trip_type": "trip_type",
    "budget_band": "budget_band",
    "lead_source_detail": "source",
    "zip": "zip",
}


@dataclass
class SuggestedList:
    name: str
    why: str
    rules: list[tuple[str, str, list[str]]]   # (property, "is any of", values) ANDed after the base rules
    purpose: str = "audience"                 # audience | suppression
    members: list[Guest] = field(default_factory=list)

    @property
    def filter_lines(self) -> list[str]:
        if self.purpose == "suppression":
            return ["marketing_consent is not equal to true", "OR hs_email_optout is equal to true"]
        lines = [f"{p} {op} {v}" for p, op, v in BASE_RULES]
        lines += [f"AND {p} is any of {', '.join(vals)}" for p, _, vals in self.rules]
        return lines

    def matches(self, g: Guest) -> bool:
        if self.purpose == "suppression":
            return not g.ad_eligible
        if not g.ad_eligible:
            return False
        return all(getattr(g, GUEST_FIELD[p]) in vals for p, _, vals in self.rules)


def top_zips(guests: list[Guest], n: int = 3) -> list[str]:
    counts = Counter(g.zip for g in guests if g.ad_eligible)
    return [z for z, _ in counts.most_common(n)]


def suggested_lists(guests: list[Guest]) -> list[SuggestedList]:
    zips = top_zips(guests) or ["(none yet)"]
    lists = [
        SuggestedList("Fairwind: Consenting guests (ads base)",
                      "The seed audience for Marketing Hub ads. Every other ad list narrows this one.", []),
        SuggestedList("Fairwind: Consented, 35–54, Europe, $5–10K",
                      "Prime-earning couples planning a European trip: one clear creative, one clear offer.",
                      [("age_range", "is any of", ["35-44", "45-54"]),
                       ("trip_type", "is any of", ["europe"]),
                       ("budget_band", "is any of", ["5k_10k"])]),
        SuggestedList("Fairwind: Honeymoon and group events",
                      "High intent and often higher budget; strong social and content angles.",
                      [("trip_type", "is any of", ["honeymoon", "group_event"])]),
        SuggestedList("Fairwind: Family vacations",
                      "Different creative and offer than couples travel.",
                      [("trip_type", "is any of", ["family"])]),
        SuggestedList("Fairwind: $10K+ trips", "Premium and luxury campaigns.",
                      [("budget_band", "is any of", ["10k_plus"])]),
        SuggestedList("Fairwind: Top zip cluster",
                      "Geo targeting that matches who actually walks in (the current top 3 consented zips).",
                      [("zip", "is any of", zips)]),
        SuggestedList("Fairwind: Social-sourced guests",
                      "Guests who found us on Instagram or Facebook; ties back to Marketing Hub's social tool.",
                      [("lead_source_detail", "is any of", ["instagram", "facebook"])]),
        SuggestedList("Fairwind: Exclusion, no ads",
                      "Suppression list. Use it to EXCLUDE these people from every ad audience; never sync it as a "
                      "targeting audience.", [], purpose="suppression"),
    ]
    for lst in lists:
        lst.members = [g for g in guests if lst.matches(g)]
    return lists
