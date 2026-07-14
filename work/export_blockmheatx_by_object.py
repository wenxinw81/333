#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    curve_type,
    group_rows,
    model_name_from_xml,
    reduce_to_30,
    write_curve_csv,
)


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def read_blockmheatx_rows(input_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockMheatx":
                rows_by_object[row.get("object_name", "BlockMheatx")].append(row)
    return fieldnames, rows_by_object


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_blockmheatx_check_csv(groups, selected, out_csv):
    selected_keys = {key for key, _ in selected}
    with Path(out_csv).open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["object_type", "object_name", "STREAMID", "HCURV_NO", "curve_type", "valid_points", "output_points", "in_dat", "status"])
        for key in sorted(groups):
            side = curve_type(groups[key])
            if side not in {"H", "C"}:
                continue
            reduced = reduce_to_30(groups[key])
            status = "OK" if len(reduced) == 30 else "NOT_30"
            if status != "OK":
                writer.writerow([*key, "HOT" if side == "H" else "COLD", len(reduced), len(reduced), "YES" if key in selected_keys else "NO", status])


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_blockmheatx_by_object.py source.xml wide_input.txt [output_dir]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    model_safe = safe_name(model_name)
    fieldnames, rows_by_object = read_blockmheatx_rows(wide_path)

    for object_name, rows in sorted(rows_by_object.items()):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
            filtered_wide = Path(tmp.name)
        try:
            write_rows(filtered_wide, fieldnames, rows)
            stem = f"{model_safe}_BlockMheatx_{safe_name(object_name)}"
            csv_path = out_dir / f"{stem}.csv"
            check_path = out_dir / f"{stem}_point_check.csv"
            groups = group_rows(filtered_wide)
            selected = []
            counts = {"H": 0, "C": 0}
            for key in sorted(groups):
                side = curve_type(groups[key])
                if side in counts and len(reduce_to_30(groups[key])) == 30 and counts[side] < 12:
                    counts[side] += 1
                    selected.append((key, side))
            write_curve_csv(filtered_wide, csv_path, xml_path=xml_path)
            write_blockmheatx_check_csv(groups, selected, check_path)
            print(f"{object_name}: curves={len(selected)}, hot={counts['H']}, cold={counts['C']}")
            print(f"  CSV: {csv_path}")
            print(f"  CHECK: {check_path}")
        finally:
            filtered_wide.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
