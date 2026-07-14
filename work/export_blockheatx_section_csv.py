#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from export_htri_compact import (
    CP_LIQUID_CANDIDATES,
    CP_VAPOR_CANDIDATES,
    H_LIQUID_CANDIDATES,
    H_TOTAL_CANDIDATES,
    H_VAPOR_CANDIDATES,
    K_LIQUID_CANDIDATES,
    K_VAPOR_CANDIDATES,
    MU_LIQUID_CANDIDATES,
    MU_VAPOR_CANDIDATES,
    MW_LIQUID_CANDIDATES,
    MW_VAPOR_CANDIDATES,
    PC_LIQUID_CANDIDATES,
    PRES_CANDIDATES,
    QUALITY_TOTAL_CANDIDATES,
    RHO_LIQUID_CANDIDATES,
    RHO_VAPOR_CANDIDATES,
    SIGMA_LIQUID_CANDIDATES,
    TEMP_CANDIDATES,
    curve_type,
    reduce_to_30,
    value,
)


GROUP_HEADER = [
    "Pressure", "", "", "Vapor Properties", "", "", "", "", "",
    "Liquid Properties", "", "", "", "", "", "", "", "",
]

FIELD_HEADER = [
    "Temperature(C)",
    "Enthalpy(kJ/kg)",
    "WeightFractionVapor",
    "Density(kg/m3)",
    "Viscosity(cP)",
    "HeatCapacity(kJ/kg-C)",
    "Conductivity(W/m-C)",
    "Enthalpy(kJ/kg)",
    "MolecularWeight",
    "Density(kg/m3)",
    "Viscosity(cP)",
    "HeatCapacity(kJ/kg-C)",
    "Conductivity(W/m-C)",
    "Enthalpy(kJ/kg)",
    "SurfaceTension(dyne/cm)",
    "LatentHeat(kJ/kg)",
    "CriticalPressure(barG)",
    "MolecularWeight",
]


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def first_number(text):
    match = re.search(r"(\d+)", text or "")
    return int(match.group(1)) if match else 999


def group_rows(wide_path):
    groups = defaultdict(list)
    with Path(wide_path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("object_type") != "BlockHeatx":
                continue
            groups[(row.get("object_name", ""), row.get("HCURV_NO", ""))].append(row)
    return groups


def row_values(row):
    return [
        value(row, TEMP_CANDIDATES),
        value(row, H_TOTAL_CANDIDATES),
        value(row, QUALITY_TOTAL_CANDIDATES),
        value(row, RHO_VAPOR_CANDIDATES),
        value(row, MU_VAPOR_CANDIDATES),
        value(row, CP_VAPOR_CANDIDATES),
        value(row, K_VAPOR_CANDIDATES),
        value(row, H_VAPOR_CANDIDATES),
        value(row, MW_VAPOR_CANDIDATES),
        value(row, RHO_LIQUID_CANDIDATES),
        value(row, MU_LIQUID_CANDIDATES),
        value(row, CP_LIQUID_CANDIDATES),
        value(row, K_LIQUID_CANDIDATES),
        value(row, H_LIQUID_CANDIDATES),
        value(row, SIGMA_LIQUID_CANDIDATES),
        value(row, ["DHVLMXMS__PNH_LIQUID_KJ_PER_KG"]),
        value(row, PC_LIQUID_CANDIDATES),
        value(row, MW_LIQUID_CANDIDATES),
    ]


def csv_value(value_):
    if value_ is None:
        return ""
    if abs(value_) == 0:
        return "0.0"
    return f"{value_:.12g}"


def write_object_csv(object_name, curves, out_dir):
    path = Path(out_dir) / f"BlockHeatx_{safe_name(object_name)}_section.csv"
    with path.open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle)
        for curve_no, rows in sorted(curves.items(), key=lambda item: first_number(item[0])):
            curve_rows = reduce_to_30(rows)
            if len(curve_rows) != 30:
                continue
            pressure = value(curve_rows[0], PRES_CANDIDATES)
            side = "HOT" if curve_type(rows) == "H" else "COLD"
            group_header = GROUP_HEADER[:]
            group_header[1] = csv_value(pressure)
            group_header[2] = "barG"
            writer.writerow([f"{object_name} {side} curve {curve_no}"])
            writer.writerow(group_header)
            writer.writerow(FIELD_HEADER)
            for row in curve_rows:
                writer.writerow([csv_value(item) for item in row_values(row)])
            writer.writerow([])
    return path


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: export_blockheatx_section_csv.py wide_input.txt output_dir")
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(dict)
    for (object_name, curve_no), rows in group_rows(sys.argv[1]).items():
        grouped[object_name][curve_no] = rows
    for object_name, curves in sorted(grouped.items()):
        print(write_object_csv(object_name, curves, out_dir))


if __name__ == "__main__":
    main()
