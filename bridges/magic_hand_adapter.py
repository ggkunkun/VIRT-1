"""MagicHand（magic-hand-windows skill）→ 结构化工具适配器。

把 skill 的 CLI 包装成与 Windows-MCP `tools/call` 同形的接口，
使 13.63B 规划器能像调用 MCP 工具一样调用 computer-use skill。

- 绝大多数 action 映射到 `scripts/cu_ui.py` 的原生子命令；
- `clipget/clipset` 映射到 `scripts/clip.py`，`move` 映射到 `scripts/winmove.py`；
- `launch+file` 由适配器用 notepad.exe 打开**我们自己的临时空白文件**，
  避免误写用户已打开的文件（本机实测发现用户记事本里有 .nc 加工程序）。

安全：
- 只操作前台可见窗口；不删除、不退出、不保存用户文件。
- `clipset` 会覆盖剪贴板，适配器自动保存原内容并在 close() 时恢复。
- `ok:true` 不等于生效；所有返回文本都保留原始输出，由验收做逐字证据核对。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(r"C:\Users\Administrator\.workbuddy\skills\magic-hand-windows\scripts")
PY = sys.executable

ACTIONS = ["probe", "apps", "launch", "tree", "focus", "info", "click", "set",
           "type", "key", "shot", "shotpng", "activate", "clipget", "clipset",
           "move", "winlist", "xy", "drag", "scroll", "seltext", "act"]
WRITE_ACTIONS = {"launch", "focus", "click", "set", "type", "key", "activate",
                 "clipset", "move", "shot", "shotpng", "xy", "drag", "scroll",
                 "seltext", "act"}

DESCRIPTION = (
    "Windows 桌面操控（computer use / 妙控手 skill）。用 Win32 HWND 树按索引精准操作，"
    "每步可回读验证。action: probe=确认 WinSta0 会话；apps=列出运行中的应用；"
    "launch=启动应用（带 file 时打开指定空白文件）；tree=读带索引的 HWND 树；"
    "focus=把应用提到前台；info/click/set=按树索引读/点/写；type=向当前焦点打字；"
    "key=按键或组合键（如 ctrl+v）；clipset/clipget=剪贴板写/读；"
    "move=按 rect 移动窗口；winlist=列出窗口 hwnd/pid/rect（客观取证）；"
    "shot/shotpng=截图(BMP)/截图转 PNG；xy=归一化坐标点击；drag=拖拽；"
    "scroll=滚动；seltext=选中文本；act=命名动作(press/click/setfocus/show)。"
    "注意：ok:true 不是证明，必须用 tree / winlist 回读目标状态。"
)


def _schema():
    return {
        "name": "MagicHand",
        "description": DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ACTIONS,
                           "description": "要执行的桌面动作"},
                "app": {"type": "string", "description": "应用名 / pid / exe 子串，如 notepad"},
                "idx": {"type": "integer", "description": "HWND 树里的行首整数索引"},
                "text": {"type": "string", "description": "set / type / clipset 的文本"},
                "combo": {"type": "string", "description": "key 的组合键，如 ctrl+v、ctrl+a"},
                "file": {"type": "string", "description": "launch 时要打开的空白文件路径"},
                "rect": {"type": "array", "items": {"type": "integer"},
                         "description": "move 的 [x,y,宽度,高度]（winmove.py 语义），"
                                        "不是 GetWindowRect 的 [l,t,r,b]；winlist 返回后者，"
                                        "需换算成 [l,t,r-l,b-t] 再传入"},
                "depth": {"type": "integer", "description": "tree 深度，默认 10"},
                "wait": {"type": "number", "description": "launch 后等待秒数"},
                "nx": {"type": "number", "description": "xy 的窗口归一化横坐标 0-1000"},
                "ny": {"type": "number", "description": "xy 的窗口归一化纵坐标 0-1000"},
                "x": {"type": "number", "description": "绝对横坐标 / drag 起点"},
                "y": {"type": "number", "description": "绝对纵坐标 / drag 起点"},
                "x2": {"type": "number", "description": "drag 终点横坐标"},
                "y2": {"type": "number", "description": "drag 终点纵坐标"},
                "win": {"type": "integer", "description": "xy 的窗口序号"},
                "direction": {"type": "string", "description": "scroll 方向 up/down"},
                "pages": {"type": "number", "description": "scroll 页数"},
                "name": {"type": "string", "description": "act 的动作名 press/click/setfocus/show"},
                "path": {"type": "string", "description": "shot/shotpng 输出路径"},
            },
            "required": ["action"]}}


# 每个 action 需要的参数（用于按任务动态裁剪工具面，避免 13.63B 在大 schema 下超时）
ACTION_PARAMS = {
    "probe": [], "apps": [], "clipget": [], "shot": ["path"], "shotpng": ["path"],
    "tree": ["app", "depth"], "info": ["app", "idx"], "winlist": ["app"],
    "focus": ["app"], "activate": ["app"], "launch": ["app", "wait", "file"],
    "set": ["app", "idx", "text"], "type": ["text"], "key": ["combo"],
    "clipset": ["text"], "move": ["app", "rect"],
    "xy": ["app", "win", "nx", "ny", "x", "y"], "drag": ["x", "y", "x2", "y2"],
    "scroll": ["app", "direction", "pages", "idx"],
    "seltext": ["app", "idx", "text"], "act": ["app", "idx", "name"],
    "click": ["app", "idx"],
}


def slim_schemas(actions: list[str]) -> list[dict]:
    """按任务只暴露必要 action 与参数。

    实测依据：全量 22 action / 20 参数（brief 853 字符）下 13.63B 语法约束规划
    3/3 超时；精简到 6 action / 5 参数（brief 186 字符）后同一任务一次通过。
    """
    wanted = [a for a in actions if a in ACTIONS]
    full = _schema()
    props = full["inputSchema"]["properties"]
    keep = {"action"}
    for a in wanted:
        keep.update(ACTION_PARAMS.get(a, []))
    return [{"name": "MagicHand",
             "description": "Windows 桌面操控（computer use）。可用动作：" + ", ".join(wanted)
                            + "。ok:true 不是证明，必须用 tree / winlist 回读目标状态。",
             "inputSchema": {"type": "object",
                             "properties": {**{"action": {"type": "string", "enum": wanted}},
                                            **{k: props[k] for k in keep if k != "action" and k in props}},
                             "required": ["action"]}}]


class MagicHandAdapter:
    name = "MagicHand"

    def __init__(self, evidence_dir: Path | None = None):
        self.evidence_dir = evidence_dir
        self._clipboard_original = None
        self._clipboard_saved = False
        self.calls: list[dict] = []

    def schemas(self) -> list[dict]:
        return [_schema()]

    # ------------------------------------------------------------------ internals
    def _run(self, script: str, *argv, timeout: int = 90) -> dict:
        try:
            p = subprocess.run([PY, script, *[str(a) for a in argv]],
                               cwd=str(SCRIPTS), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        except Exception as e:
            return {"rc": -1, "stdout": "", "stderr": f"{type(e).__name__}: {e}"}
        return {"rc": p.returncode, "stdout": (p.stdout or "").strip(),
                "stderr": (p.stderr or "").strip()[:400]}

    @staticmethod
    def _format_tree(raw: str) -> str:
        """tree --json → 可逐字引用的可读文本（模型与验收都靠它取证据）。"""
        try:
            d = json.loads(raw)
        except Exception:
            return raw[:2500]
        lines = [f"app: {d.get('app')} (pid {d.get('pid')}, exe {d.get('exe')})  "
                 f"nodes: {d.get('count')}"]
        for w in d.get("windows") or []:
            lines.append(f"window idx={w.get('idx')} \"{w.get('title')}\"")
        for n in d.get("nodes") or []:
            title = str(n.get("title") or "").replace("\r", " ").replace("\n", " ")
            lines.append(f"[{n.get('i')}] {n.get('role')} sub={n.get('sub')} "
                         f"title=\"{title[:220]}\"")
        return "\n".join(lines)[:3000]

    def _save_clipboard(self):
        if self._clipboard_saved:
            return
        r = self._run("clip.py", "get")
        self._clipboard_original = r["stdout"] if r["rc"] == 0 else None
        self._clipboard_saved = True
        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)
            (self.evidence_dir / "clipboard_before.json").write_text(
                json.dumps({"length": len(self._clipboard_original or ""),
                            "saved": self._clipboard_original is not None},
                           ensure_ascii=False, indent=2), encoding="utf-8")

    def restore(self):
        """结束时恢复剪贴板原内容，避免把用户剪贴板留在测试文本上。"""
        if self._clipboard_saved and self._clipboard_original is not None:
            self._run("clip.py", "set", self._clipboard_original)
            return True
        return False

    def _resolve_editable_idx(self, app: str) -> int:
        """set 未给 idx 时，从 HWND 树自动定位第一个可见可编辑控件。"""
        r = self._run("cu_ui.py", "tree", app, "--depth", "10", "--json")
        try:
            d = json.loads(r["stdout"])
            cand = [n for n in d.get("nodes", []) if n.get("visible") and (
                n.get("role") in ("Edit", "RichEdit") or
                "RichEdit" in str(n.get("sub")) or "TextBox" in str(n.get("sub")))]
            return cand[0]["i"] if cand else 0
        except Exception:
            return 0

    def _set_paste_fallback(self, app: str, value: str, raw: str) -> tuple[str, str]:
        """实测依据：新版记事本 RichEditD2DPT 对 WM_SETTEXT/WM_CHAR 返回 ok:true 但文本不落地。

        当 set 的目标是顶层窗口、或走 win:type 且非编辑控件时，改用
        clipset -> focus -> key ctrl+v，并用 tree 回读判定是否真的落地。
        """
        try:
            d = json.loads(raw)
        except Exception:
            return raw, "cu_ui.py"
        bad = (d.get("role") == "Window" or d.get("idx") == 0 or
               (d.get("method") == "win:type" and "Edit" not in str(d.get("role"))))
        if not bad:
            return raw, "cu_ui.py"
        self._save_clipboard()
        steps = [self._run("clip.py", "set", value),
                 self._run("cu_ui.py", "focus", app)]
        time.sleep(0.25)
        steps.append(self._run("cu_ui.py", "key", "ctrl+v"))
        time.sleep(0.7)
        tr = self._run("cu_ui.py", "tree", app, "--depth", "10", "--json")
        landed = value in (tr["stdout"] or "")
        out = {"ok": landed, "impl": "paste_fallback",
               "reason": "set 目标为顶层窗口 / WM_CHAR 在本机不生效，改走剪贴板粘贴",
               "original_set": d, "verified_by_tree": landed, "text": value}
        self.calls.append({"action": "paste_fallback",
                           "argv": ["clip.py set", "cu_ui.py focus",
                                    "cu_ui.py key ctrl+v", "cu_ui.py tree"],
                           "impl": "paste_fallback", "rc": 0 if landed else 1,
                           "out": json.dumps(out, ensure_ascii=False)[:600]})
        return json.dumps(out, ensure_ascii=False), "paste_fallback"

    # ------------------------------------------------------------------ public
    def call(self, name: str, args: dict) -> dict:
        if name != self.name:
            return {"text": f"[SKILL ERROR] unknown tool {name}", "is_error": True}
        action = str(args.get("action") or "")
        app = args.get("app")
        impl = "cu_ui.py"
        argv = []
        local_launch = False

        if action == "probe":
            argv = ["probe"]
        elif action == "apps":
            argv = ["apps"]
        elif action == "launch":
            if args.get("file"):
                # 适配器本地启动：cu_ui.py launch 不支持附带文件参数
                f = Path(str(args["file"]))
                f.parent.mkdir(parents=True, exist_ok=True)
                if not f.exists():
                    f.write_text("", encoding="utf-8")
                try:
                    subprocess.Popen(["notepad.exe", str(f)])
                    time.sleep(float(args.get("wait") or 2.5))
                    out = {"ok": True, "via": "local_notepad_with_tempfile", "file": str(f)}
                    text = json.dumps(out, ensure_ascii=False)
                    impl = "local_launch_for_temp_file"
                    self.calls.append({"action": action, "argv": ["notepad.exe", str(f)],
                                       "impl": impl, "rc": 0, "out": text[:600]})
                    return {"text": text, "is_error": False, "argv": ["notepad.exe", str(f)],
                            "impl": impl}
                except Exception as e:
                    return {"text": f"[SKILL ERROR] launch failed: {e}", "is_error": True}
            else:
                argv = ["launch", str(app or "notepad"), "--wait", str(args.get("wait") or 2.5)]
        elif action == "tree":
            argv = ["tree", str(app), "--depth", str(args.get("depth") or 10), "--json"]
        elif action == "focus":
            argv = ["focus", str(app)]
        elif action == "activate":
            argv = ["activate", str(app)]
        elif action == "info":
            argv = ["info", str(app), str(args.get("idx") or 0)]
        elif action == "click":
            argv = ["click", str(app), str(args.get("idx") or 0)]
        elif action == "set":
            idx = args.get("idx")
            if idx is None:
                idx = self._resolve_editable_idx(str(app))
            argv = ["set", str(app), str(idx), str(args.get("text") or "")]
        elif action == "type":
            argv = ["type", str(args.get("text") or "")]
        elif action == "key":
            # 参数别名归一化：模型偶尔把组合键写进 text
            combo = args.get("combo") or args.get("text") or ""
            argv = ["key", str(combo)]
        elif action == "shot":
            argv = ["shot"] + (["--path", str(args["path"])] if args.get("path") else [])
        elif action == "shotpng":
            bmp = str(args.get("path") or (Path(self.evidence_dir or Path(".")) / "cu_shot.bmp"))
            png = str(Path(bmp).with_suffix(".png"))
            Path(bmp).parent.mkdir(parents=True, exist_ok=True)
            r0 = self._run("cu_ui.py", "shot", "--path", bmp)
            r1 = self._run("bmp2png.py", bmp, png)
            out = {"ok": r0["rc"] == 0 and r1["rc"] == 0,
                   "bmp": bmp, "png": png,
                   "png_exists": Path(png).is_file(),
                   "png_bytes": Path(png).stat().st_size if Path(png).is_file() else 0,
                   "convert_out": r1["stdout"][:200]}
            self.calls.append({"action": "shotpng", "argv": [bmp, png],
                               "impl": "cu_ui.py+bmp2png.py", "rc": 0 if out["ok"] else 1,
                               "out": str(out)[:600]})
            return {"text": json.dumps(out, ensure_ascii=False), "is_error": not out["ok"],
                    "argv": [bmp, png], "impl": "cu_ui.py+bmp2png.py"}
        elif action == "winlist":
            impl = "winmove.py"
            script, argv = "winmove.py", ["--list", str(app)]
        elif action == "xy":
            if args.get("nx") is not None and args.get("ny") is not None:
                argv = ["xy", "--app", str(app), "--win", str(args.get("win") or 0),
                        "--nx", str(args["nx"]), "--ny", str(args["ny"])]
            else:
                argv = ["xy", str(args.get("x") or 0), str(args.get("y") or 0)]
        elif action == "drag":
            argv = ["drag", str(args.get("x") or 0), str(args.get("y") or 0),
                    str(args.get("x2") or 0), str(args.get("y2") or 0)]
        elif action == "scroll":
            argv = ["scroll", str(args.get("direction") or "down"),
                    "--app", str(app), "--pages", str(args.get("pages") or 1)]
            if args.get("idx") is not None:
                argv += ["--idx", str(args["idx"])]
        elif action == "seltext":
            argv = ["seltext", str(app), str(args.get("idx") or 0),
                    str(args.get("text") or ""), "--mode", "select"]
        elif action == "act":
            argv = ["act", str(app), str(args.get("idx") or 0),
                    str(args.get("name") or "press")]
        elif action == "clipget":
            impl = "clip.py"
            script, argv = "clip.py", ["get"]
        elif action == "clipset":
            self._save_clipboard()
            impl = "clip.py"
            script, argv = "clip.py", ["set", str(args.get("text") or "")]
        elif action == "move":
            impl = "winmove.py"
            rect = args.get("rect") or []
            script = "winmove.py"
            argv = [str(app), "--rect", *[str(x) for x in rect[:4]]]
        else:
            return {"text": f"[SKILL ERROR] unsupported action {action!r}", "is_error": True}

        script = script if action in ("clipget", "clipset", "move", "winlist") else "cu_ui.py"
        r = self._run(script, *argv)
        raw_text = r["stdout"] or r["stderr"]
        # 必须在格式化之前判定 ok:false —— 第一轮全面测试发现 tree 的
        # app_not_found 被 _format_tree 改写后以 "app:" 开头，绕过了错误检测。
        pre_error = False
        if raw_text.startswith("{"):
            try:
                pre_error = json.loads(raw_text).get("ok") is False
            except Exception:
                pass
        text = self._format_tree(raw_text) if (action == "tree" and r["rc"] == 0) else raw_text
        if action == "set" and r["rc"] == 0:
            text, impl = self._set_paste_fallback(str(app),
                                                  str(args.get("text") or ""), text)
        is_error = r["rc"] != 0 or pre_error
        if not is_error and text.startswith("{"):
            try:
                is_error = json.loads(text).get("ok") is False
            except Exception:
                pass
        self.calls.append({"action": action, "argv": argv, "impl": impl,
                           "rc": r["rc"], "out": text[:600]})
        return {"text": text[:3000], "is_error": is_error, "argv": argv, "impl": impl}
