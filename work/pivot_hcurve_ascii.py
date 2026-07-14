#!/usr/bin/env python3
import csv
import sys
from collections import OrderedDict
from pathlib import Path


def make_column(row):
    variable = row["variable"]
    phase = row.get("PHASE", "")
    unit = row.get("unit", "")
    parts = [variable]
    if phase:
        parts.append(phase)
    if unit:
        parts.append(unit.replace("/", "_PER_"))
    return "_".join(parts)


def point_index(row):
    return row.get("NPOINT") or row.get("Point_No.") or ""


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: pivot_hcurve_ascii.py long_input.txt wide_output.txt")

    rows_by_key = OrderedDict()
    columns = []
    with Path(sys.argv[1]).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (
                row["object_type"],
                row["object_name"],
                row.get("STREAMID", ""),
                row["HCURV_NO"],
                point_index(row),
            )
            rows_by_key.setdefault(
                key,
                {
                    "object_type": row["object_type"],
                    "object_name": row["object_name"],
                    "STREAMID": row.get("STREAMID", ""),
                    "HCURV_NO": row["HCURV_NO"],
                    "NPOINT": point_index(row),
                },
            )
            column = make_column(row)
            if column not in columns:
                columns.append(column)
            rows_by_key[key][column] = row["value"]

    fields = ["object_type", "object_name", "STREAMID", "HCURV_NO", "NPOINT"] + columns
    with Path(sys.argv[2]).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for row in rows_by_key.values():
            writer.writerow({field: row.get(field, "") for field in fields})

    print(f"Wide rows: {len(rows_by_key)}")
    print(f"Wide columns: {len(fields)}")


if __name__ == "__main__":
    main()
