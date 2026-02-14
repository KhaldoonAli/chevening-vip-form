#!/usr/bin/env python3
"""Tests for the rental lead matching engine."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from inventory import load_inventory
from lead_parser import parse_lead, has_meaningful_filters
from matcher import match_lead, build_clarifying_response


CSV_PATH = os.path.join(os.path.dirname(__file__), "sample_inventory.csv")


class TestInventoryLoader(unittest.TestCase):
    def test_loads_units(self):
        units = load_inventory(CSV_PATH)
        self.assertGreater(len(units), 0)

    def test_excludes_shared_rooms(self):
        units = load_inventory(CSV_PATH)
        for u in units:
            self.assertIn(u["unit_type"], ("Studio", "1Bed", "2Bed"),
                          f"Shared room found: {u['unit_id']}")

    def test_bool_fields_parsed(self):
        units = load_inventory(CSV_PATH)
        for u in units:
            self.assertIsInstance(u["gym"], bool)
            self.assertIsInstance(u["bills_included"], bool)
            self.assertIsInstance(u["furnished"], bool)

    def test_int_fields_parsed(self):
        units = load_inventory(CSV_PATH)
        for u in units:
            self.assertIsInstance(u["rent_monthly_gbp"], int)
            self.assertIsInstance(u["deposit_gbp"], int)


class TestLeadParser(unittest.TestCase):
    def test_parse_city(self):
        f = parse_lead("I need a flat in London")
        self.assertEqual(f["city"], "London")

    def test_parse_budget_pound_sign(self):
        f = parse_lead("Budget £1200 per month")
        self.assertEqual(f["budget_max_gbp"], 1200)

    def test_parse_budget_keyword(self):
        f = parse_lead("up to 900 per month")
        self.assertEqual(f["budget_max_gbp"], 900)

    def test_parse_unit_type_studio(self):
        f = parse_lead("Looking for a studio")
        self.assertEqual(f["unit_type"], "Studio")

    def test_parse_unit_type_1bed(self):
        f = parse_lead("1 bedroom apartment")
        self.assertEqual(f["unit_type"], "1Bed")

    def test_parse_unit_type_2bed(self):
        f = parse_lead("two bedroom flat")
        self.assertEqual(f["unit_type"], "2Bed")

    def test_parse_amenities(self):
        f = parse_lead("Must have gym and bills included, furnished")
        self.assertIn("gym", f["must_have"])
        self.assertIn("bills_included", f["must_have"])
        self.assertIn("furnished", f["must_have"])

    def test_parse_date(self):
        f = parse_lead("Move in September 2025")
        self.assertEqual(f["available_from_by"], "2025-09-01")

    def test_parse_walk_commute(self):
        f = parse_lead("Within 15 minutes walk")
        self.assertEqual(f["commute_walk_max_mins"], 15)

    def test_has_meaningful_filters_true(self):
        f = parse_lead("Studio in Manchester under £800")
        self.assertTrue(has_meaningful_filters(f))

    def test_has_meaningful_filters_false(self):
        f = parse_lead("hello world random text")
        self.assertFalse(has_meaningful_filters(f))


class TestMatcher(unittest.TestCase):
    def setUp(self):
        self.units = load_inventory(CSV_PATH)

    def test_basic_match_london_1bed(self):
        filters = parse_lead("1 bed in London under £1400 with gym")
        result = match_lead(filters, self.units)
        self.assertGreater(len(result["matches"]), 0)
        self.assertLessEqual(len(result["matches"]), 3)
        for m in result["matches"]:
            self.assertEqual(m["city"], "London")
            self.assertEqual(m["unit_type"], "1Bed")
            self.assertLessEqual(m["rent_monthly_gbp"], 1400)

    def test_basic_match_manchester_studio(self):
        filters = parse_lead("Studio in Manchester, budget £800")
        result = match_lead(filters, self.units)
        self.assertGreater(len(result["matches"]), 0)
        for m in result["matches"]:
            self.assertEqual(m["city"], "Manchester")
            self.assertEqual(m["unit_type"], "Studio")
            self.assertLessEqual(m["rent_monthly_gbp"], 800)

    def test_no_match_returns_relaxations(self):
        filters = parse_lead("Studio in London under £200 with gym")
        result = match_lead(filters, self.units)
        self.assertEqual(len(result["matches"]), 0)
        self.assertNotEqual(result["no_match_reason"], "")
        self.assertGreater(len(result["suggested_relaxations"]), 0)

    def test_max_three_matches(self):
        filters = parse_lead("Any flat in London")
        result = match_lead(filters, self.units)
        self.assertLessEqual(len(result["matches"]), 3)

    def test_shared_rooms_never_returned(self):
        filters = parse_lead("Cheapest room anywhere")
        result = match_lead(filters, self.units)
        for m in result["matches"]:
            self.assertIn(m["unit_type"], ("Studio", "1Bed", "2Bed"))

    def test_clarifying_questions_for_vague_input(self):
        result = build_clarifying_response("asdf")
        self.assertGreater(len(result["clarifying_questions"]), 0)
        self.assertEqual(len(result["matches"]), 0)

    def test_output_schema(self):
        """Verify the output dict has all required keys."""
        filters = parse_lead("1bed in Birmingham")
        result = match_lead(filters, self.units)
        required_keys = {
            "clarifying_questions", "filters_applied", "matches",
            "no_match_reason", "suggested_relaxations",
        }
        self.assertTrue(required_keys.issubset(result.keys()))
        filter_keys = {
            "city", "unit_type", "budget_max_gbp", "available_from_by",
            "min_contract_months", "must_have",
            "commute_walk_max_mins", "commute_transit_max_mins",
        }
        self.assertTrue(filter_keys.issubset(result["filters_applied"].keys()))

    def test_match_fields_present(self):
        filters = parse_lead("1bed in Edinburgh")
        result = match_lead(filters, self.units)
        if result["matches"]:
            m = result["matches"][0]
            for key in ("rank", "unit_id", "agency_name", "city", "area",
                        "unit_type", "rent_monthly_gbp", "deposit_gbp",
                        "available_from", "min_contract_months",
                        "key_reasons", "tradeoffs"):
                self.assertIn(key, m, f"Missing key: {key}")


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.units = load_inventory(CSV_PATH)

    def test_bills_included_filter(self):
        filters = parse_lead("1bed Manchester bills included under £1000")
        result = match_lead(filters, self.units)
        for m in result["matches"]:
            # Find the unit in our loaded data to verify
            unit = next(u for u in self.units if u["unit_id"] == m["unit_id"])
            self.assertTrue(unit["bills_included"])

    def test_contract_length_filter(self):
        filters = parse_lead("1bed Birmingham 6 month contract")
        result = match_lead(filters, self.units)
        for m in result["matches"]:
            self.assertLessEqual(m["min_contract_months"], 6)

    def test_availability_date_filter(self):
        filters = parse_lead("Studio available from August 2025 in Manchester")
        result = match_lead(filters, self.units)
        for m in result["matches"]:
            self.assertLessEqual(m["available_from"], "2025-08-01")


if __name__ == "__main__":
    unittest.main()
