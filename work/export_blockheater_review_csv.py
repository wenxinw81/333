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


def safe_name(text):
    return re.sub(r"[/:\\\\]+", "_", text)


def group_blockheater_rows(wide_path):
    groups = defaultdict(list)
    with Path(wide_path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            if row.get("object_type") != "BlockHeater":
                continue
            key = (row.get("object_name", ""), row.get("HCURV_NO", ""))
            groups[key].append(row)
    return groups


def first_number(text):
    match = re.search(r"(\d+)", text or "")
    return int(match.group(1)) if match else 999


def write_review_csv(wide_path, out_dir):
    out_dir = Path(out_dir)
    groups = group_blockheater_rows(wide_path)
    rows_by_object = defaultdict(list)

    for (object_name, hcurv_no), rows in sorted(groups.items(), key=lambda item: (item[0][0], first_number(item[0][1]))):
        curve_rows = reduce_to_30(rows)
        side = "HOT" if curve_type(rows) == "H" else "COLD"
        set_no = first_number(hcurv_no)
        pressure = value(curve_rows[0], PRES_CANDIDATES) if curve_rows else None
        for index, row in enumerate(curve_rows, 1):
            rows_by_object[object_name].append(
                {
                    "object_name": object_name,
                    "curve_no": hcurv_no,
                    "set_no": set_no,
                    "side": side,
                    "pressure": pressure,
                    "point": index,
                    "Temperature": value(row, TEMP_CANDIDATES),
                    "Enthalpy_Total": value(row, H_TOTAL_CANDIDATES),
                    "WeightFractionVapor": value(row, QUALITY_TOTAL_CANDIDATES),
                    "Vapor_Density": value(row, RHO_VAPOR_CANDIDATES),
                    "Vapor_Viscosity": value(row, MU_VAPOR_CANDIDATES),
                    "Vapor_HeatCapacity": value(row, CP_VAPOR_CANDIDATES),
                    "Vapor_Conductivity": value(row, K_VAPOR_CANDIDATES),
                    "Vapor_Enthalpy": value(row, H_VAPOR_CANDIDATES),
                    "Vapor_MolecularWeight": value(row, MW_VAPOR_CANDIDATES),
                    "Liquid_Density": value(row, RHO_LIQUID_CANDIDATES),
                    "Liquid_Viscosity": value(row, MU_LIQUID_CANDIDATES),
                    "Liquid_HeatCapacity": value(row, CP_LIQUID_CANDIDATES),
                    "Liquid_Conductivity": value(row, K_LIQUID_CANDIDATES),
                    "Liquid_Enthalpy": value(row, H_LIQUID_CANDIDATES),
                    "Liquid_SurfaceTension": value(row, SIGMA_LIQUID_CANDIDATES),
                    "Liquid_LatentHeat": value(row, ["DHVLMXMS__PNH_LIQUID_KJ_PER_KG"]),
                    "Liquid_CriticalPressure": value(row, PC_LIQUID_CANDIDATES),
                    "Liquid_MolecularWeight": value(row, MW_LIQUID_CANDIDATES),
                }
            )

    fieldnames = [
        "object_name",
        "curve_no",
        "set_no",
        "side",
        "pressure",
        "point",
        "Temperature",
        "Enthalpy_Total",
        "WeightFractionVapor",
        "Vapor_Density",
        "Vapor_Viscosity",
        "Vapor_HeatCapacity",
        "Vapor_Conductivity",
        "Vapor_Enthalpy",
        "Vapor_MolecularWeight",
        "Liquid_Density",
        "Liquid_Viscosity",
        "Liquid_HeatCapacity",
        "Liquid_Conductivity",
        "Liquid_Enthalpy",
        "Liquid_SurfaceTension",
        "Liquid_LatentHeat",
        "Liquid_CriticalPressure",
        "Liquid_MolecularWeight",
    ]

    written = []
    for object_name, rows in rows_by_object.items():
        path = out_dir / f"BlockHeater_{safe_name(object_name)}_review.csv"
        with path.open("w", encoding="ascii", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: export_blockheater_review_csv.py wide_input.txt output_dir")
    for path in write_review_csv(sys.argv[1], sys.argv[2]):
        print(path)


if __name__ == "__main__":
    main()
