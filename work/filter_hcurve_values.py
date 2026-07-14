#!/usr/bin/env python3
import csv
import sys
from pathlib import Path


KEEP_PHASES = {
    "TEMP__PNH": {""},
    "TEMP__PNSH": {""},
    "TEMP__NH": {""},
    "TEMP_OUT": {""},
    "HMX__PNH": {"TOTAL", "VAPOR", "LIQUID"},
    "MASSVFRA__PNH": {"TOTAL"},
    "RHOMX__PNH": {"VAPOR", "LIQUID"},
    "MUMX__PNH": {"VAPOR", "LIQUID"},
    "CPMX__PNH": {"VAPOR", "LIQUID"},
    "KMX__PNH": {"VAPOR", "LIQUID"},
    "MWMX__PNH": {"VAPOR", "LIQUID"},
}


def should_keep_value(row):
    variable = row["variable"]
    phase = row.get("PHASE", "")
    return variable in KEEP_PHASES and phase in KEEP_PHASES[variable]


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


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: filter_hcurve_values.py long_input.txt filtered_wide_output.txt")

    rows_by_key = {}
    order = []
    columns = []

    with Path(sys.argv[1]).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (
                row["object_type"],
                row["object_name"],
                row["HCURV_NO"],
                row["NPOINT"],
            )
            if key not in rows_by_key:
                order.append(key)
                rows_by_key[key] = {
                    "object_type": row["object_type"],
                    "object_name": row["object_name"],
                    "HCURV_NO": row["HCURV_NO"],
                    "NPOINT": row["NPOINT"],
                }

            column = make_column(row)
            if column not in columns:
                columns.append(column)
            rows_by_key[key][column] = row["value"] if should_keep_value(row) else ""

    fields = ["object_type", "object_name", "HCURV_NO", "NPOINT"] + columns
    with Path(sys.argv[2]).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for key in order:
            row = rows_by_key[key]
            writer.writerow({field: row.get(field, "") for field in fields})

    print(f"Filtered wide rows: {len(order)}")
    print(f"Filtered wide columns: {len(fields)}")


if __name__ == "__main__":
    main()
