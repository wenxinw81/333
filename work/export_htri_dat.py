#!/usr/bin/env python3
import csv
import sys
from collections import defaultdict
from pathlib import Path


META_COLUMNS = {
    "object_type",
    "object_name",
    "TOTAL_MASS_FLOW_KG_PER_HR",
    "PRESSURE_DROP_KPA",
    "DUTY_KW",
    "INLET_TEMP_C",
    "OUTLET_TEMP_C",
    "DELTA_TEMP_C",
    "HEAT_COOL_FLAG",
    "INLET_MASSVFRA_TOTAL",
    "OUTLET_MASSVFRA_TOTAL",
    "HCURV_NO",
    "NPOINT",
}


def f(value, default=None):
    if value in (None, "", "*"):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def fmt_e(value):
    if value is None:
        return "  0.00000E+00"
    return f"{value:13.5E}"


def fmt_fixed(value, width=12, precision=4):
    if value is None:
        return " " * width
    return f"{value:{width}.{precision}f}"


def write_series(lines, title, values, width=12, precision=4, per_line=5):
    if not any(value is not None for value in values):
        return False
    lines.append(f"*   {title}")
    for i in range(0, len(values), per_line):
        chunk = values[i : i + per_line]
        lines.append("    ," + ",".join(fmt_fixed(v, width, precision) for v in chunk))
    return True


def sorted_group_rows(rows):
    return sorted(rows, key=lambda row: int(row["NPOINT"]))


def reduce_to_30_points(rows):
    if len(rows) <= 30:
        return rows

    remove_count = len(rows) - 30
    removable = list(range(4, len(rows) - 1, 2))
    if len(removable) < remove_count:
        removable.extend(index for index in range(5, len(rows) - 1, 2) if index not in removable)

    remove_indexes = set(removable[:remove_count])
    return [row for index, row in enumerate(rows) if index not in remove_indexes]


def rows_with_valid_temperature(rows):
    valid = [row for row in rows if f(row.get("TEMP_OUT_C")) is not None]
    return valid or rows


def column_values(rows, column):
    return [f(row.get(column)) for row in rows]


def compact_name(prefix):
    return "HotFluid    " if prefix == "H" else "ColdFluid   "


def prepared_rows(rows):
    return reduce_to_30_points(rows_with_valid_temperature(sorted_group_rows(rows)))


def curve_prefix(rows):
    rows = prepared_rows(rows)
    if not rows:
        return "C"
    inlet_temp = f(rows[0].get("TEMP_OUT_C"))
    outlet_temp = f(rows[-1].get("TEMP_OUT_C"))
    if inlet_temp is not None and outlet_temp is not None and outlet_temp < inlet_temp:
        return "H"
    return "C"


def export_curve(lines, object_type, object_name, hcurv_no, rows, include_process, include_fluid):
    rows = prepared_rows(rows)
    first = rows[0]
    last = rows[-1]

    inlet_temp = f(first.get("TEMP_OUT_C"))
    outlet_temp = f(last.get("TEMP_OUT_C"))
    delta = None if inlet_temp is None or outlet_temp is None else outlet_temp - inlet_temp
    is_hot = delta is not None and delta < 0
    prefix = "H" if is_hot else "C"
    label = "HOT" if is_hot else "COLD"

    flow = f(first.get("TOTAL_MASS_FLOW_KG_PER_HR"))
    inlet_quality = f(first.get("MASSVFRA__PNH_TOTAL"))
    outlet_quality = f(last.get("MASSVFRA__PNH_TOTAL"))
    pressure = f(first.get("PRES_OUT_MPAG"))
    npoints = len(rows)

    if include_process:
        lines.append("* ")
        lines.append(f"* {label} STREAM PROCESS DATA")
        lines.append(
            f"* PROCESS DATA FROM ASPEN BLOCK ID= {object_name}, CURVE TYPE={label}, CURV {hcurv_no:>3}"
        )
        lines.append("*   TOTAL FLOW RATE KG/SEC          ")
        lines.append("*   WEIGHT FRACTION VAPOR AT INLET")
        lines.append("*   WEIGHT FRACTION VAPOR AT OUTLET")
        lines.append("*   TEMPERATURE AT INLET C               ")
        lines.append("*   TEMPERATURE AT OUTLET C               ")
        lines.append("*   ABSOLUTE PRESSURE AT INLET KPA             ")
        lines.append(
            f"{prefix}PRO,{fmt_e(flow)},{fmt_e(inlet_quality)},{fmt_e(outlet_quality)},"
            f"{fmt_e(inlet_temp)},{fmt_e(outlet_temp)}"
        )
        lines.append(f"    ,{fmt_e(pressure)}")

    lines.append("* ")
    if include_fluid:
        lines.append(f"* {label} STREAM PROPERTY DATA")
        lines.append(f"{prefix}FLU, '{compact_name(prefix)}', , , , ,  {npoints}")
    lines.append(
        f"* PROPERTY DATA FROM ASPEN BLOCK ID= {object_name}, CURVE TYPE={label}, CUR {hcurv_no:>3}"
    )
    lines.append("*   REFERENCE PRESSURE NUMBER, REFERENCE PRESSURE KPA             ")
    q_card = "HOTQ" if prefix == "H" else "COLDQ"
    lines.append(f"{q_card},   1,{fmt_e(pressure)}")
    write_series(lines, "TEMPERATURE C               ", column_values(rows, "TEMP_OUT_C"), 12, 2)
    write_series(lines, "ENTHALPY KJ/KG           ", column_values(rows, "HMX__PNH_TOTAL_KJ_PER_KG"), 12, 1)
    write_series(lines, "QUALITY", column_values(rows, "MASSVFRA__PNH_TOTAL"), 12, 4)

    vapor_block = []
    wrote_vapor = False
    wrote_vapor |= write_series(vapor_block, "DENSITY KG/CUM                      ", column_values(rows, "RHOMX__PNH_VAPOR_KG_PER_CUM"), 12, 4)
    wrote_vapor |= write_series(vapor_block, "VISCOSITY MN-SEC/SQM                ", column_values(rows, "MUMX__PNH_VAPOR_CP"), 12, 4)
    wrote_vapor |= write_series(vapor_block, "CONDUCTIVITY WATT/M-K               ", column_values(rows, "KMX__PNH_VAPOR_WATT_PER_M-K"), 12, 4)
    wrote_vapor |= write_series(vapor_block, "HEAT CAPACITY KJ/KG-K               ", column_values(rows, "CPMX__PNH_VAPOR_KJ_PER_KG-K"), 12, 4)
    wrote_vapor |= write_series(vapor_block, "ENTHALPY KJ/KG                      ", column_values(rows, "HMX__PNH_VAPOR_KJ_PER_KG"), 12, 1)
    wrote_vapor |= write_series(vapor_block, "MOLECULAR WEIGHT                    ", column_values(rows, "MWMX__PNH_VAPOR"), 12, 4)
    if wrote_vapor:
        lines.append("* ")
        lines.append(f"* {label} STREAM VAPOR PROPERTIES PROFILE")
        lines.append("*   REFERENCE PRESSURE NUMBER")
        lines.append(f"{prefix}PVA,   1")
        lines.extend(vapor_block)

    liquid_block = []
    wrote_liquid = False
    wrote_liquid |= write_series(liquid_block, "DENSITY KG/CUM                      ", column_values(rows, "RHOMX__PNH_LIQUID_KG_PER_CUM"), 12, 2)
    wrote_liquid |= write_series(liquid_block, "VISCOSITY MN-SEC/SQM                ", column_values(rows, "MUMX__PNH_LIQUID_CP"), 12, 4)
    wrote_liquid |= write_series(liquid_block, "CONDUCTIVITY WATT/M-K               ", column_values(rows, "KMX__PNH_LIQUID_WATT_PER_M-K"), 12, 4)
    wrote_liquid |= write_series(liquid_block, "HEAT CAPACITY KJ/KG-K               ", column_values(rows, "CPMX__PNH_LIQUID_KJ_PER_KG-K"), 12, 4)
    wrote_liquid |= write_series(liquid_block, "ENTHALPY KJ/KG                      ", column_values(rows, "HMX__PNH_LIQUID_KJ_PER_KG"), 12, 1)
    wrote_liquid |= write_series(liquid_block, "SURFACE TENSION MN/M                ", column_values(rows, "SIGMAMX__PNH_LIQUID_DYNE_PER_CM"), 12, 4)
    wrote_liquid |= write_series(liquid_block, "MOLECULAR WEIGHT                    ", column_values(rows, "MWMX__PNH_LIQUID"), 12, 4)
    if wrote_liquid:
        lines.append("* ")
        lines.append(f"* {label} STREAM LIQUID PROPERTIES PROFILE")
        lines.append("*   REFERENCE PRESSURE NUMBER")
        lines.append(f"{prefix}PLI,   1")
        lines.extend(liquid_block)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: export_htri_dat.py wide_input.txt model_name output.dat")

    input_path, model_name, output_path = sys.argv[1:]
    with Path(input_path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        groups = defaultdict(list)
        for row in reader:
            key = (row["object_type"], row["object_name"], row["HCURV_NO"])
            groups[key].append(row)

    lines = [
        "* HTRI process and physical property input data",
        "* generated by APToHTRI",
        "* HTRI Export Program (hcurve_export)",
        f"* model = {model_name}",
        "* PROBLEM DESCRIPTION",
        "PROB, 'Aspen Plus to HTRI Heat Exchanger Export'",
        "CASE, 'Generated by htri_export program'",
        "* CONTROL DATA",
        "* DATA INPUT UNITS SYSTEM=SI",
        "CONT, , , 1",
    ]

    selected = []
    counts = {"H": 0, "C": 0}
    for key in sorted(groups, key=lambda key: (key[1], int(key[2]))):
        prefix = curve_prefix(groups[key])
        if counts[prefix] >= 12:
            continue
        counts[prefix] += 1
        selected.append(key)

    emitted_common = {"H": False, "C": False}
    for object_type, object_name, hcurv_no in selected:
        prefix = curve_prefix(groups[(object_type, object_name, hcurv_no)])
        include_common = not emitted_common[prefix]
        export_curve(
            lines,
            object_type,
            object_name,
            hcurv_no,
            groups[(object_type, object_name, hcurv_no)],
            include_process=include_common,
            include_fluid=include_common,
        )
        emitted_common[prefix] = True

    Path(output_path).write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"Wrote {output_path}")
    print(f"Curves: {len(selected)}")
    print(f"Hot curves: {counts['H']}")
    print(f"Cold curves: {counts['C']}")


if __name__ == "__main__":
    main()
