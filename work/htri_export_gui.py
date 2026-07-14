#!/usr/bin/env python3
import queue
import threading
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from htri_export_pipeline import (
    default_output_dir,
    export_all,
    export_mheat_selected,
    merge_dat_files,
    mheat_curve_summary,
    run_parse_pipeline,
    run_standard_exports,
)


class HtriExportGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Aspen XML to HTRI DAT/CSV")
        self.geometry("1050x720")
        self.minsize(900, 620)

        self.xml_path = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.status = tk.StringVar(value="请选择 XML 文件")
        self.paths = None
        self.mheat_items = {}
        self.log_queue = queue.Queue()
        self.log_file = self._create_log_file()

        self._build_ui()
        self.log(f"运行日志：{self.log_file}")
        self.after(100, self._drain_log)

    def _create_log_file(self):
        log_dir = Path.home() / "Documents" / "HTRI_XML_Exporter" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"htri_export_{datetime.now():%Y%m%d_%H%M%S}.log"

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="XML 文件").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(top, textvariable=self.xml_path).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(top, text="选择", command=self.choose_xml).grid(row=0, column=2, padx=(8, 0), pady=3)

        ttk.Label(top, text="输出目录").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(top, textvariable=self.out_dir).grid(row=1, column=1, sticky="ew", pady=3)
        ttk.Button(top, text="选择", command=self.choose_out_dir).grid(row=1, column=2, padx=(8, 0), pady=3)

        actions = ttk.Frame(self, padding=(10, 0, 10, 8))
        actions.grid(row=1, column=0, sticky="ew")
        for index in range(8):
            actions.columnconfigure(index, weight=0)
        actions.columnconfigure(8, weight=1)

        ttk.Button(actions, text="解析 XML", command=self.parse_xml).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="导出 DAT/CSV", command=self.export_selected).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="一键解析并导出", command=self.parse_and_export).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="全选 MHEAT", command=lambda: self.set_mheat_selection(True)).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="清空 MHEAT", command=lambda: self.set_mheat_selection(False)).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(actions, text="合并 DAT", command=self.merge_dat).grid(row=0, column=5, padx=(0, 8))
        ttk.Button(actions, text="打开输出目录", command=self.open_output_dir).grid(row=0, column=6, padx=(0, 8))
        ttk.Label(actions, textvariable=self.status).grid(row=0, column=8, sticky="e")

        center = ttk.Panedwindow(self, orient=tk.VERTICAL)
        center.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        list_frame = ttk.Labelframe(center, text="MHEAT 曲线选择（双击切换是否导出；MHEAT 仅生成 CSV）", padding=6)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            list_frame,
            columns=("selected", "object", "stream", "curve", "side", "raw", "points"),
            show="headings",
            selectmode="extended",
        )
        headings = [
            ("selected", "导出", 70),
            ("object", "设备", 120),
            ("stream", "物流", 120),
            ("curve", "曲线", 120),
            ("side", "冷热", 90),
            ("raw", "原始点", 90),
            ("points", "输出点", 90),
        ]
        for column, label, width in headings:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self.toggle_tree_item)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        log_frame = ttk.Labelframe(center, text="日志", padding=6)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=12, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        center.add(list_frame, weight=3)
        center.add(log_frame, weight=2)

    def choose_xml(self):
        path = filedialog.askopenfilename(
            title="选择 Aspen XML",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if not path:
            return
        self.xml_path.set(path)
        if not self.out_dir.get():
            self.out_dir.set(str(default_output_dir(path)))

    def choose_out_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.out_dir.set(path)

    def log(self, text):
        line = str(text)
        self.log_queue.put(line)
        try:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def _drain_log(self):
        while True:
            try:
                text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
        self.after(100, self._drain_log)

    def run_background(self, target):
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def require_paths(self):
        xml = self.xml_path.get().strip()
        if not xml:
            messagebox.showwarning("缺少 XML", "请先选择 XML 文件。")
            return None, None
        out = self.out_dir.get().strip() or str(default_output_dir(xml))
        self.out_dir.set(out)
        return xml, out

    def parse_xml(self):
        xml, out = self.require_paths()
        if not xml:
            return

        def task():
            try:
                self.after(0, self.status.set, "解析中...")
                self.paths = run_parse_pipeline(xml, out, self.log)
                self.after(0, self.load_mheat_curves)
                self.after(0, self.status.set, "解析完成")
                self.log(f"解析完成：{self.paths['final_table']}")
            except Exception as exc:
                self.after(0, self.status.set, "解析失败")
                self.log("ERROR: " + "".join(traceback.format_exception(exc)).rstrip())
                self.after(0, messagebox.showerror, "解析失败", str(exc))

        self.run_background(task)

    def load_mheat_curves(self):
        if not self.paths:
            return
        items = mheat_curve_summary(self.paths["final_table"])
        self.tree.delete(*self.tree.get_children())
        self.mheat_items.clear()
        for item in items:
            item_id = item["key"]
            selected = "是" if item["default_selected"] else "否"
            self.mheat_items[item_id] = dict(item, selected=item["default_selected"])
            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    selected,
                    item["object_name"],
                    item["stream"],
                    item["curve"],
                    item["side"],
                    item["raw_points"],
                    item["output_points"],
                ),
            )
        self.log(f"MHEAT 可选曲线：{len(items)} 条")

    def toggle_tree_item(self, _event=None):
        for item_id in self.tree.selection():
            item = self.mheat_items.get(item_id)
            if not item:
                continue
            item["selected"] = not item["selected"]
            values = list(self.tree.item(item_id, "values"))
            values[0] = "是" if item["selected"] else "否"
            self.tree.item(item_id, values=values)

    def set_mheat_selection(self, selected):
        for item_id, item in self.mheat_items.items():
            item["selected"] = selected
            values = list(self.tree.item(item_id, "values"))
            if values:
                values[0] = "是" if selected else "否"
                self.tree.item(item_id, values=values)

    def selected_mheat_keys(self):
        return [key for key, item in self.mheat_items.items() if item.get("selected")]

    def export_selected(self):
        xml, out = self.require_paths()
        if not xml:
            return
        if not self.paths:
            messagebox.showwarning("还未解析", "请先解析 XML，或使用“一键解析并导出”。")
            return

        def task():
            try:
                self.after(0, self.status.set, "导出中...")
                run_standard_exports(xml, self.paths["final_table"], out, self.log)
                export_mheat_selected(xml, self.paths["final_table"], out, self.selected_mheat_keys(), self.log)
                self.after(0, self.status.set, "导出完成")
                self.log(f"输出目录：{out}")
            except Exception as exc:
                self.after(0, self.status.set, "导出失败")
                self.log("ERROR: " + "".join(traceback.format_exception(exc)).rstrip())
                self.after(0, messagebox.showerror, "导出失败", str(exc))

        self.run_background(task)

    def parse_and_export(self):
        xml, out = self.require_paths()
        if not xml:
            return

        def task():
            try:
                self.after(0, self.status.set, "解析并导出中...")
                out_dir, paths = export_all(xml, out, None, self.log)
                self.paths = paths
                self.after(0, self.load_mheat_curves)
                self.after(0, self.status.set, "导出完成")
                self.log(f"输出目录：{out_dir}")
            except Exception as exc:
                self.after(0, self.status.set, "失败")
                self.log("ERROR: " + "".join(traceback.format_exception(exc)).rstrip())
                self.after(0, messagebox.showerror, "执行失败", str(exc))

        self.run_background(task)

    def merge_dat(self):
        dat_files = filedialog.askopenfilenames(
            title="选择要合并的 DAT 文件",
            filetypes=[("DAT files", "*.dat"), ("All files", "*.*")],
        )
        if not dat_files:
            return
        default_dir = self.out_dir.get().strip() or str(Path(dat_files[0]).parent)
        out_path = filedialog.asksaveasfilename(
            title="保存合并后的 DAT",
            initialdir=default_dir,
            initialfile="merged.dat",
            defaultextension=".dat",
            filetypes=[("DAT files", "*.dat"), ("All files", "*.*")],
        )
        if not out_path:
            return
        try:
            merge_dat_files(dat_files, out_path)
            self.log(f"合并完成：{out_path}")
            self.status.set("DAT 合并完成")
        except Exception as exc:
            self.log("ERROR: " + "".join(traceback.format_exception(exc)).rstrip())
            messagebox.showerror("合并失败", str(exc))

    def open_output_dir(self):
        out = self.out_dir.get().strip()
        if not out:
            return
        path = Path(out)
        path.mkdir(parents=True, exist_ok=True)
        import subprocess
        subprocess.run(["open", str(path)])


if __name__ == "__main__":
    try:
        HtriExportGui().mainloop()
    except Exception as exc:
        log_dir = Path.home() / "Documents" / "HTRI_XML_Exporter" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"htri_export_crash_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_file.write_text("".join(traceback.format_exception(exc)), encoding="utf-8")
        raise
