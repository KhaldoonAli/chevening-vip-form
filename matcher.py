"""Matching and scoring engine: filters inventory and ranks units."""

from typing import Dict, Any, List, Optional, Tuple


def _date_lte(unit_date: str, target_date: str) -> bool:
    """Return True if unit is available on or before the target date."""
    if not unit_date or not target_date:
        return True
    return unit_date <= target_date


def _passes_hard_filters(unit: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Return True if unit passes all hard (mandatory) filters."""
    # City filter
    if filters["city"]:
        if unit["city"].lower() != filters["city"].lower():
            return False

    # Unit type filter
    if filters["unit_type"]:
        if unit["unit_type"] != filters["unit_type"]:
            return False

    # Budget filter (hard cap)
    if filters["budget_max_gbp"] is not None:
        if unit["rent_monthly_gbp"] > filters["budget_max_gbp"]:
            return False

    # Availability date
    if filters["available_from_by"]:
        if not _date_lte(unit["available_from"], filters["available_from_by"]):
            return False

    # Contract length — unit's minimum must not exceed what the lead wants
    if filters["min_contract_months"] is not None:
        if unit["min_contract_months"] > filters["min_contract_months"]:
            return False

    # Must-have amenities
    for amenity in filters.get("must_have", []):
        if not unit.get(amenity, False):
            return False

    # Commute constraints
    if filters["commute_walk_max_mins"] is not None:
        if unit["walk_mins_to_uni"] > filters["commute_walk_max_mins"]:
            return False
    if filters["commute_transit_max_mins"] is not None:
        if unit["transit_mins_to_uni"] > filters["commute_transit_max_mins"]:
            return False

    return True


def _score_unit(unit: Dict[str, Any], filters: Dict[str, Any]) -> float:
    """Score a unit — higher is better. Used to rank among passing units."""
    score = 0.0

    # Price: prefer cheaper (normalise against budget or use raw rent)
    budget = filters.get("budget_max_gbp")
    if budget:
        savings_pct = (budget - unit["rent_monthly_gbp"]) / budget
        score += savings_pct * 30  # up to 30 points for being cheaper
    else:
        # Without a budget, invert rent (lower rent = higher score)
        score += max(0, (2000 - unit["rent_monthly_gbp"]) / 2000) * 20

    # Amenity bonuses
    for amenity in ("gym", "bills_included", "cctv", "furnished"):
        if unit.get(amenity):
            score += 5

    # Commute: prefer shorter commute
    score += max(0, (60 - unit.get("walk_mins_to_uni", 60)) / 60) * 15
    score += max(0, (60 - unit.get("transit_mins_to_uni", 60)) / 60) * 10

    # Contract flexibility: shorter min is better
    score += max(0, (12 - unit.get("min_contract_months", 12)) / 12) * 5

    # Area match bonus
    area = filters.get("area", "")
    if area and area.lower() in unit.get("area", "").lower():
        score += 10

    return round(score, 2)


def _build_key_reasons(unit: Dict[str, Any], filters: Dict[str, Any]) -> List[str]:
    """Generate human-readable reasons this unit is a good match."""
    reasons = []

    if filters["city"] and unit["city"].lower() == filters["city"].lower():
        reasons.append(f"Located in {unit['city']}, {unit['area']}")

    if filters["unit_type"] and unit["unit_type"] == filters["unit_type"]:
        reasons.append(f"{unit['unit_type']} as requested")

    budget = filters.get("budget_max_gbp")
    if budget:
        if unit["rent_monthly_gbp"] <= budget:
            reasons.append(
                f"£{unit['rent_monthly_gbp']}/mo — within £{budget} budget "
                f"(saves £{budget - unit['rent_monthly_gbp']}/mo)"
            )

    matched_amenities = [
        a for a in filters.get("must_have", []) if unit.get(a)
    ]
    if matched_amenities:
        labels = [a.replace("_", " ").title() for a in matched_amenities]
        reasons.append(f"Has: {', '.join(labels)}")

    if unit.get("university_nearby"):
        reasons.append(
            f"{unit['walk_mins_to_uni']} min walk / "
            f"{unit['transit_mins_to_uni']} min transit to "
            f"{unit['university_nearby']}"
        )

    if not reasons:
        reasons.append(f"{unit['unit_type']} in {unit['city']}, {unit['area']}")

    return reasons[:4]


def _build_tradeoffs(unit: Dict[str, Any], filters: Dict[str, Any]) -> List[str]:
    """Identify tradeoffs / things the lead might not love."""
    tradeoffs = []

    for amenity in filters.get("must_have", []):
        if not unit.get(amenity):
            tradeoffs.append(f"No {amenity.replace('_', ' ')}")

    if filters.get("commute_walk_max_mins"):
        if unit["walk_mins_to_uni"] > filters["commute_walk_max_mins"]:
            tradeoffs.append(
                f"Walk is {unit['walk_mins_to_uni']} min "
                f"(wanted ≤{filters['commute_walk_max_mins']})"
            )

    budget = filters.get("budget_max_gbp")
    if budget and unit["rent_monthly_gbp"] == budget:
        tradeoffs.append("At the top of your budget")

    if not unit.get("bills_included"):
        if "bills_included" not in filters.get("must_have", []):
            tradeoffs.append("Bills not included — budget for utilities")

    if not tradeoffs:
        tradeoffs.append("None identified")

    return tradeoffs[:3]


def _suggest_relaxations(
    filters: Dict[str, Any],
    all_units: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """When no matches found, suggest concrete relaxations based on inventory."""
    suggestions: List[Dict[str, str]] = []

    # Try relaxing budget
    if filters.get("budget_max_gbp"):
        budget = filters["budget_max_gbp"]
        # Find cheapest unit that passes other filters
        relaxed = dict(filters, budget_max_gbp=None)
        candidates = [u for u in all_units if _passes_other_filters(u, relaxed, skip="budget")]
        if candidates:
            cheapest = min(candidates, key=lambda u: u["rent_monthly_gbp"])
            diff = cheapest["rent_monthly_gbp"] - budget
            if diff > 0:
                suggestions.append({
                    "change": "Increase budget",
                    "by": f"£{diff}",
                    "why": (
                        f"Cheapest matching unit is {cheapest['unit_id']} at "
                        f"£{cheapest['rent_monthly_gbp']}/mo in {cheapest['area']}, "
                        f"{cheapest['city']}"
                    ),
                })

    # Try removing amenity requirements
    for amenity in filters.get("must_have", []):
        relaxed_must = [a for a in filters["must_have"] if a != amenity]
        relaxed = dict(filters, must_have=relaxed_must)
        candidates = [u for u in all_units if _passes_hard_filters(u, relaxed)]
        if candidates:
            suggestions.append({
                "change": f"Drop '{amenity.replace('_', ' ')}' requirement",
                "by": "N/A",
                "why": f"{len(candidates)} unit(s) become available",
            })

    # Try different city
    if filters.get("city"):
        relaxed = dict(filters, city="")
        candidates = [u for u in all_units if _passes_hard_filters(u, relaxed)]
        if candidates:
            cities = sorted(set(u["city"] for u in candidates))
            suggestions.append({
                "change": "Consider other cities",
                "by": ", ".join(cities),
                "why": f"{len(candidates)} unit(s) available in: {', '.join(cities)}",
            })

    return suggestions[:4]


def _passes_other_filters(
    unit: Dict[str, Any],
    filters: Dict[str, Any],
    skip: str,
) -> bool:
    """Like _passes_hard_filters but skips one filter category."""
    f = dict(filters)
    if skip == "budget":
        f["budget_max_gbp"] = None
    elif skip == "city":
        f["city"] = ""
    elif skip == "unit_type":
        f["unit_type"] = ""
    return _passes_hard_filters(unit, f)


def match_lead(
    filters: Dict[str, Any],
    units: List[Dict[str, Any]],
    max_results: int = 3,
) -> Dict[str, Any]:
    """
    Match parsed lead filters against inventory units.

    Returns the full output dict ready for JSON serialisation.
    """
    # Filter
    passing = [u for u in units if _passes_hard_filters(u, filters)]

    # Score & rank
    scored: List[Tuple[float, Dict[str, Any]]] = [
        (_score_unit(u, filters), u) for u in passing
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build matches (max 3)
    matches = []
    for rank, (score, unit) in enumerate(scored[:max_results], start=1):
        matches.append({
            "rank": rank,
            "unit_id": unit["unit_id"],
            "agency_name": unit["agency_name"],
            "city": unit["city"],
            "area": unit["area"],
            "unit_type": unit["unit_type"],
            "rent_monthly_gbp": unit["rent_monthly_gbp"],
            "deposit_gbp": unit["deposit_gbp"],
            "available_from": unit["available_from"],
            "min_contract_months": unit["min_contract_months"],
            "key_reasons": _build_key_reasons(unit, filters),
            "tradeoffs": _build_tradeoffs(unit, filters),
        })

    # Build result
    result: Dict[str, Any] = {
        "clarifying_questions": [],
        "filters_applied": {
            "city": filters.get("city", ""),
            "unit_type": filters.get("unit_type", ""),
            "budget_max_gbp": filters.get("budget_max_gbp"),
            "available_from_by": filters.get("available_from_by", ""),
            "min_contract_months": filters.get("min_contract_months"),
            "must_have": filters.get("must_have", []),
            "commute_walk_max_mins": filters.get("commute_walk_max_mins"),
            "commute_transit_max_mins": filters.get("commute_transit_max_mins"),
        },
        "matches": matches,
        "no_match_reason": "",
        "suggested_relaxations": [],
    }

    if not matches:
        result["no_match_reason"] = (
            "No units in inventory match all your criteria."
        )
        result["suggested_relaxations"] = _suggest_relaxations(filters, units)
    elif len(matches) < max_results:
        result["no_match_reason"] = (
            f"Only {len(matches)} unit(s) matched — fewer than {max_results} "
            f"because the remaining inventory didn't pass your filters."
        )

    return result


def build_clarifying_response(raw_text: str) -> Dict[str, Any]:
    """Return a response asking clarifying questions when the lead is too vague."""
    return {
        "clarifying_questions": [
            "Which city are you looking in? (e.g., London, Manchester, Birmingham, Edinburgh)",
            "What is your maximum monthly budget in GBP? (e.g., £1200)",
            "What type of unit do you need? (Studio, 1Bed, or 2Bed)",
            "When do you need to move in? (e.g., September 2025)",
        ],
        "filters_applied": {
            "city": "",
            "unit_type": "",
            "budget_max_gbp": None,
            "available_from_by": "",
            "min_contract_months": None,
            "must_have": [],
            "commute_walk_max_mins": None,
            "commute_transit_max_mins": None,
        },
        "matches": [],
        "no_match_reason": "Lead request was unclear — clarifying questions sent.",
        "suggested_relaxations": [],
    }
