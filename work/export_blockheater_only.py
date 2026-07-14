#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from pathlib import Path

from export_htri_compact import (
    export_dat,
    group_rows,
    model_name_from_xml,
    write_check_csv,
    write_curve_csv,
)


def filter_blockheater_wide(input_path, output_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [row for row in reader if row.get("object_type") == "BlockHeater"]

    with Path(output_path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_blockheater_only.py source.xml wide_input.txt [output_dir]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    safe_name = re.sub(r"[/:\\\\]+", "_", model_name)
    stem = f"{safe_name}_BlockHeater"

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        filtered_wide = Path(tmp.name)

    try:
        row_count = filter_blockheater_wide(wide_path, filtered_wide)
        dat_path = out_dir / f"{stem}.dat"
        csv_path = out_dir / f"{stem}.csv"
        check_path = out_dir / f"{stem}_point_check.csv"
        selected, counts = export_dat(filtered_wide, xml_path, dat_path, model_name)
        groups = group_rows(filtered_wide)
        write_curve_csv(filtered_wide, csv_path)
        write_check_csv(groups, selected, check_path)
    finally:
        filtered_wide.unlink(missing_ok=True)

    print(f"Filtered BlockHeater wide rows: {row_count}")
    print(f"DAT: {dat_path}")
    print(f"CSV: {csv_path}")
    print(f"CHECK: {check_path}")
    print(f"Curves: {len(selected)}, hot={counts['H']}, cold={counts['C']}")


if __name__ == "__main__":
    main()
