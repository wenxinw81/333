#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


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


def f(value):
    if value in (None, "", "*"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def first_number(text, default=999):
    match = re.search(r"(\d+)", text or "")
    return int(match.group(1)) if match else default


def value(row, candidates):
    for column in candidates:
        if f(row.get(column)) is not None:
            return f(row[column])
    return None


def point_number(row):
    return int(row.get("NPOINT") or 0)


def valid_rows(rows):
    ordered = sorted(rows, key=point_number)
    valid = [row for row in ordered if value(row, TEMP_CANDIDATES) is not None]
    return valid or ordered


def reduce_to_30(rows):
    rows = valid_rows(rows)
    if len(rows) <= 30:
        return rows
    remove_count = len(rows) - 30
    candidates = list(range(4, len(rows) - 1, 2))
    candidates.extend(index for index in range(5, len(rows) - 1, 2) if index not in candidates)
    remove = set(candidates[:remove_count])
    return [row for index, row in enumerate(rows) if index not in remove]


def curve_side(rows):
    rows = reduce_to_30(rows)
    if not rows:
        return "UNKNOWN"
    inlet = value(rows[0], TEMP_CANDIDATES)
    outlet = value(rows[-1], TEMP_CANDIDATES)
    if inlet is None or outlet is None:
        return "UNKNOWN"
    return "HOT" if outlet < inlet else "COLD"


def profile_for(object_type):
    if object_type == "BlockMheatx":
        return "mheatx"
    if object_type == "BlockRadfrac":
        return "radfrac"
    if object_type in {"BlockHeater", "BlockFlash2", "BlockFlash3", "BlockHeatx"}:
        return "standard"
    return "unknown"


def group_wide_rows(wide_path):
    groups = defaultdict(list)
    with Path(wide_path).open("r", encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            key = (
                row.get("object_type", ""),
                row.get("object_name", ""),
                row.get("STREAMID", ""),
                row.get("HCURV_NO", ""),
            )
            groups[key].append(row)
    return groups


def write_profile_summary(wide_path, out_csv):
    groups = group_wide_rows(wide_path)
    selected_count = defaultdict(int)
    rows = []

    for key, group_rows in sorted(
        groups.items(),
        key=lambda item: (profile_for(item[0][0]), item[0][1], item[0][2], first_number(item[0][3]), item[0][3]),
    ):
        object_type, object_name, streamid, hcurv_no = key
        profile = profile_for(object_type)
        side = curve_side(group_rows)
        valid_count = len(valid_rows(group_rows))
        output_count = len(reduce_to_30(group_rows))
        eligible = output_count == 30 and side in {"HOT", "COLD"} and profile != "unknown"
        profile_side_key = (profile, side)
        in_dat = False
        if eligible and selected_count[profile_side_key] < 12:
            selected_count[profile_side_key] += 1
            in_dat = True
        rows.append(
            {
                "profile": profile,
                "object_type": object_type,
                "object_name": object_name,
                "streamid": streamid,
                "hcurv_no": hcurv_no,
                "side": side,
                "valid_points": valid_count,
                "output_points": output_count,
                "in_dat_candidate": "YES" if in_dat else "NO",
                "reason": "OK" if in_dat else ("NOT_30" if output_count != 30 else "LIMIT_OR_PROFILE"),
            }
        )

    fields = [
        "profile",
        "object_type",
        "object_name",
        "streamid",
        "hcurv_no",
        "side",
        "valid_points",
        "output_points",
        "in_dat_candidate",
        "reason",
    ]
    with Path(out_csv).open("w", encoding="ascii", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: htri_model_profiles.py wide_table.txt profile_summary.csv")
    rows = write_profile_summary(sys.argv[1], sys.argv[2])
    counts = defaultdict(int)
    for row in rows:
        counts[(row["profile"], row["side"])] += 1
    print(f"Profile rows: {len(rows)}")
    for key in sorted(counts):
        print(f"{key[0]},{key[1]}: {counts[key]}")


if __name__ == "__main__":
    main()
