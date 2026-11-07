---
name: windows-industrial-desktop-automation
description: >-
  Precision Windows desktop GUI automation, mouse/keyboard control, screen perception,
  and specialized CAD/CAM software (SOLIDWORKS, AutoCAD, NX, Vericut, CIMCO, SSCNC) manipulation
  for autonomous AI Agents. Use when an AI Agent needs to capture the screen, click buttons,
  type text, trigger shortcuts, manage CAD windows, or execute end-to-end desktop operations on Windows.
version: 1.0.0
tags: [desktop-automation, windows-gui, computer-use, cad-cam, mouse-keyboard, screen-ocr]
---

# Windows Industrial Desktop Automation Skill

Empowers the AI Agent with direct, deterministic Windows desktop control, perception, and industrial CAD/CAM GUI orchestration.

## Capabilities & Architecture

1. **Screen Perception**:
   - High-speed GDI / PIL full-screen and window region capture.
   - Coordinate grid overlays and visual anchoring.
2. **Precision Input Control**:
   - Native Windows API (`pywin32` / `SendInput` / `pyautogui`) mouse click, double click, right click, drag, scroll.
   - Keyboard character entry, multi-key hotkeys (`Ctrl+S`, `Alt+F`, `F5`, `Esc`).
3. **Window Lifecycle & Focus Management**:
   - Enumerate all running top-level windows, HWND handles, titles, and bounding rectangles.
   - Force foreground activation (`SetForegroundWindow`, `ShowWindow(SW_RESTORE)`).
4. **CAD/CAM GUI Automation**:
   - Window targeting for `SLDMAIN.EXE` (SOLIDWORKS), `acad.exe` (AutoCAD), `ugraf.exe` (NX), `vericut.exe`, `cimco.exe`, `sscnc.exe`.
   - Dialog handling (File Open, Save As, Overwrite Confirmation, Error Alert dismissal).
   - Viewport navigation (pan, rotate, zoom, fit to window `F`).

---

## User Screen Hardware Profile & CAD/CAM Coordinate Layout (1920x1080 @ 125% DPI)

针对用户当前 `1920 x 1080` (工作区: `1920 x 1020`，底部任务栏: `60px`) 屏幕配置，主流工业软件窗口最大化状态下的绝对物理坐标基准如下：

### 1. SOLIDWORKS 2021 典型界面布局
- **顶部 CommandManager / 工具栏**: `y: 0 ~ 125`，草图/特征标签页切换位: `(180, 45)`、`(240, 45)`
- **左侧 FeatureManager 设计树 / 属性管理器**: `x: 0 ~ 320`，`y: 125 ~ 985`
- **中央 3D 建模图形视口 (Graphics Viewport)**: `x: 320 ~ 1680`，`y: 125 ~ 985` (中心点: `(1000, 555)`)
- **右侧任务窗格 (Task Pane)**: `x: 1680 ~ 1920`，`y: 125 ~ 985`
- **底部状态栏 (Status Bar)**: `y: 985 ~ 1020` (提示当前处于“正在编辑零件/草图”)

### 2. Autodesk AutoCAD 2026 典型界面布局
- **顶部功能区 (Ribbon Panels)**: `y: 0 ~ 140`，常用绘图/修改命令区: `x: 50 ~ 600`
- **左上 UCS 视口控件 / 视图立方体 (ViewCube)**: `x: 1720 ~ 1880`，`y: 160 ~ 320`
- **主绘图区 (Model Space Viewport)**: `x: 30 ~ 1920`，`y: 140 ~ 960`
- **底部浮动命令行 (Command Line Window)**: `x: 350 ~ 1570`，`y: 960 ~ 1005`
- **底部辅助绘图状态栏 (OSNAP/ORTHO/DYN)**: `x: 1200 ~ 1920`，`y: 1005 ~ 1020`

### 3. Siemens NX 12.0 典型界面布局
- **顶部 Ribbon 选项卡与快捷工具栏**: `y: 0 ~ 130`
- **左侧资源条与部件导航器 (Part Navigator)**: `x: 0 ~ 300`，`y: 130 ~ 980`
- **中央主建模视口**: `x: 300 ~ 1920`，`y: 130 ~ 980`
- **底部状态行与提示行**: `y: 980 ~ 1020`

---

## Tool API Reference

### 1. Screen Capture
```bash
python scripts/desktop_controller.py capture --output screenshot.png
python scripts/desktop_controller.py capture --window "SOLIDWORKS" --output sw_view.png
python scripts/desktop_controller.py capture --region 100,100,800,600 --output region.png
```

### 2. Window Discovery & Focus
```bash
python scripts/desktop_controller.py list-windows
python scripts/desktop_controller.py focus --title "SOLIDWORKS"
```

### 3. Mouse & Keyboard Execution
```bash
# Click at specific coordinate
python scripts/desktop_controller.py click --x 450 --y 320
python scripts/desktop_controller.py dblclick --x 450 --y 320
python scripts/desktop_controller.py right-click --x 450 --y 320

# Drag between coordinates
python scripts/desktop_controller.py drag --start 200,200 --end 600,400

# Keyboard typing and hotkeys
python scripts/desktop_controller.py type --text "C:\\Projects\\gear_assembly.SLDPRT"
python scripts/desktop_controller.py hotkey --keys "ctrl,s"
python scripts/desktop_controller.py hotkey --keys "alt,f4"
```

### 4. CAD Specialized Routine
```bash
python scripts/cad_gui_bridge.py new-part --software solidworks
python scripts/cad_gui_bridge.py export-step --path "D:\\Output\\part.step"
python scripts/cad_gui_bridge.py dismiss-dialogs
```
