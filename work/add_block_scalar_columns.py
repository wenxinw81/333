#!/usr/bin/env python3
import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SCALAR_FIELDS = {
    "BAL_MASO_FLW": "TOTAL_MASS_FLOW_KG_PER_HR",
    "PDROP": "PRESSURE_DROP_KPA",
    "QCALC": "DUTY_KW",
}
STREAM_SCALAR_FIELDS = {
    "PDROP2": "PRESSURE_DROP_KPA",
}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def parse_xml_with_wrapper(path):
    data = Path(path).read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        raw = data.decode("utf-16")
    else:
        raw = data.decode("utf-8-sig")
    raw = re.sub(r"<\?xml[^>]*\?>", "", raw).strip()
    return ET.fromstring(f"<ROOT>{raw}</ROOT>")


def direct_value(element):
    for child in list(element):
        if local_name(child.tag) == "Value":
            return child.text or ""
    return ""


def index_items(element, tag_name):
    for child in list(element):
        if local_name(child.tag) == tag_name:
            items = child.attrib.get("items", "")
            return [item.strip() for item in items.split(",") if item.strip()]
    return []


def object_key(element):
    return (local_name(element.tag), element.attrib.get("name", ""))


def extract_object_scalars(root):
    scalars = {}
    stream_scalars = {}
    for element in root.iter():
        name = element.attrib.get("name")
        if not name:
            continue
        found = {}
        found_by_stream = {}
        for child in list(element):
            tag = local_name(child.tag)
            if tag in SCALAR_FIELDS:
                found[SCALAR_FIELDS[tag]] = direct_value(child)
            if tag in STREAM_SCALAR_FIELDS:
                streams = index_items(child, "STREAMID")
                values = [value.strip() for value in direct_value(child).split(",")]
                if streams:
                    for index, stream in enumerate(streams):
                        if index < len(values):
                            found_by_stream.setdefault(stream, {})[STREAM_SCALAR_FIELDS[tag]] = values[index]
        if found:
            scalars[object_key(element)] = found
        if found_by_stream:
            for stream, values in found_by_stream.items():
                stream_scalars[(local_name(element.tag), name, stream)] = values
    return scalars, stream_scalars


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: add_block_scalar_columns.py source.xml wide_input.txt wide_output.txt"
        )

    root = parse_xml_with_wrapper(sys.argv[1])
    scalars, stream_scalars = extract_object_scalars(root)
    scalar_columns = list(SCALAR_FIELDS.values())

    with Path(sys.argv[2]).open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fields = list(reader.fieldnames or [])
        insert_at = fields.index("HCURV_NO") if "HCURV_NO" in fields else len(fields)
        out_fields = fields[:insert_at] + scalar_columns + fields[insert_at:]

        with Path(sys.argv[3]).open("w", encoding="ascii", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=out_fields, delimiter="\t")
            writer.writeheader()
            for row in reader:
                object_scalars = scalars.get((row["object_type"], row["object_name"]), {})
                object_stream_scalars = stream_scalars.get((row["object_type"], row["object_name"], row.get("STREAMID", "")), {})
                for column in scalar_columns:
                    row[column] = object_stream_scalars.get(column, object_scalars.get(column, ""))
                writer.writerow({field: row.get(field, "") for field in out_fields})

    print(f"Objects with scalar fields: {len(scalars)}")
    for key in sorted(scalars):
        print(f"{key[0]} {key[1]}: {scalars[key]}")
    print(f"Objects with stream scalar fields: {len(stream_scalars)}")


if __name__ == "__main__":
    main()
