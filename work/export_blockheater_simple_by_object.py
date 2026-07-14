#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    export_dat_with_options,
    group_rows,
    model_name_from_xml,
    write_check_csv,
    write_curve_csv,
)


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def read_blockheater_rows(input_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockHeater":
                rows_by_object[row.get("object_name", "BlockHeater")].append(row)
    return fieldnames, rows_by_object


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_blockheater_simple_by_object.py source.xml wide_input.txt [output_dir]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    model_safe = safe_name(model_name)
    fieldnames, rows_by_object = read_blockheater_rows(wide_path)

    for object_name, rows in sorted(rows_by_object.items()):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
            filtered_wide = Path(tmp.name)
        try:
            write_rows(filtered_wide, fieldnames, rows)
            stem = f"{model_safe}_BlockHeater_{safe_name(object_name)}_simple"
            dat_path = out_dir / f"{stem}.dat"
            csv_path = out_dir / f"{stem}.csv"
            check_path = out_dir / f"{stem}_point_check.csv"
            selected, counts = export_dat_with_options(
                filtered_wide,
                xml_path,
                dat_path,
                model_name,
                include_fixed_cards=False,
                include_hxs_comments=False,
                include_extra_liquid_props=False,
            )
            groups = group_rows(filtered_wide)
            write_curve_csv(filtered_wide, csv_path)
            write_check_csv(groups, selected, check_path)
            print(f"{object_name}: curves={len(selected)}, hot={counts['H']}, cold={counts['C']}")
            print(f"  DAT: {dat_path}")
            print(f"  CSV: {csv_path}")
            print(f"  CHECK: {check_path}")
        finally:
            filtered_wide.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
