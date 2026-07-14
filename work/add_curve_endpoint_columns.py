#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path


BASE_COLUMNS = ["object_type", "object_name", "HCURV_NO"]
POINT_COLUMN = "NPOINT"
TEMP_COLUMN = "TEMP_OUT_C"
MASSVFRA_COLUMN = "MASSVFRA__PNH_TOTAL"

DERIVED_COLUMNS = [
    "INLET_TEMP_C",
    "OUTLET_TEMP_C",
    "DELTA_TEMP_C",
    "HEAT_COOL_FLAG",
    "INLET_MASSVFRA_TOTAL",
    "OUTLET_MASSVFRA_TOTAL",
]


def point_number(row):
    try:
        return int(row[POINT_COLUMN])
    except (TypeError, ValueError):
        return 0


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_delta(delta):
    if delta is None:
        return ""
    return f"{delta:.12g}"


def classify(delta):
    if delta is None:
        return ""
    if delta > 0:
        return "HEATED"
    if delta < 0:
        return "COOLED"
    return "NO_CHANGE"


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: add_curve_endpoint_columns.py wide_input.txt wide_output.txt"
        )

    with Path(sys.argv[1]).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    grouped = defaultdict(list)
    for row in rows:
        key = tuple(row[column] for column in BASE_COLUMNS)
        grouped[key].append(row)

    derived_by_key = {}
    for key, group_rows in grouped.items():
        ordered = sorted(group_rows, key=point_number)
        first = ordered[0]
        last = ordered[-1]
        inlet_temp = first.get(TEMP_COLUMN, "")
        outlet_temp = last.get(TEMP_COLUMN, "")
        delta = None
        inlet_float = as_float(inlet_temp)
        outlet_float = as_float(outlet_temp)
        if inlet_float is not None and outlet_float is not None:
            delta = outlet_float - inlet_float
        derived_by_key[key] = {
            "INLET_TEMP_C": inlet_temp,
            "OUTLET_TEMP_C": outlet_temp,
            "DELTA_TEMP_C": format_delta(delta),
            "HEAT_COOL_FLAG": classify(delta),
            "INLET_MASSVFRA_TOTAL": first.get(MASSVFRA_COLUMN, ""),
            "OUTLET_MASSVFRA_TOTAL": last.get(MASSVFRA_COLUMN, ""),
        }

    insert_after = "DUTY_KW" if "DUTY_KW" in fieldnames else "NPOINT"
    insert_at = fieldnames.index(insert_after) + 1
    out_fields = fieldnames[:insert_at] + DERIVED_COLUMNS + fieldnames[insert_at:]

    with Path(sys.argv[2]).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, delimiter="\t")
        writer.writeheader()
        for row in rows:
            key = tuple(row[column] for column in BASE_COLUMNS)
            row.update(derived_by_key[key])
            writer.writerow({field: row.get(field, "") for field in out_fields})

    print(f"Rows: {len(rows)}")
    print("Derived curve endpoints:")
    for key in sorted(derived_by_key):
        print("\t".join(key + tuple(derived_by_key[key][column] for column in DERIVED_COLUMNS)))


if __name__ == "__main__":
    main()
