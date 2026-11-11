"""The "Ideal Traveler Profile": what consented guests have in common. Non-consenting guests only appear in the
operational totals, never in the profile."""

from collections import Counter

from app import choices
from app.models import Guest


def totals(guests: list[Guest]) -> dict[str, int]:
    return {
        "checkins": sum(g.checkin_count for g in guests),
        "repeat_guests": sum(1 for g in guests if g.checkin_count > 1),
        "guests": len(guests),
        "consented": sum(1 for g in guests if g.ad_eligible),
        "declined": sum(1 for g in guests if not g.marketing_consent and g.opted_out_at is None),
        "opted_out": sum(1 for g in guests if g.opted_out_at is not None or g.email_optout),
    }


def _breakdown(values, options=None, top=None):
    counts = Counter(values)
    if options:  # keep the form's natural order, show zero bars too
        rows = [(choices.label(options, v), counts.get(v, 0)) for v, _ in options]
    else:
        rows = [(k, n) for k, n in counts.most_common(top)]
    return {"labels": [r[0] for r in rows], "counts": [r[1] for r in rows]}


def ideal_traveler(guests: list[Guest]) -> dict:
    eligible = [g for g in guests if g.ad_eligible]
    profile = {
        "zips": _breakdown([g.zip for g in eligible], top=6),
        "ages": _breakdown([g.age_range for g in eligible], choices.AGE_RANGES),
        "trips": _breakdown([g.trip_type for g in eligible], choices.TRIP_TYPES),
        "budgets": _breakdown([g.budget_band for g in eligible], choices.BUDGET_BANDS),
        "sources": _breakdown([g.source for g in eligible], choices.SOURCES),
        "size": len(eligible),
    }
    profile["headline"] = headline(eligible)
    return profile


def headline(eligible: list[Guest]) -> str:
    """One plain sentence a travel owner can repeat: the most common answer in each field."""
    if not eligible:
        return "No consented guests yet."

    def top(attr, options):
        value, _ = Counter(getattr(g, attr) for g in eligible).most_common(1)[0]
        return choices.label(options, value)

    zip_code, _ = Counter(g.zip for g in eligible).most_common(1)[0]
    return (f"Most often: {top('age_range', choices.AGE_RANGES)}, planning a {_trip_words(top('trip_type', choices.TRIP_TYPES))} "
            f"trip at {top('budget_band', choices.BUDGET_BANDS)}, near {zip_code}. "
            f"Top source: {top('source', choices.SOURCES)}.")


def _trip_words(label: str) -> str:
    """'Beach' -> 'beach', but keep place names capitalized ('Europe')."""
    return label if label == "Europe" else label.lower()
