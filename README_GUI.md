# Aspen XML to HTRI DAT/CSV GUI

## 启动

在 macOS 上双击 `run_htri_gui.command`，或在终端执行：

```bash
python3 work/htri_export_gui.py
```

在 Windows 上双击 `run_htri_gui_windows.bat`，或在命令行执行：

```bat
python work\htri_export_gui.py
```

## Windows 打包

客户是 Windows 时，建议在 Windows 电脑上打包 `.exe`。先安装 PyInstaller：

```bat
python -m pip install pyinstaller
```

然后双击：

```text
build_windows_exe.bat
```

打包结果在：

```text
dist\HTRI_XML_Exporter
```

把整个 `HTRI_XML_Exporter` 文件夹发给客户即可。客户双击里面的 `HTRI_XML_Exporter.exe` 运行。

也可以用 GitHub Actions 打包：

1. 把代码推送到 GitHub 仓库。
2. 打开仓库的 `Actions`。
3. 选择 `Build Windows EXE`。
4. 点击 `Run workflow`。
5. 成功后下载 `HTRI_XML_Exporter_windows` artifact。

如果打包失败，GitHub Actions 页面会保留完整错误日志。

## 报错日志

程序运行时会自动生成日志文件：

```text
%USERPROFILE%\Documents\HTRI_XML_Exporter\logs
```

客户测试时如果导出失败，让客户把这个目录里最新的 `.log` 文件发回来即可。

## 功能

- 选择 Aspen XML 文件并解析 HCURVE 数据。
- 生成各模型对应的 DAT/CSV：
  - BlockHeater：DAT + CSV
  - BlockHeatx：DAT + CSV
  - BlockRadfrac：HOT/COLD 两个 DAT + CSV
  - BlockMcompr：最多 10 个 DAT + CSV，并输出曲线选择表
  - BlockMheatx：仅 CSV
- MHEAT 曲线可在界面中选择，双击曲线行可切换是否导出。
- 可选择多个 DAT 文件并合并成一个 DAT。

## 使用建议

如果需要手动挑 MHEAT 曲线，先点击“解析 XML”，在列表里勾选曲线后，再点击“导出 DAT/CSV”。

如果不需要挑选，直接点击“一键解析并导出”，会按默认规则导出所有有效 MHEAT 曲线。
