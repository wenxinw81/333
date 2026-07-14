#!/usr/bin/env python3
import csv
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    curve_type,
    export_dat_with_options,
    f,
    group_rows,
    local_name,
    model_name_from_xml,
    read_xml,
    reduce_to_30,
    write_check_csv,
    write_curve_csv,
)


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def direct_value(element):
    for child in list(element):
        if local_name(child.tag) == "Value":
            return child.text or ""
    return ""


def stream_temperatures(root):
    temps = {}
    for element in root.iter():
        if local_name(element.tag) != "StreamMaterial":
            continue
        name = element.attrib.get("name")
        if not name:
            continue
        for child in list(element):
            if local_name(child.tag) == "TEMP_OUT":
                temp = f(direct_value(child))
                if temp is not None:
                    temps[name] = temp
    return temps


def blockheatx_side_names(xml_path):
    root = read_xml(xml_path)
    temps = stream_temperatures(root)
    inlet_streams = defaultdict(list)
    for element in root.iter():
        if local_name(element.tag) != "Connection":
            continue
        dest = element.attrib.get("dest")
        stream = element.attrib.get("stream")
        if dest and stream:
            inlet_streams[dest].append(stream)

    names = {}
    for object_name, streams in inlet_streams.items():
        known = [(stream, temps[stream]) for stream in streams if stream in temps]
        if len(known) < 2:
            continue
        cold_stream = min(known, key=lambda item: item[1])[0]
        hot_stream = max(known, key=lambda item: item[1])[0]
        names[(object_name, "C")] = cold_stream
        names[(object_name, "H")] = hot_stream
    return names


def read_blockheatx_rows(input_path):
    with Path(input_path).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockHeatx":
                rows_by_object[row.get("object_name", "BlockHeatx")].append(row)
    return fieldnames, rows_by_object


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_blockheatx_check_csv(groups, selected, out_csv):
    selected_keys = {key for key, _ in selected}
    with Path(out_csv).open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["object_type", "object_name", "STREAMID", "HCURV_NO", "curve_type", "valid_points", "output_points", "in_dat", "status"])
        for key in sorted(groups):
            hcurv_no = key[3].upper()
            if not (hcurv_no.startswith("HOT") or hcurv_no.startswith("COLD")):
                continue
            reduced = reduce_to_30(groups[key])
            status = "OK" if len(reduced) == 30 else "NOT_30"
            if status != "OK":
                side = curve_type(groups[key])
                writer.writerow([*key, "HOT" if side == "H" else "COLD", len(reduced), len(reduced), "YES" if key in selected_keys else "NO", status])


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_blockheatx_by_object.py source.xml wide_input.txt [output_dir]")

    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = model_name_from_xml(xml_path)
    model_safe = safe_name(model_name)
    side_names = blockheatx_side_names(xml_path)
    fieldnames, rows_by_object = read_blockheatx_rows(wide_path)

    for object_name, rows in sorted(rows_by_object.items()):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
            filtered_wide = Path(tmp.name)
        try:
            write_rows(filtered_wide, fieldnames, rows)
            stem = f"{model_safe}_BlockHeatx_{safe_name(object_name)}"
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
                prefer_curve_flow_types={"BlockHeatx"},
                side_stream_names=side_names,
                component_cards_from_curve=True,
            )
            groups = group_rows(filtered_wide)
            write_curve_csv(filtered_wide, csv_path, xml_path=xml_path, side_stream_names=side_names)
            write_blockheatx_check_csv(groups, selected, check_path)
            print(f"{object_name}: curves={len(selected)}, hot={counts['H']}, cold={counts['C']}")
            print(f"  DAT: {dat_path}")
            print(f"  CSV: {csv_path}")
            print(f"  CHECK: {check_path}")
        finally:
            filtered_wide.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
