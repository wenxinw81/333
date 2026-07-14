#!/usr/bin/env python3
import csv
import re
import sys
import xml.etree.ElementTree as ET
from itertools import product
from pathlib import Path


XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


def split_items(text):
    if text is None or text == "":
        return []
    return [item.strip() for item in text.split(",")]


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


def dimension_children(element):
    dims = []
    for child in list(element):
        if local_name(child.tag) == "Value":
            continue
        if child.attrib.get(XSI_TYPE) == "EnumerationIndex" and "items" in child.attrib:
            dims.append((local_name(child.tag), split_items(child.attrib["items"])))
    return dims


def direct_value(element):
    for child in list(element):
        if local_name(child.tag) == "Value":
            return child.text or ""
    return ""


def nearest_object(element, parent):
    while parent.get(element) is not None:
        element = parent[element]
        if element.attrib.get("name"):
            return local_name(element.tag), element.attrib.get("name")
    return "", ""


def build_parent_map(root):
    return {child: parent for parent in root.iter() for child in list(parent)}


def extract_rows(root):
    parent = build_parent_map(root)
    rows = []
    warnings = []

    for element in root.iter():
        dims = dimension_children(element)
        if not any(name == "HCURV_NO" for name, _ in dims):
            continue

        values = split_items(direct_value(element))
        expected = 1
        for _, items in dims:
            expected *= max(len(items), 1)

        object_type, object_name = nearest_object(element, parent)
        variable = local_name(element.tag)
        domain = element.attrib.get("domain", "")
        unit = element.attrib.get("unit", "")

        if expected != len(values):
            warnings.append(
                f"{object_type}:{object_name}:{variable} expected {expected} values, got {len(values)}"
            )

        dim_names = [name for name, _ in dims]
        dim_items = [items for _, items in dims]
        combinations = list(product(*dim_items))

        for index, combo in enumerate(combinations):
            value = values[index] if index < len(values) else ""
            row = {
                "object_type": object_type,
                "object_name": object_name,
                "variable": variable,
                "domain": domain,
                "unit": unit,
                "value": value,
            }
            for dim_name, dim_value in zip(dim_names, combo):
                row[dim_name] = dim_value
            rows.append(row)

    return rows, warnings


def write_ascii(rows, out_path):
    dim_columns = []
    for row in rows:
        for key in row:
            if key not in {"object_type", "object_name", "variable", "domain", "unit", "value"}:
                if key not in dim_columns:
                    dim_columns.append(key)

    priority = ["HCURV_NO", "NPOINT", "PHASE", "COMPONENTS", "SUBSTREAM"]
    dim_columns = sorted(dim_columns, key=lambda key: (priority.index(key) if key in priority else 99, key))
    fields = ["object_type", "object_name", "variable", "domain", "unit"] + dim_columns + ["value"]

    with Path(out_path).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: extract_hcurve_ascii.py input.xml output.txt")
    root = parse_xml_with_wrapper(sys.argv[1])
    rows, warnings = extract_rows(root)
    write_ascii(rows, sys.argv[2])
    print(f"HCURVE rows: {len(rows)}")
    print(f"Warnings: {len(warnings)}")
    for warning in warnings[:20]:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
