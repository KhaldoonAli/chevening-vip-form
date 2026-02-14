#!/usr/bin/env python3
"""
Fulgur Rental Lead Matching Engine

Usage:
    python main.py --lead "I need a 1bed in London under £1400 with gym" \
                   --inventory sample_inventory.csv

    python main.py --lead-file lead.txt --inventory units.csv

    # pipe lead text via stdin
    echo "Studio in Manchester, budget £800" | python main.py --inventory sample_inventory.csv
"""

import argparse
import json
import sys
import os

from inventory import load_inventory
from lead_parser import parse_lead, has_meaningful_filters
from matcher import match_lead, build_clarifying_response


def main():
    parser = argparse.ArgumentParser(
        description="Fulgur Rental Lead Matching Engine",
    )
    parser.add_argument(
        "--lead", "-l",
        type=str,
        default=None,
        help="Lead request as free text (inline).",
    )
    parser.add_argument(
        "--lead-file", "-f",
        type=str,
        default=None,
        help="Path to a text file containing the lead request.",
    )
    parser.add_argument(
        "--inventory", "-i",
        type=str,
        default="sample_inventory.csv",
        help="Path to the inventory CSV file (default: sample_inventory.csv).",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty-print JSON output.",
    )

    args = parser.parse_args()

    # Resolve lead text
    lead_text = args.lead
    if lead_text is None and args.lead_file:
        with open(args.lead_file, encoding="utf-8") as fh:
            lead_text = fh.read().strip()
    if lead_text is None:
        if not sys.stdin.isatty():
            lead_text = sys.stdin.read().strip()
        else:
            print("Error: provide lead text via --lead, --lead-file, or stdin.",
                  file=sys.stderr)
            sys.exit(1)

    if not lead_text:
        print("Error: lead text is empty.", file=sys.stderr)
        sys.exit(1)

    # Load inventory
    inv_path = args.inventory
    if not os.path.isabs(inv_path):
        inv_path = os.path.join(os.path.dirname(__file__) or ".", inv_path)

    units = load_inventory(inv_path)
    if not units:
        print(f"Warning: no valid units loaded from {inv_path}", file=sys.stderr)

    # Parse lead
    filters = parse_lead(lead_text)

    # If lead is too vague, ask clarifying questions
    if not has_meaningful_filters(filters):
        result = build_clarifying_response(lead_text)
    else:
        result = match_lead(filters, units)

    # Output
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
