#!/usr/bin/env python3
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


TOTAL_COLUMNS = [
    "TEMP_OUT_C",
    "HMX__PNH_TOTAL_KJ_PER_KG",
    "HMX_TOTAL_KJ_PER_KG",
    "MASSVFRA__PNH_TOTAL",
]

VAPOR_COLUMNS = [
    "RHOMX__PNH_VAPOR_KG_PER_CUM",
    "RHOMX_VAPOR_KG_PER_CUM",
    "MUMX__PNH_VAPOR_CP",
    "KMX__PNH_VAPOR_WATT_PER_M-K",
    "CPMX__PNH_VAPOR_KJ_PER_KG-K",
    "HMX__PNH_VAPOR_KJ_PER_KG",
    "HMX_VAPOR_KJ_PER_KG",
    "MWMX__PNH_VAPOR",
    "MWMX_VAPOR",
    "MWMX_VAPOR_G_PER_MOL",
]

LIQUID_COLUMNS = [
    "RHOMX__PNH_LIQUID_KG_PER_CUM",
    "RHOMX_LIQUID_KG_PER_CUM",
    "MUMX__PNH_LIQUID_CP",
    "KMX__PNH_LIQUID_WATT_PER_M-K",
    "CPMX__PNH_LIQUID_KJ_PER_KG-K",
    "HMX__PNH_LIQUID_KJ_PER_KG",
    "HMX_LIQUID_KJ_PER_KG",
    "SIGMAMX__PNH_LIQUID_MN_PER_M",
    "SIGMAMX__PNH_LIQUID_DYNE_PER_CM",
    "DHVLMXMS__PNH_LIQUID_KJ_PER_KG",
    "TCMX__PNH_LIQUID_C",
    "PCMX__PNH_LIQUID_KPA",
    "PCMX__PNH_LIQUID_MPA",
    "MWMX__PNH_LIQUID",
    "MWMX_LIQUID",
    "MWMX_LIQUID_G_PER_MOL",
]

TEMP_CANDIDATES = [
    "TEMP__PNH_TOTAL_C",
    "TEMP__PNH_C",
    "TEMP__PNSH_TOTAL_C",
    "TEMP__PNSH_C",
    "TEMP__NH_C",
    "TEMP_OUT_C",
    "TEMP_OUT2_C",
    "TEMP_CLD_C",
    "TEMP_HOT_C",
]
PRES_CANDIDATES = [
    "PRES__PNH_TOTAL_KPA",
    "PRES__PNH_KPA",
    "PRES__PNH_TOTAL_BAR",
    "PRES__PNH_BAR",
    "PRES__PNH_TOTAL_MPAG",
    "PRES__PNH_MPAG",
    "PRES__PNSH_TOTAL_KPA",
    "PRES__PNSH_KPA",
    "PRES__PNSH_BAR",
    "PRES__PNSH_MPAG",
    "PRES__NH_KPA",
    "PRES__NH_BAR",
    "PRES__NH_MPAG",
    "PRES_OUT_KPA",
    "PRES_OUT_MPAG",
    "PRES_OUT_BAR",
    "PRES_OUT2_KPA",
    "PRES_OUT2_MPAG",
    "PRES_OUT2_BAR",
    "PRES_CLD_KPA",
    "PRES_CLD_BAR",
    "PRES_HOT_KPA",
    "PRES_HOT_BAR",
]
FLOW_CANDIDATES = ["MASSFLMX__PNH_TOTAL_KG_PER_SEC", "MASSFLMX_TOTAL_KG_PER_SEC", "MASSFLMX__PNSH_TOTAL_KG_PER_SEC"]
H_TOTAL_CANDIDATES = ["HMX__PNH_TOTAL_KJ_PER_KG", "HMX__PNH_TOTAL_J_PER_KG", "HMX_TOTAL_KJ_PER_KG", "HMX_TOTAL_J_PER_KG", "HMX__PNSH_TOTAL_KJ_PER_KG", "HMX__PNSH_TOTAL_J_PER_KG"]
H_VAPOR_CANDIDATES = ["HMX__PNH_VAPOR_KJ_PER_KG", "HMX__PNH_VAPOR_J_PER_KG", "HMX_VAPOR_KJ_PER_KG", "HMX_VAPOR_J_PER_KG", "HMX__PNSH_VAPOR_KJ_PER_KG", "HMX__PNSH_VAPOR_J_PER_KG"]
H_LIQUID_CANDIDATES = ["HMX__PNH_LIQUID_KJ_PER_KG", "HMX__PNH_LIQUID_J_PER_KG", "HMX_LIQUID_KJ_PER_KG", "HMX_LIQUID_J_PER_KG", "HMX__PNSH_LIQUID_KJ_PER_KG", "HMX__PNSH_LIQUID_J_PER_KG"]
QUALITY_TOTAL_CANDIDATES = ["MASSVFRA__PNH_TOTAL", "MASSVFRA__PNSH_TOTAL"]
RHO_VAPOR_CANDIDATES = ["RHOMX__PNH_VAPOR_KG_PER_CUM", "RHOMX_VAPOR_KG_PER_CUM", "RHOMX__PNSH_VAPOR_KG_PER_CUM"]
RHO_LIQUID_CANDIDATES = ["RHOMX__PNH_LIQUID_KG_PER_CUM", "RHOMX_LIQUID_KG_PER_CUM", "RHOMX__PNSH_LIQUID_KG_PER_CUM"]
MU_VAPOR_CANDIDATES = ["MUMX__PNH_VAPOR_CP", "MUMX__PNH_VAPOR_N-SEC_PER_SQM", "MUMX__PNH_VAPOR_MN-SEC_PER_SQM", "MUMX__PNSH_VAPOR_CP", "MUMX__PNSH_VAPOR_N-SEC_PER_SQM", "MUMX__PNSH_VAPOR_MN-SEC_PER_SQM"]
MU_LIQUID_CANDIDATES = ["MUMX__PNH_LIQUID_CP", "MUMX__PNH_LIQUID_N-SEC_PER_SQM", "MUMX__PNH_LIQUID_MN-SEC_PER_SQM", "MUMX__PNSH_LIQUID_CP", "MUMX__PNSH_LIQUID_N-SEC_PER_SQM", "MUMX__PNSH_LIQUID_MN-SEC_PER_SQM"]
K_VAPOR_CANDIDATES = ["KMX__PNH_VAPOR_WATT_PER_M-K", "KMX__PNSH_VAPOR_WATT_PER_M-K"]
K_LIQUID_CANDIDATES = ["KMX__PNH_LIQUID_WATT_PER_M-K", "KMX__PNSH_LIQUID_WATT_PER_M-K"]
CP_VAPOR_CANDIDATES = ["CPMX__PNH_VAPOR_KJ_PER_KG-K", "CPMX__PNH_VAPOR_J_PER_KG-K", "CPMX__PNSH_VAPOR_KJ_PER_KG-K", "CPMX__PNSH_VAPOR_J_PER_KG-K"]
CP_LIQUID_CANDIDATES = ["CPMX__PNH_LIQUID_KJ_PER_KG-K", "CPMX__PNH_LIQUID_J_PER_KG-K", "CPMX__PNSH_LIQUID_KJ_PER_KG-K", "CPMX__PNSH_LIQUID_J_PER_KG-K"]
MW_VAPOR_CANDIDATES = ["MWMX__PNH_VAPOR", "MWMX_VAPOR", "MWMX_VAPOR_G_PER_MOL", "MWMX__PNSH_VAPOR"]
MW_LIQUID_CANDIDATES = ["MWMX__PNH_LIQUID", "MWMX_LIQUID", "MWMX_LIQUID_G_PER_MOL", "MWMX__PNSH_LIQUID"]
MW_TOTAL_CANDIDATES = ["MWMX__PNH_TOTAL", "MWMX_TOTAL", "MWMX__PNSH_TOTAL"]
SIGMA_LIQUID_CANDIDATES = ["SIGMAMX__PNH_LIQUID_MN_PER_M", "SIGMAMX__PNH_LIQUID_DYNE_PER_CM", "SIGMAMX__PNH_LIQUID_N_PER_M", "SIGMAMX__PNSH_LIQUID_MN_PER_M", "SIGMAMX__PNSH_LIQUID_DYNE_PER_CM", "SIGMAMX__PNSH_LIQUID_N_PER_M", "SIGMAMX__PNSH_LIQUID"]
TC_LIQUID_CANDIDATES = ["TCMX__PNH_LIQUID_C", "TCMX__PNSH_LIQUID_C", "TCMX__PNH_TOTAL_C", "TCMX__PNH_VAPOR_C", "TCMX__PNSH_TOTAL_C", "TCMX__PNSH_VAPOR_C"]
PC_LIQUID_CANDIDATES = ["PCMX__PNH_LIQUID_KPA", "PCMX__PNH_LIQUID_MPA", "PCMX__PNH_LIQUID_N_PER_SQM", "PCMX__PNSH_LIQUID_KPA", "PCMX__PNSH_LIQUID_MPA", "PCMX__PNSH_LIQUID_N_PER_SQM", "PCMX__PNH_TOTAL_KPA", "PCMX__PNH_VAPOR_KPA", "PCMX__PNSH_TOTAL_KPA", "PCMX__PNSH_VAPOR_KPA"]
LATENT_HEAT_CANDIDATES = ["DHVLMXMS__PNH_LIQUID_KJ_PER_KG", "DHVLMXMS__PNH_TOTAL_KJ_PER_KG", "DHVLMXMS__PNSH_LIQUID_KJ_PER_KG", "DHVLMXMS__PNSH_TOTAL_KJ_PER_KG"]


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def read_xml(path):
    data = Path(path).read_bytes()
    raw = data.decode("utf-16") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8-sig")
    raw = re.sub(r"<\?xml[^>]*\?>", "", raw).strip()
    return ET.fromstring(f"<ROOT>{raw}</ROOT>")


def model_name_from_xml(xml_path):
    root = read_xml(xml_path)
    for child in list(root):
        name = child.attrib.get("name")
        if local_name(child.tag) == "Plant" and name:
            return name
    return Path(xml_path).stem


def connection_dest_streams(xml_path):
    root = read_xml(xml_path)
    mapping = {}
    for element in root.iter():
        if local_name(element.tag) != "Connection":
            continue
        dest = element.attrib.get("dest")
        stream = element.attrib.get("stream")
        if dest and stream:
            mapping.setdefault(dest, stream)
    return mapping


def f(value):
    if value in (None, "", "*"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def value(row, candidates):
    for column in candidates:
        if column in row and f(row[column]) is not None:
            return f(row[column])
    return None


def fmt(value, zero_decimal=False):
    if value is None:
        return "          1*"
    if zero_decimal and abs(value) == 0:
        return "         0.0"
    return f"{value:12.7g}"


def format_tokens(values, zero_decimal=False):
    tokens = []
    index = 0
    while index < len(values):
        if values[index] is None:
            start = index
            while index < len(values) and values[index] is None:
                index += 1
            tokens.append(f"{index - start:11d}*")
        else:
            tokens.append(fmt(values[index], zero_decimal=zero_decimal))
            index += 1
    return tokens


def write_values(lines, values, per_line=5, zero_decimal=False, comment=None):
    if comment:
        lines.append(f"*   {comment}")
    tokens = format_tokens(values, zero_decimal=zero_decimal)
    for index in range(0, len(tokens), per_line):
        lines.append("     " + ",".join(tokens[index:index + per_line]) + ",")


def has_values(rows, candidate_groups):
    for row in rows:
        for candidates in candidate_groups:
            if value(row, candidates) is not None:
                return True
    return False


def valid_rows(rows):
    out = [row for row in sorted(rows, key=lambda r: int(r["NPOINT"])) if value(row, TEMP_CANDIDATES) is not None]
    return out or sorted(rows, key=lambda r: int(r["NPOINT"]))


def reduce_to_30(rows):
    rows = valid_rows(rows)
    if len(rows) <= 30:
        return rows
    remove_count = len(rows) - 30
    candidates = list(range(4, len(rows) - 1, 2))
    candidates += [i for i in range(5, len(rows) - 1, 2) if i not in candidates]
    remove = set(candidates[:remove_count])
    return [row for idx, row in enumerate(rows) if idx not in remove]


def curve_type(rows):
    rows = reduce_to_30(rows)
    tin = value(rows[0], TEMP_CANDIDATES)
    tout = value(rows[-1], TEMP_CANDIDATES)
    if tin is None or tout is None:
        return ""
    return "H" if tin is not None and tout is not None and tout < tin else "C"


def group_rows(wide_path):
    groups = defaultdict(list)
    with Path(wide_path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (
                row["object_type"],
                row["object_name"],
                row.get("STREAMID", ""),
                row["HCURV_NO"],
            )
            groups[key].append(row)
    return groups


def ordered_selected(groups):
    counts = {"H": 0, "C": 0}
    selected = []
    def sort_key(key):
        h = key[3]
        m = re.search(r"(\d+)$", h)
        n = int(m.group(1)) if m else 999
        return (key[1], key[2], n, h)
    for key in sorted(groups, key=sort_key):
        side = curve_type(groups[key])
        if side not in counts:
            continue
        if len(reduce_to_30(groups[key])) != 30:
            continue
        if counts[side] >= 12:
            continue
        counts[side] += 1
        selected.append((key, side))
    return selected, counts


def stream_name(key, dest_streams, side=None, side_stream_names=None):
    _, object_name, streamid, _ = key
    if side_stream_names and side:
        name = side_stream_names.get((object_name, side))
        if name:
            return name
    return streamid or dest_streams.get(object_name, object_name)


def export_dat(wide_path, xml_path, out_path, model_name):
    return export_dat_with_options(wide_path, xml_path, out_path, model_name)


def export_dat_with_options(
    wide_path,
    xml_path,
    out_path,
    model_name,
    include_fixed_cards=True,
    include_hxs_comments=True,
    include_mlen=True,
    include_process_pressure_line=True,
    include_process_pressure_drop=False,
    extra_header_lines=None,
    include_extra_liquid_props=True,
    include_data_comments=False,
    prefer_curve_flow_types=None,
    side_stream_names=None,
    component_cards_from_curve=False,
):
    prefer_curve_flow_types = set(prefer_curve_flow_types or [])
    groups = group_rows(wide_path)
    selected, counts = ordered_selected(groups)
    dest_streams = connection_dest_streams(xml_path)
    qcalc_by_stream = qcalc_values_by_stream(xml_path)
    hot = [(key, side) for key, side in selected if side == "H"]
    cold = [(key, side) for key, side in selected if side == "C"]

    duty_mw = None
    if selected:
        duty_key, duty_side = selected[0]
        duty_rows = reduce_to_30(groups[duty_key])
        duty_fluid = stream_name(duty_key, dest_streams, duty_side, side_stream_names)
        duty_mw = duty_for_csv(duty_rows[0], duty_fluid, qcalc_by_stream)
    lines = [
        "PROB, 'Aspen Plus to HTRI Heat Exchanger Export'",
        "CASE, 'Generated by htri_export program'",
        f"CONT,         2*,           1,         1*,{fmt(duty_mw)}",
    ]

    def process_line(key, side):
        rows = reduce_to_30(groups[key])
        first, last = rows[0], rows[-1]
        pro = "HPRO" if side == "H" else "CPRO"
        flow = value(first, FLOW_CANDIDATES) if key[0] in prefer_curve_flow_types else None
        if flow is None:
            flow = f(first.get('TOTAL_MASS_FLOW_KG_PER_HR'))
        out = [
            f"{pro},{fmt(flow)},{fmt(value(first, QUALITY_TOTAL_CANDIDATES))},"
            f"{fmt(value(last, QUALITY_TOTAL_CANDIDATES))},{fmt(value(first, TEMP_CANDIDATES))},{fmt(value(last, TEMP_CANDIDATES))},",
        ]
        if include_process_pressure_line:
            if include_process_pressure_drop:
                out.append(f"     {fmt(value(first, PRES_CANDIDATES))},{fmt(f(first.get('PRESSURE_DROP_KPA')))},         2*,           1")
            else:
                out.append(f"     {fmt(value(first, PRES_CANDIDATES))},         3*,           1")
        return out

    if hot:
        lines.extend(process_line(hot[0][0], "H"))
    if cold:
        lines.extend(process_line(cold[0][0], "C"))

    if include_fixed_cards:
        lines.extend([
            "SHEL,       'AES',         0.0,         4*,           1,         9*,",
            "                2,           0,        5054,        5054,        5054",
            "TUBE,           1,        25.4,      2.7686,         2*,           1,",
            "              1*,       31.75,         1*,        6096,          30",
            "NOZZ,           1,           1,           1,           1,        16*,",
            "                7,           3,         1*,           2,           9",
            "OGEO,         5*,         'N',        19*,           3,         2*,",
            "            3.175,        18*,           1,         7*,         'N',",
            "             15*,       3.175,        19*, 182.2222222",
            "DGEO,        11*,          16,         9*,           1,         8*,",
            "              0.0,         1*,           1",
            "FLUX,         2*,           1",
            "ME1P,         2*,           1,           1,        11*,           1,",
            "                1",
            "ME2P,        10*,         0.0,         0.0",
        ])
    if include_mlen:
        lines.append("OGEO,        17*,         'Y',         7*,           1,        56*,         'Y'")
    lines.extend(extra_header_lines or [])

    def write_curve_blocks(curves, side):
        if not curves:
            return
        flu = "HFLU" if side == "H" else "CFLU"
        qcard = "HOTQ" if side == "H" else "COLQ"
        pva = "HPVA" if side == "H" else "CPVA"
        pli = "HPLI" if side == "H" else "CPLI"
        first_key = curves[0][0]
        first_rows = reduce_to_30(groups[first_key])
        name = stream_name(first_key, dest_streams, side, side_stream_names)[:7].ljust(7)
        lines.append(f"{flu}, '{name}',           1,           3,         2*,{len(first_rows):12d}")
        if include_hxs_comments:
            lines.extend([
                "*[HXS] BEG PPKG",
                "*[HXS] PPKG PACKAGE=17",
                "*[HXS] DESC \"System model: IAPWS-IF97\"",
                "*[HXS] OPTN MIXRULE=1",
                "*[HXS] END PPKG",
                f"*[HXS] {'HCOM' if side == 'H' else 'CCOM'}    1,     'Water',    18.01528",
            ])

        for ref_no, (key, _) in enumerate(curves, 1):
            rows = reduce_to_30(groups[key])
            first = rows[0]
            if include_data_comments:
                lines.append("*   REFERENCE PRESSURE NUMBER, REFERENCE PRESSURE")
            lines.append(f"{qcard},{ref_no:12d},{fmt(value(first, PRES_CANDIDATES))},")
            write_values(lines, [value(r, TEMP_CANDIDATES) for r in rows], comment="TEMPERATURE" if include_data_comments else None)
            write_values(lines, [value(r, H_TOTAL_CANDIDATES) for r in rows], comment="ENTHALPY" if include_data_comments else None)
            write_values(lines, [value(r, QUALITY_TOTAL_CANDIDATES) for r in rows], zero_decimal=True, comment="QUALITY" if include_data_comments else None)

            vapor_candidate_groups = [
                RHO_VAPOR_CANDIDATES,
                MU_VAPOR_CANDIDATES,
                K_VAPOR_CANDIDATES,
                CP_VAPOR_CANDIDATES,
                H_VAPOR_CANDIDATES,
                MW_VAPOR_CANDIDATES,
            ]
            if side == "H" or has_values(rows, vapor_candidate_groups):
                if include_data_comments:
                    lines.append("*   REFERENCE PRESSURE NUMBER")
                lines.append(f"{pva},{ref_no:12d},")
                for comment, candidates in [
                    ("DENSITY", RHO_VAPOR_CANDIDATES),
                    ("VISCOSITY", MU_VAPOR_CANDIDATES),
                    ("CONDUCTIVITY", K_VAPOR_CANDIDATES),
                    ("HEAT CAPACITY", CP_VAPOR_CANDIDATES),
                    ("ENTHALPY", H_VAPOR_CANDIDATES),
                    ("MOLECULAR WEIGHT", MW_VAPOR_CANDIDATES),
                ]:
                    write_values(lines, [value(r, candidates) for r in rows], comment=comment if include_data_comments else None)

            if include_data_comments:
                lines.append("*   REFERENCE PRESSURE NUMBER")
            lines.append(f"{pli},{ref_no:12d},")
            liquid_candidates = [
                ("DENSITY", RHO_LIQUID_CANDIDATES),
                ("VISCOSITY", MU_LIQUID_CANDIDATES),
                ("CONDUCTIVITY", K_LIQUID_CANDIDATES),
                ("HEAT CAPACITY", CP_LIQUID_CANDIDATES),
                ("ENTHALPY", H_LIQUID_CANDIDATES),
                ("SURFACE TENSION", SIGMA_LIQUID_CANDIDATES),
                ("LATENT HEAT", LATENT_HEAT_CANDIDATES),
            ]
            if include_extra_liquid_props:
                liquid_candidates.extend([
                    ("CRITICAL TEMPERATURE", TC_LIQUID_CANDIDATES),
                    ("CRITICAL PRESSURE", PC_LIQUID_CANDIDATES),
                    ("LEWIS NUMBER", ["LEWIS_NUMBER_PLACEHOLDER"]),
                    ("MOLECULAR WEIGHT", MW_LIQUID_CANDIDATES),
                ])
            else:
                liquid_candidates.append(("MOLECULAR WEIGHT", MW_LIQUID_CANDIDATES))
            for comment, candidates in liquid_candidates:
                write_values(lines, [value(r, candidates) for r in rows], comment=comment if include_data_comments else None)
        if side == "H":
            if component_cards_from_curve:
                mw = value(first_rows[0], MW_TOTAL_CANDIDATES + MW_VAPOR_CANDIDATES + MW_LIQUID_CANDIDATES)
                lines.append(f"HCON,           1,{fmt(mw)}")
            else:
                lines.append("HCON,           1,    18.01528")
        elif component_cards_from_curve:
            mw = value(first_rows[0], MW_TOTAL_CANDIDATES + MW_VAPOR_CANDIDATES + MW_LIQUID_CANDIDATES)
            lines.append(f"CCON,           1,{fmt(mw)}")

    write_curve_blocks(hot, "H")
    write_curve_blocks(cold, "C")
    lines.append("ENDC")

    Path(out_path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return selected, counts


def csv_cell(value):
    return "" if value is None else value


def split_items(text):
    if not text:
        return []
    return [item.strip() for item in text.split(",")]


def qcalc_values_by_stream(xml_path):
    if not xml_path:
        return {}
    root = read_xml(xml_path)
    out = {}
    for element in root.iter():
        object_name = element.attrib.get("name")
        if not object_name:
            continue
        for child in list(element):
            if local_name(child.tag) != "QCALC":
                continue
            streams = []
            values = []
            for item in list(child):
                item_name = local_name(item.tag)
                if item_name == "STREAMID":
                    streams = split_items(item.attrib.get("items", ""))
                elif item_name == "Value":
                    values = [f(value) for value in split_items(item.text or "")]
            if streams:
                for stream, duty in zip(streams, values):
                    if duty is not None:
                        out[(object_name, stream)] = duty
            elif values and values[0] is not None:
                out[(object_name, "")] = values[0]
    return out


def duty_for_csv(row, fluid, qcalc_by_stream):
    object_name = row.get("object_name", "")
    duty = qcalc_by_stream.get((object_name, fluid))
    if duty is None:
        duty = qcalc_by_stream.get((object_name, ""))
    if duty is None:
        duty = f(row.get("DUTY_KW"))
    return abs(duty) / 1000 if duty is not None else None


def write_curve_csv(wide_path, out_csv, xml_path=None, side_stream_names=None):
    groups = group_rows(wide_path)
    dest_streams = connection_dest_streams(xml_path) if xml_path else {}
    qcalc_by_stream = qcalc_values_by_stream(xml_path)

    def curve_number_key(key):
        hcurv_no = key[3]
        match = re.search(r"(\d+)$", hcurv_no or "")
        return int(match.group(1)) if match else 999

    def natural_key(item):
        key, _ = item
        hcurv_no = key[3]
        number = curve_number_key(key)
        return (key[1], number, key[2], hcurv_no)

    curve_items = []
    for key, raw_rows in groups.items():
        rows = reduce_to_30(raw_rows)
        if len(rows) != 30:
            continue
        side = curve_type(rows)
        if side not in {"H", "C"}:
            continue
        curve_items.append((key, rows))

    with Path(out_csv).open("w", encoding="ascii", newline="") as dst:
        writer = csv.writer(dst)
        natural_items = sorted(curve_items, key=natural_key)
        side_order = {}
        for _, rows in natural_items:
            side = curve_type(rows)
            if side not in side_order:
                side_order[side] = len(side_order)
        sorted_items = sorted(
            natural_items,
            key=lambda item: (
                side_order[curve_type(item[1])],
                stream_name(item[0], dest_streams, curve_type(item[1]), side_stream_names),
                curve_number_key(item[0]),
                item[0][3],
            ),
        )
        device_name = sorted_items[0][0][1] if sorted_items else ""
        writer.writerow([device_name])
        seen_fluids = set()
        for block_index, (key, rows) in enumerate(sorted_items):
            side = curve_type(rows)
            first, last = rows[0], rows[-1]
            fluid = stream_name(key, dest_streams, side, side_stream_names)
            mass_flow = value(first, FLOW_CANDIDATES) or f(first.get("TOTAL_MASS_FLOW_KG_PER_HR"))
            pressure = value(first, PRES_CANDIDATES)
            pressure_drop = f(first.get("PRESSURE_DROP_KPA"))
            duty_mw = duty_for_csv(first, fluid, qcalc_by_stream)
            row = lambda values=None: writer.writerow((values or []) + [""] * (21 - len(values or [])))

            if block_index:
                row([])
            if fluid not in seen_fluids:
                row(["", "Fluid name", "", fluid])
                row(["", "Fluid quantity, Total", "kg/s", csv_cell(mass_flow)])
                row(["", "Temperature (In/Out)", "C", csv_cell(value(first, TEMP_CANDIDATES)), csv_cell(value(last, TEMP_CANDIDATES))])
                row(["", "Vapor weight fraction (In/Out)", "", csv_cell(value(first, QUALITY_TOTAL_CANDIDATES)), csv_cell(value(last, QUALITY_TOTAL_CANDIDATES))])
                row(["", "Inlet pressure", "kPa", csv_cell(pressure)])
                row(["", "Pressure drop, allow.", "kPa", csv_cell(pressure_drop)])
                row(["", "Exchanger duty", "MegaWatts", csv_cell(duty_mw)])
                row([])
                seen_fluids.add(fluid)
            row(["", "Pressure", csv_cell(pressure), "kPa", "Vapor Properties", "", "", "", "", "", "Liquid Properties"])
            row([
                "",
                "Temperature(C)",
                "Enthalpy(kJ/kg)",
                "WeightFractionVapor",
                "Density(kg/m3)",
                "Viscosity(mN-s/m2)",
                "HeatCapacity(kJ/kg-C)",
                "Conductivity(W/m-C)",
                "Enthalpy(kJ/kg)",
                "MolecularWeight",
                "Density(kg/m3)",
                "Viscosity(mN-s/m2)",
                "HeatCapacity(kJ/kg-C)",
                "Conductivity(W/m-C)",
                "Enthalpy(kJ/kg)",
                "SurfaceTension(mN/m)",
                "LatentHeat(kJ/kg)",
                "CriticalPressure(kPa)",
                "CriticalTemperature(C)",
                "MolecularWeight",
                "LewisNumber",
            ])
            for data_row in rows:
                row([
                    "",
                    csv_cell(value(data_row, TEMP_CANDIDATES)),
                    csv_cell(value(data_row, H_TOTAL_CANDIDATES)),
                    csv_cell(value(data_row, QUALITY_TOTAL_CANDIDATES)),
                    csv_cell(value(data_row, RHO_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, MU_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, CP_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, K_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, H_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, MW_VAPOR_CANDIDATES)),
                    csv_cell(value(data_row, RHO_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, MU_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, CP_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, K_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, H_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, SIGMA_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, LATENT_HEAT_CANDIDATES)),
                    csv_cell(value(data_row, PC_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, TC_LIQUID_CANDIDATES)),
                    csv_cell(value(data_row, MW_LIQUID_CANDIDATES)),
                    "",
                ])


def write_check_csv(groups, selected, out_csv):
    selected_keys = {key for key, _ in selected}
    with Path(out_csv).open("w", encoding="ascii", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["object_type", "object_name", "STREAMID", "HCURV_NO", "curve_type", "valid_points", "output_points", "in_dat", "status"])
        for key in sorted(groups):
            side = curve_type(groups[key])
            valid = valid_rows(groups[key])
            reduced = reduce_to_30(groups[key])
            status = "OK" if len(reduced) == 30 else "NOT_30"
            if status != "OK":
                writer.writerow([*key, "HOT" if side == "H" else "COLD", len(valid), len(reduced), "YES" if key in selected_keys else "NO", status])


def main():
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("Usage: export_htri_compact.py source.xml wide_input.txt [output_dir]")
    xml_path = sys.argv[1]
    wide_path = sys.argv[2]
    out_dir = Path(sys.argv[3]) if len(sys.argv) == 4 else Path("outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_name = model_name_from_xml(xml_path)
    safe_name = re.sub(r"[/:\\\\]+", "_", model_name)
    dat_path = out_dir / f"{safe_name}.dat"
    csv_path = out_dir / f"{safe_name}.csv"
    check_path = out_dir / f"{safe_name}_point_check.csv"
    selected, counts = export_dat(wide_path, xml_path, dat_path, model_name)
    groups = group_rows(wide_path)
    write_curve_csv(wide_path, csv_path, xml_path=xml_path)
    write_check_csv(groups, selected, check_path)
    print(f"DAT: {dat_path}")
    print(f"CSV: {csv_path}")
    print(f"CHECK: {check_path}")
    print(f"Curves: {len(selected)}, hot={counts['H']}, cold={counts['C']}")


if __name__ == "__main__":
    main()
