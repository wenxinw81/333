#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    export_dat_with_options,
    f,
    group_rows,
    model_name_from_xml,
    reduce_to_30,
    write_curve_csv,
)


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def read_blockradfrac_rows(input_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockRadfrac":
                hcurv_no = (row.get("HCURV_NO") or "").upper()
                if hcurv_no.startswith(("COND", "REB")):
                    rows_by_object[row.get("object_name", "BlockRadfrac")].append(row)
    return fieldnames, rows_by_object


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def curve_number(hcurv_no):
    match = re.search(r"(\d+)$", hcurv_no or "")
    return int(match.group(1)) if match else 999


def has_pnh_properties(rows):
    for row in rows:
        for key, value in row.items():
            if "__PNH" in key and f(value) is not None:
                return True
    return False


def fill_sparse_curves(rows, fieldnames):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("HCURV_NO", "")].append(row)

    by_curve_point = {
        curve: {row.get("NPOINT"): row for row in curve_rows}
        for curve, curve_rows in groups.items()
    }
    filled = [dict(row) for row in rows]
    filled_by_identity = {
        (row.get("HCURV_NO", ""), row.get("NPOINT", "")): row
        for row in filled
    }

    for prefix in ("COND", "REB"):
        curves = sorted(
            [curve for curve in groups if curve.upper().startswith(prefix)],
            key=curve_number,
        )
        rich_curves = [curve for curve in curves if has_pnh_properties(groups[curve])]
        for curve in curves:
            if has_pnh_properties(groups[curve]):
                continue
            before = [candidate for candidate in rich_curves if curve_number(candidate) < curve_number(curve)]
            after = [candidate for candidate in rich_curves if curve_number(candidate) > curve_number(curve)]
            left = before[-1] if before else None
            right = after[0] if after else None
            if not left and not right:
                continue
            for point, target in by_curve_point[curve].items():
                out = filled_by_identity[(curve, point)]
                left_row = by_curve_point.get(left, {}).get(point) if left else None
                right_row = by_curve_point.get(right, {}).get(point) if right else None
                for field in fieldnames:
                    if "__PNH" not in field and not field.startswith("MASSFLMX"):
                        continue
                    if f(out.get(field)) is not None:
                        continue
                    left_value = f(left_row.get(field)) if left_row else None
                    right_value = f(right_row.get(field)) if right_row else None
                    if left_value is not None and right_value is not None:
                        out[field] = str((left_value + right_value) / 2)
                    elif left_value is not None:
                        out[field] = str(left_value)
                    elif right_value is not None:
                        out[field] = str(right_value)
            curve_rows = sorted(
                [filled_by_identity[(curve, row.get("NPOINT", ""))] for row in by_curve_point[curve].values()],
                key=lambda row: int(row.get("NPOINT") or 0),
            )
            for field in fieldnames:
                if "__PNH" not in field and not field.startswith("MASSFLMX"):
                    continue
                for index, row in enumerate(curve_rows):
                    if f(row.get(field)) is not None:
                        continue
                    nearest = None
                    for distance in range(1, len(curve_rows)):
                        left_index = index - distance
                        right_index = index + distance
                        if left_index >= 0 and f(curve_rows[left_index].get(field)) is not None:
                            nearest = curve_rows[left_index].get(field)
                            break
                        if right_index < len(curve_rows) and f(curve_rows[right_index].get(field)) is not None:
                            nearest = curve_rows[right_index].get(field)
                            break
                    if nearest is not None:
                        row[field] = nearest
    return filled


def write_blockradfrac_check_csv(groups, selected, out_csv):
    selected_keys = {key for key, _ in selected}
    with Path(out_csv).open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["object_type", "object_name", "STREAMID", "HCURV_NO", "curve_type", "valid_points", "output_points", "in_dat", "status"])
        for key in sorted(groups):
            hcurv_no = key[3].upper()
            if not hcurv_no.startswith(("COND", "REB")):
                continue
            reduced = reduce_to_30(groups[key])
            status = "OK" if len(reduced) == 30 else "NOT_30"
            if status != "OK":
                side = "HOT" if hcurv_no.startswith("COND") else "COLD"
                writer.writerow([*key, side, len(reduced), len(reduced), "YES" if key in selected_keys else "NO", status])


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_blockradfrac_by_object.py source.xml wide_input.txt [output_dir]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    model_safe = safe_name(model_name)
    fieldnames, rows_by_object = read_blockradfrac_rows(wide_path)

    side_specs = [
        ("COND", "HOT", "H", "COND"),
        ("REB", "COLD", "C", "REB"),
    ]
    for object_name, rows in sorted(rows_by_object.items()):
        for prefix, label, side, stream_suffix in side_specs:
            side_rows = [row for row in rows if (row.get("HCURV_NO") or "").upper().startswith(prefix)]
            if not side_rows:
                continue
            side_rows = fill_sparse_curves(side_rows, fieldnames)
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
                filtered_wide = Path(tmp.name)
            try:
                write_rows(filtered_wide, fieldnames, side_rows)
                side_names = {
                    (object_name, side): f"{object_name}-{stream_suffix}",
                }
                stem = f"{model_safe}_BlockRadfrac_{safe_name(object_name)}_{label}"
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
                    prefer_curve_flow_types={"BlockRadfrac"},
                    side_stream_names=side_names,
                    component_cards_from_curve=True,
                )
                groups = group_rows(filtered_wide)
                write_curve_csv(filtered_wide, csv_path, xml_path=xml_path, side_stream_names=side_names)
                write_blockradfrac_check_csv(groups, selected, check_path)
                print(f"{object_name} {label}: curves={len(selected)}, hot={counts['H']}, cold={counts['C']}")
                print(f"  DAT: {dat_path}")
                print(f"  CSV: {csv_path}")
                print(f"  CHECK: {check_path}")
            finally:
                filtered_wide.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
