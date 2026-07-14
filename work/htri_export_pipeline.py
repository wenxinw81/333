#!/usr/bin/env python3
import csv
import contextlib
import io
import runpy
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from export_htri_compact import (
    curve_type,
    group_rows,
    model_name_from_xml,
    reduce_to_30,
    write_curve_csv,
)
from export_blockmheatx_by_object import write_blockmheatx_check_csv


WORK_DIR = Path(__file__).resolve().parent
ROOT_DIR = WORK_DIR.parent

PIPELINE_STEPS = [
    ("extract_hcurve_ascii.py", "{xml}", "{long}"),
    ("pivot_hcurve_ascii.py", "{long}", "{wide}"),
    ("add_block_scalar_columns.py", "{xml}", "{wide}", "{wide_scalars}"),
    ("add_curve_endpoint_columns.py", "{wide_scalars}", "{final_table}"),
]

MODEL_EXPORTERS = [
    "export_blockheater_by_object.py",
    "export_blockheatx_by_object.py",
    "export_blockradfrac_by_object.py",
    "export_blockmcompr_by_object.py",
]


def safe_name(text):
    out = "".join("_" if ch in '/:\\\\' else ch for ch in str(text or ""))
    return out.strip() or "output"


def default_output_dir(xml_path, parent=None):
    parent = Path(parent) if parent else ROOT_DIR / "outputs"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return parent / f"{safe_name(Path(xml_path).stem)}_gui_{stamp}"


def run_command(args, log=None):
    if log:
        log("$ " + " ".join(str(arg) for arg in args))
    proc = subprocess.run(
        [str(arg) for arg in args],
        cwd=str(ROOT_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if log and proc.stdout:
        log(proc.stdout.rstrip())
    if proc.returncode:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(str(arg) for arg in args)}")
    return proc.stdout


def run_script(script, script_args, log=None):
    script = Path(script)
    display = [sys.executable, script, *script_args]
    if log:
        log("$ " + " ".join(str(arg) for arg in display))
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    sys.argv = [str(script), *[str(arg) for arg in script_args]]
    sys.path.insert(0, str(script.parent))
    sys.path.insert(0, str(WORK_DIR))
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code:
            raise RuntimeError(f"Command failed ({code}): {' '.join(str(arg) for arg in display)}") from exc
    finally:
        sys.argv = old_argv
        sys.path = old_path
    output = stdout.getvalue()
    if log and output:
        log(output.rstrip())
    return output


def script_path(script_name):
    candidates = [
        WORK_DIR / script_name,
        ROOT_DIR / "work" / script_name,
    ]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates.extend([
            exe_dir / "work" / script_name,
            exe_dir / "_internal" / "work" / script_name,
            meipass / "work" / script_name,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def run_parse_pipeline(xml_path, out_dir, log=None):
    xml_path = Path(xml_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "xml": xml_path,
        "long": out_dir / "long.txt",
        "wide": out_dir / "wide.txt",
        "wide_scalars": out_dir / "wide_scalars.txt",
        "final_table": out_dir / "final_table.txt",
    }
    for step in PIPELINE_STEPS:
        script = script_path(step[0])
        args = [str(paths[token.strip("{}")]) if token.startswith("{") else token for token in step[1:]]
        run_script(script, args, log)
    return paths


def run_standard_exports(xml_path, final_table, out_dir, log=None):
    made = []
    for script_name in MODEL_EXPORTERS:
        before = set(Path(out_dir).glob("*"))
        run_script(script_path(script_name), [xml_path, final_table, out_dir], log)
        after = set(Path(out_dir).glob("*"))
        made.extend(sorted(after - before))
    return made


def read_mheatx_rows(final_table):
    final_table = Path(final_table)
    with final_table.open("r", encoding="ascii", newline="") as src:
        reader = csv.DictReader(src, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows_by_object = defaultdict(list)
        for row in reader:
            if row.get("object_type") == "BlockMheatx":
                rows_by_object[row.get("object_name", "BlockMheatx")].append(row)
    return fieldnames, rows_by_object


def mheat_curve_summary(final_table):
    _, rows_by_object = read_mheatx_rows(final_table)
    items = []
    for object_name, rows in sorted(rows_by_object.items()):
        groups = defaultdict(list)
        for row in rows:
            key = (
                row.get("object_type", ""),
                row.get("object_name", ""),
                row.get("STREAMID", ""),
                row.get("HCURV_NO", ""),
            )
            groups[key].append(row)
        for key in sorted(groups):
            reduced = reduce_to_30(groups[key])
            side = curve_type(groups[key])
            if side not in {"H", "C"}:
                continue
            items.append({
                "key": "|".join(key),
                "object_name": object_name,
                "stream": key[2],
                "curve": key[3],
                "side": "HOT" if side == "H" else "COLD",
                "raw_points": len(groups[key]),
                "output_points": len(reduced),
                "default_selected": len(reduced) == 30,
            })
    return items


def write_rows(path, fieldnames, rows):
    with Path(path).open("w", encoding="ascii", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def export_mheat_selected(xml_path, final_table, out_dir, selected_keys=None, log=None):
    model_safe = safe_name(model_name_from_xml(xml_path))
    fieldnames, rows_by_object = read_mheatx_rows(final_table)
    selected_key_set = set(selected_keys or [])
    outputs = []

    for object_name, rows in sorted(rows_by_object.items()):
        object_keys = {
            "|".join((
                row.get("object_type", ""),
                row.get("object_name", ""),
                row.get("STREAMID", ""),
                row.get("HCURV_NO", ""),
            ))
            for row in rows
        }
        if selected_key_set:
            object_selected = selected_key_set & object_keys
        else:
            object_selected = object_keys
        filtered = [
            row for row in rows
            if "|".join((
                row.get("object_type", ""),
                row.get("object_name", ""),
                row.get("STREAMID", ""),
                row.get("HCURV_NO", ""),
            )) in object_selected
        ]
        if not filtered:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
            filtered_wide = Path(tmp.name)
        try:
            write_rows(filtered_wide, fieldnames, filtered)
            stem = f"{model_safe}_BlockMheatx_{safe_name(object_name)}"
            csv_path = Path(out_dir) / f"{stem}.csv"
            check_path = Path(out_dir) / f"{stem}_point_check.csv"
            groups = group_rows(filtered_wide)
            selected = []
            for key in sorted(groups):
                joined = "|".join(key)
                if joined not in object_selected:
                    continue
                side = curve_type(groups[key])
                if side in {"H", "C"}:
                    selected.append((key, side))
            write_curve_csv(filtered_wide, csv_path, xml_path=xml_path)
            write_blockmheatx_check_csv(groups, selected, check_path)
            outputs.extend([csv_path, check_path])
            if log:
                log(f"MHEAT {object_name}: CSV {csv_path}")
        finally:
            filtered_wide.unlink(missing_ok=True)
    return outputs


def merge_dat_files(dat_files, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="ascii", newline="\n") as dst:
        for index, dat_file in enumerate(dat_files):
            text = Path(dat_file).read_text(encoding="ascii")
            if index and not text.startswith("\n"):
                dst.write("\n")
            dst.write(text.rstrip())
            dst.write("\n")
    return out_path


def export_all(xml_path, out_dir=None, selected_mheat_keys=None, log=None):
    out_dir = Path(out_dir) if out_dir else default_output_dir(xml_path)
    paths = run_parse_pipeline(xml_path, out_dir, log)
    run_standard_exports(xml_path, paths["final_table"], out_dir, log)
    export_mheat_selected(xml_path, paths["final_table"], out_dir, selected_mheat_keys, log)
    return out_dir, paths


def copy_for_delivery(files, target_dir):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for file_path in files:
        src = Path(file_path)
        if src.is_file():
            copied.append(shutil.copy2(src, target_dir / src.name))
    return copied
