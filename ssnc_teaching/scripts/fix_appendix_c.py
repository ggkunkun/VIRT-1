# -*- coding: utf-8 -*-
p = r'D:\Virtu模型\ssnc_teaching\docs\01_核心模块全覆盖教学.md'
s = open(p, encoding='utf-8').read()
idx = s.find('## 附录C')
if idx >= 0:
    s = s[:idx]
add = '''## 附录C：证据化 Computer-Use 控制契约（v1.2 实测，SSCNC 7.2.2.0 / FANUC 0iM 标准面板）

> 本节全部结论来自 2026-11-19 对运行中实例的 hwnd/消息级实测，非推测。

### C.1 激活通道（按优先级）
| 控件类型 | 通道 | 状态 |
|---|---|---|
| Button 子控件（面板55键、CRT软键/键盘、对话框按钮） | SendMessageW(hwnd, BM_CLICK) | 已验证产生真实响应 |
| Win32 菜单 | 枚举 GetMenu/GetSubMenu 后按命令ID发 WM_COMMAND | 已验证（9个顶层菜单全枚举） |
| 模式旋钮（自绘 Static） | 真实鼠标弧拖（见 C.2） | 已验证切至 AUTO 并驱动仿真 |
| 旋钮/大 Static 的普通点击、直线拖、BM_CLICK | — | 无效（自绘控件不吃合成消息） |

### C.2 模式选择旋钮（唯一非 Button 控件，已破解）
- 控件：操作面板对话框内 Static 控件，ID=9651（左上 96×107px，自绘旋转开关）。
- 定位：GetDlgItem(面板hwnd, 9651) 后 GetWindowRect 取实时矩形（面板随主窗移动，勿缓存坐标）。
- 手势：顺时针弧拖——按下于旋钮中心，沿半径约30px 圆弧从 -90 度拖到 +90 度（约1秒、24步），松开=前进一个模式档位。
- 档位验证（双通道）：
  1. BM_CLICK 循环启动键（ID=9518）→ 非 AUTO/MDI/示教/DNC 时弹模态「请切换到AUTO、MDI、示教或DNC模式!」；
  2. 3D 视图（AfxFrameOrView100s）逐帧像素差分：连续大位移=程序运行中。
- 实测记录：evidence/verify_auto_log.jsonl——第2个 CW 档位后循环启动，6帧中5帧运动（847163/13345/30352/856086 px），AUTO 仿真确认。
- 其余两个大旋钮：ID=9650（进给修调）、9652（主轴修调），同手势但不影响运行模式。

### C.3 必须回读的校验节点
- 每次输入后枚举可见对话框取文本，或读 CRT/3D 视图状态；禁止以「调用返回」当成功。
- 模态弹窗会禁用主窗与面板（IsWindowEnabled=0），处理完必须先解除再继续。
- 急停（ID=9506）与 JOG 类（9586/9606）行为已验证；急停弹「请释放紧停按扭!」。

### C.4 证据文件
computer_use_control_map.json（含 mode_knob_SOLVED）、opanel_dialog_templates.json（3个面板模板全控件解析）、mode_dialogs_parsed.json（794/795/800模式对话框）、controlor_panel_scan.json（Controlor DLL扫描）、verify_auto_log.jsonl、auto_hunt_log.jsonl。
'''
open(p, 'w', encoding='utf-8').write(s + add)
print('fixed appendix C')
