"""Inventory loader: reads a CSV file and returns typed unit dicts."""

import csv
from typing import List, Dict, Any


ALLOWED_UNIT_TYPES = {"Studio", "1Bed", "2Bed"}

BOOL_FIELDS = ("gym", "bills_included", "cctv", "furnished")
INT_FIELDS = ("rent_monthly_gbp", "deposit_gbp", "min_contract_months",
              "walk_mins_to_uni", "transit_mins_to_uni")


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("yes", "true", "1")


def _parse_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return 0


def load_inventory(csv_path: str) -> List[Dict[str, Any]]:
    """Load units from CSV, excluding shared rooms."""
    units: List[Dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            unit_type = row.get("unit_type", "").strip()
            if unit_type not in ALLOWED_UNIT_TYPES:
                continue  # Rule 3: exclude shared rooms
            unit: Dict[str, Any] = {
                "unit_id": row["unit_id"].strip(),
                "agency_name": row["agency_name"].strip(),
                "city": row["city"].strip(),
                "area": row["area"].strip(),
                "unit_type": unit_type,
                "available_from": row["available_from"].strip(),
                "university_nearby": row.get("university_nearby", "").strip(),
            }
            for f in INT_FIELDS:
                unit[f] = _parse_int(row.get(f, "0"))
            for f in BOOL_FIELDS:
                unit[f] = _parse_bool(row.get(f, "no"))
            units.append(unit)
    return units
