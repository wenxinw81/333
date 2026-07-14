#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    PRES_CANDIDATES,
    TEMP_CANDIDATES,
    curve_type,
    export_dat_with_options,
    f,
    group_rows,
    model_name_from_xml,
    reduce_to_30,
    value,
    write_check_csv,
    write_curve_csv,
)


MAX_EXPORTS_PER_OBJECT = 10
CURVES_PER_EXPORT = 3


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def read_blockmcompr_rows(input_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockMcompr":
                rows_by_object[row.get("object_name", "BlockMcompr")].append(row)
    return fieldnames, rows_by_object


def curve_number(hcurv_no):
    match = re.search(r"(\d+)$", hcurv_no or "")
    return int(match.group(1)) if match else 999


def has_property_values(rows):
    for row in rows:
        for key, value in row.items():
            if key.startswith(("TEMP__", "PRES__")):
                continue
            if ("__PNH" in key or key.startswith("MASSFLMX")) and f(value) is not None:
                return True
    return False


def fill_sparse_properties(rows, fieldnames):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("HCURV_NO", "")].append(row)

    rich_curves = [curve for curve, curve_rows in groups.items() if has_property_values(curve_rows)]
    if not rich_curves:
        return rows

    by_curve_point = {
        curve: {row.get("NPOINT"): row for row in curve_rows}
        for curve, curve_rows in groups.items()
    }
    filled = [dict(row) for row in rows]
    filled_by_identity = {
        (row.get("HCURV_NO", ""), row.get("NPOINT", "")): row
        for row in filled
    }

    for curve, curve_rows in groups.items():
        if has_property_values(curve_rows):
            continue
        source_curve = min(rich_curves, key=lambda candidate: abs(curve_number(candidate) - curve_number(curve)))
        for point in by_curve_point[curve]:
            target = filled_by_identity[(curve, point)]
            source = by_curve_point[source_curve].get(point)
            if not source:
                continue
            for field in fieldnames:
                if field.startswith(("TEMP__", "PRES__")):
                    continue
                if "__PNH" not in field and not field.startswith("MASSFLMX"):
                    continue
                if f(target.get(field)) is None and f(source.get(field)) is not None:
                    target[field] = source[field]
    return filled


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def sorted_curve_ids(rows):
    curves = sorted({row.get("HCURV_NO", "") for row in rows}, key=curve_number)
    return [curve for curve in curves if curve]


def write_selection_template(path, object_name, rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("HCURV_NO", "")].append(row)
    fields = [
        "object_name",
        "hcurv_no",
        "selected",
        "dat_no",
        "curve_type",
        "raw_points",
        "output_points",
        "temperature_in",
        "temperature_out",
        "pressure",
    ]
    with Path(path).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, curve in enumerate(sorted_curve_ids(rows), 1):
            curve_rows = groups[curve]
            reduced = reduce_to_30(curve_rows)
            first = reduced[0] if reduced else {}
            last = reduced[-1] if reduced else {}
            writer.writerow({
                "object_name": object_name,
                "hcurv_no": curve,
                "selected": "YES",
                "dat_no": (index - 1) // CURVES_PER_EXPORT + 1,
                "curve_type": "HOT" if curve_type(curve_rows) == "H" else "COLD",
                "raw_points": len(curve_rows),
                "output_points": len(reduced),
                "temperature_in": value(first, TEMP_CANDIDATES),
                "temperature_out": value(last, TEMP_CANDIDATES),
                "pressure": value(first, PRES_CANDIDATES),
            })


def read_selection(path, object_name):
    selected_by_dat = defaultdict(list)
    if not path:
        return selected_by_dat
    with Path(path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("object_name") != object_name:
                continue
            if (row.get("selected") or "").strip().upper() not in {"YES", "Y", "1", "TRUE"}:
                continue
            curve = (row.get("hcurv_no") or "").strip()
            if not curve:
                continue
            try:
                dat_no = int((row.get("dat_no") or "1").strip())
            except ValueError:
                dat_no = 1
            selected_by_dat[dat_no].append(curve)
    return selected_by_dat


def main():
    if len(sys.argv) not in {3, 4, 5}:
        raise SystemExit("Usage: export_blockmcompr_by_object.py source.xml wide_input.txt [output_dir] [selection_csv]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) >= 4 else Path("outputs")
    selection_csv = Path(sys.argv[4]) if len(sys.argv) == 5 else None
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    model_safe = safe_name(model_name)
    fieldnames, rows_by_object = read_blockmcompr_rows(wide_path)

    for object_name, rows in sorted(rows_by_object.items()):
        rows = fill_sparse_properties(rows, fieldnames)
        selection_path = out_dir / f"{model_safe}_BlockMcompr_{safe_name(object_name)}_curve_selection.csv"
        write_selection_template(selection_path, object_name, rows)
        selected_by_dat = read_selection(selection_csv, object_name) if selection_csv else {}
        if selected_by_dat:
            batches = [
                selected_by_dat[index]
                for index in sorted(selected_by_dat)
                if 1 <= index <= MAX_EXPORTS_PER_OBJECT
            ]
        else:
            curves = sorted_curve_ids(rows)
            batches = [
                curves[index:index + CURVES_PER_EXPORT]
                for index in range(0, len(curves), CURVES_PER_EXPORT)
            ][:MAX_EXPORTS_PER_OBJECT]
        print(f"  SELECT: {selection_path}")
        for batch_no, batch_curves in enumerate(batches, 1):
            batch_rows = [row for row in rows if row.get("HCURV_NO", "") in set(batch_curves)]
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
                filtered_wide = Path(tmp.name)
            try:
                write_rows(filtered_wide, fieldnames, batch_rows)
                stem = f"{model_safe}_BlockMcompr_{safe_name(object_name)}_{batch_no:02d}"
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
                    prefer_curve_flow_types={"BlockMcompr"},
                    component_cards_from_curve=True,
                )
                groups = group_rows(filtered_wide)
                write_curve_csv(filtered_wide, csv_path, xml_path=xml_path)
                write_check_csv(groups, selected, check_path)
                print(
                    f"{object_name} #{batch_no}: curves={len(selected)}, "
                    f"hot={counts['H']}, cold={counts['C']}, source={','.join(batch_curves)}"
                )
                print(f"  DAT: {dat_path}")
                print(f"  CSV: {csv_path}")
                print(f"  CHECK: {check_path}")
            finally:
                filtered_wide.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
