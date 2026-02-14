"""Parse free-text lead requests into structured filters."""

import re
from typing import Dict, Any, List, Optional


# Known cities in our inventory
KNOWN_CITIES = {
    "london", "manchester", "birmingham", "edinburgh",
}

# Known areas mapped to their city
KNOWN_AREAS: Dict[str, str] = {
    "shoreditch": "London",
    "camden": "London",
    "canary wharf": "London",
    "king's cross": "London",
    "kings cross": "London",
    "city centre": "",  # ambiguous — needs city context
    "fallowfield": "Manchester",
    "selly oak": "Birmingham",
    "old town": "Edinburgh",
    "newington": "Edinburgh",
    "stratford": "London",
    "rusholme": "Manchester",
}

UNIT_TYPE_PATTERNS = {
    "studio": "Studio",
    "1bed": "1Bed",
    "1 bed": "1Bed",
    "1-bed": "1Bed",
    "one bed": "1Bed",
    "one bedroom": "1Bed",
    "1 bedroom": "1Bed",
    "2bed": "2Bed",
    "2 bed": "2Bed",
    "2-bed": "2Bed",
    "two bed": "2Bed",
    "two bedroom": "2Bed",
    "2 bedroom": "2Bed",
}

AMENITY_KEYWORDS = {
    "gym": "gym",
    "bills included": "bills_included",
    "bills inc": "bills_included",
    "all bills": "bills_included",
    "inclusive": "bills_included",
    "cctv": "cctv",
    "security camera": "cctv",
    "furnished": "furnished",
    "fully furnished": "furnished",
}


def _extract_budget(text: str) -> Optional[int]:
    """Extract max monthly budget from text like '£1200', '1200 per month', 'budget 1200'."""
    patterns = [
        r"(?:budget|max|up\s+to|under|below|no\s+more\s+than)\s*[£$]?\s*(\d[\d,]*)",
        r"[£]\s*(\d[\d,]*)",
        r"(\d[\d,]*)\s*(?:per\s+month|pcm|pm|/month|monthly|a\s+month)",
        r"(\d{3,4})\s*(?:gbp|pounds?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def _extract_date(text: str) -> Optional[str]:
    """Extract an availability date (YYYY-MM-DD or month name)."""
    # ISO-style
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    # "September 2025", "Sep 2025"
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        "january": "01", "february": "02", "march": "03",
        "april": "04", "june": "06", "july": "07",
        "august": "08", "september": "09", "october": "10",
        "november": "11", "december": "12",
    }
    m = re.search(
        r"(?:from|by|before|starting|move\s+in)\s+(\w+)\s+(\d{4})",
        text, re.IGNORECASE,
    )
    if m:
        mon = m.group(1).lower()
        year = m.group(2)
        if mon in month_map:
            return f"{year}-{month_map[mon]}-01"
    # standalone month + year
    m = re.search(r"\b(\w+)\s+(\d{4})\b", text, re.IGNORECASE)
    if m:
        mon = m.group(1).lower()
        year = m.group(2)
        if mon in month_map:
            return f"{year}-{month_map[mon]}-01"
    return None


def _extract_contract_months(text: str) -> Optional[int]:
    """Extract minimum contract length."""
    m = re.search(r"(\d+)\s*month", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_commute(text: str):
    """Extract walk/transit max minutes."""
    walk = transit = None
    m = re.search(r"(\d+)\s*min(?:ute)?s?\s*walk", text, re.IGNORECASE)
    if m:
        walk = int(m.group(1))
    m = re.search(
        r"(\d+)\s*min(?:ute)?s?\s*(?:transit|commute|travel|transport|tube|bus)",
        text, re.IGNORECASE,
    )
    if m:
        transit = int(m.group(1))
    # generic "within X mins" — treat as transit
    if not walk and not transit:
        m = re.search(r"within\s+(\d+)\s*min", text, re.IGNORECASE)
        if m:
            transit = int(m.group(1))
    return walk, transit


def parse_lead(text: str) -> Dict[str, Any]:
    """Parse free-text lead into a structured filter dict."""
    lower = text.lower()

    # City
    city = ""
    for c in KNOWN_CITIES:
        if c in lower:
            city = c.title()
            break

    # Area
    area = ""
    for a, a_city in KNOWN_AREAS.items():
        if a in lower:
            area = a
            if not city and a_city:
                city = a_city
            break

    # Unit type
    unit_type = ""
    for pattern, utype in UNIT_TYPE_PATTERNS.items():
        if pattern in lower:
            unit_type = utype
            break

    # Budget
    budget = _extract_budget(text)

    # Available from
    avail = _extract_date(text)

    # Contract
    contract = _extract_contract_months(text)

    # Amenities
    must_have: List[str] = []
    for kw, amenity in AMENITY_KEYWORDS.items():
        if kw in lower and amenity not in must_have:
            must_have.append(amenity)

    # Commute
    walk_max, transit_max = _extract_commute(text)

    return {
        "city": city,
        "area": area,
        "unit_type": unit_type,
        "budget_max_gbp": budget,
        "available_from_by": avail or "",
        "min_contract_months": contract,
        "must_have": must_have,
        "commute_walk_max_mins": walk_max,
        "commute_transit_max_mins": transit_max,
        "raw_text": text,
    }


def has_meaningful_filters(filters: Dict[str, Any]) -> bool:
    """Return True if the parsed lead has at least one actionable filter."""
    return bool(
        filters["city"]
        or filters["unit_type"]
        or filters["budget_max_gbp"]
        or filters["available_from_by"]
        or filters["must_have"]
        or filters["commute_walk_max_mins"]
        or filters["commute_transit_max_mins"]
    )
