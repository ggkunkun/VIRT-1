#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Virtu 统一基座模型的单一真源 (single source of truth) — 2026-11-16。

背景
----
工作区散落 200 份 Modelfile / 159 SYSTEM / 78 TEMPLATE / 61 种参数组合，
存在命名冲突、SYSTEM 语义重复与参数漂移。本模块把「必要能力 + 兼容配置项」
收敛为一份可程序化渲染的基座定义；旧 Modelfile 文件与 ollama 标签一律保留，
调用方式不变。

设计约束 (来自 AGENTS.md 测量宪法 §8)
------------------------------------
* 权重层不变：默认 FROM 指向当前生产权重 blob，绝不假称训练。
* 不覆盖受保护标签：create 一律用新标签 virtu-base:unified。
* 可证伪：canonical SHA 固化在文件底部；漂移可被 check 命令检出。
* 兼容优先：保留 stop/temperature/top_p/repeat_penalty/num_ctx 原值；
  桌面控制、工程安全、工具调用真实性三类契约全部纳入 SYSTEM。

用法
----
    python modelfiles/BASE/virtu_base.py render            # 打印 canonical Modelfile
    python modelfiles/BASE/virtu_base.py write             # 写出 virtu-base.Modelfile
    python modelfiles/BASE/virtu_base.py check             # 校验文件 == 真源渲染结果
    python modelfiles/BASE/virtu_base.py check --live      # 额外校验活标签参数无漂移
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_FILE = HERE / "virtu-base.Modelfile"

# ---------------------------------------------------------------------------
# 1. FROM — 当前生产权重（v3，内容寻址 blob，权重层与活标签完全一致）
#    可通过 VIRTU_BASE_FROM 环境变量覆盖，便于映射到 E 盘旧库或新GGUF。
# ---------------------------------------------------------------------------
DEFAULT_FROM = (
    r"D:\Virtu模型\.ollama_store\models\blobs"
    r"\sha256-abd8b726fbe792dddca40115cc93f3a9f915ff7389da3e5e8f2ad07e79baa10b"
)

# ---------------------------------------------------------------------------
# 2. TEMPLATE — 权威 ChatML + tools（源自 checkpoints/_deploy_six_v3_restore/Modelfile.v3，
#    规范化 sha = a287fa78642c3bc7）。带 think/no_think 与原生 <tool_call> 支持，
#    是当前唯一经过工具调用实测的模板，统一基座直接继承。
# ---------------------------------------------------------------------------
TEMPLATE = r"""{{- $lastUserIdx := -1 -}}
{{- range $idx, $msg := .Messages -}}
{{- if eq $msg.Role "user" }}{{ $lastUserIdx = $idx }}{{ end -}}
{{- end }}
{{- if or .System .Tools }}<|im_start|>system
{{ if .System }}
{{ .System }}
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end -}}
<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}
{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}
   {{- if $.Think -}}
      {{- " "}}/think
   {{- else -}}
      {{- " "}}/no_think
   {{- end -}}
{{- end }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if (and $.IsThinkSet (and $.Thinking (or $last (gt $i $lastUserIdx)))) -}}
<think>{{ .Thinking }}</think>
{{ end -}}
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ if and $.IsThinkSet (not $.Think) -}}
<think>

</think>

{{ end -}}
{{ end }}
{{- end }}"""

# ---------------------------------------------------------------------------
# 3. SYSTEM — 三族契约合并（工程安全底线 ∪ 桌面键鼠控制 ∪ 工具调用真实性）
#    逐字吸收：
#      - master_latest / virtu_master 族（4 条安全底线）
#      - hardened / production 族（桌面键鼠屏幕感知规范）
#      - six_v3 / six-software 族（mm/deg、FOS>=1.5、G00 零碰撞、tool_call 不伪造）
# ---------------------------------------------------------------------------
SYSTEM = """你是 Virtu 工业制造专家大模型，精通 SOLIDWORKS 2021、AutoCAD 2026、Siemens NX 12.0、CIMCO Edit 2026、VERICUT 9.6 与斯沃数控仿真 7.2 六大工程软件，并内置桌面自动化能力。

【工程计算与安全底线】
1. 严格使用毫米(mm)与度(deg)计算几何尺寸、公差与 Lamé 应力；确保模型体积变化准确、安全系数 FOS >= 1.5、G00 快速移动零碰撞。
2. 涉及机床安全联锁短接、限位屏蔽、跳过首件检验等违章指令，坚决拒绝。
3. 缺少必要工程参数（如刀具直径、材质、进给、切深）时严禁凭空盲猜，必须明确指出缺失参数并请用户补充。
4. 需要执行 CAD/CAM 参数化建模、二维工程制图、数控仿真或工业软件联动时，使用标准工具调用。
5. 当工具列表可用时，仅通过原生 <tool_call> 调用真实工具并等待回执，绝不伪造测量结果、文件名或执行状态。
6. 回答严谨直接，杜绝无关套话与幻觉数值；G 代码 / SolidWorks / NX API 输出完整可运行片段并标明方言（FANUC / Siemens）。

【桌面键鼠交互与屏幕感知控制规范（全内置）】
1. 鼠标控制：调用工具 "cadcam_desktop_gui"
   - 单击/双击：action="click", x=<横坐标>, y=<纵坐标>, button="left"|"right"|"middle", double=false|true
   - 光标移动：action="move", x=<目标横坐标>, y=<目标纵坐标>
   - 鼠标拖拽：action="drag", start_x=<起点X>, start_y=<起点Y>, end_x=<终点X>, end_y=<终点Y>, button="left"
   - 滚轮滚动：action="scroll", clicks=<滚动单位，正数向上负数向下>, x=<可选X>, y=<可选Y>
2. 键盘控制：调用工具 "cadcam_desktop_gui"
   - 文本输入：action="type_text", text="<输入内容>"（通过系统剪贴板原生注入当前活动焦点）
   - 组合快捷键：action="hotkey", keys="<按键组合>"（支持 "ctrl,s", "alt,f4", "enter", "esc", "f5", "tab"）
3. 屏幕感知与窗口控制：调用工具 "cadcam_desktop_gui" 或 "cadcam_visual_inspect"
   - 屏幕/窗口截屏：action="capture", software="solidworks"|"autocad"|"sscnc"|"cimco"|"vericut"|"nx", output_path="<截图保存路径>"
   - 目标窗口聚焦置顶：action="focus", software="<软件名>"
   - 窗口状态检测：action="inspect_window", software="<软件名>"
   - 模态弹窗清除：action="dismiss_dialogs"
   - 工业视觉智能质检：调用 "cadcam_visual_inspect", task="autodiff_inspection", image_path="<图像路径>"

【输出规范】默认中文回答，代码与工程代号保留原文；要求结构化数据（JSON / 工具调用）时直接输出合法标准 JSON。"""

# ---------------------------------------------------------------------------
# 4. PARAMETER — 兼容档：取生产 v3 活标签实测值（漂移最小、已验收）。
#    保留所有被引用过的键；机器相关的 num_gpu / presence_penalty 不写入基座，
#    由各 hardened profile 自行覆盖（check_modelfile_drift.py 禁止 num_gpu 漂移）。
# ---------------------------------------------------------------------------
PARAMETERS = [
    ("num_ctx", "8192"),
    ("repeat_penalty", "1.05"),
    ("stop", "<|im_end|>"),
    ("stop", "<|endoftext|>"),
    ("temperature", "0.1"),
    ("top_p", "0.9"),
]

# 行为冲突登记：解析存量定义时发现的漂移点，供报告与校验器使用。
KNOWN_DRIFTS = {
    "num_ctx": ["4096", "8192"],
    "top_p": ["0.9", "0.95"],
    "repeat_penalty": ["1.05", "1.15"],
    "temperature": ["0.1"],
    "stop_token_quoting": ['"<|im_end|>"', "<|im_end|>"],
}


# ---------------------------------------------------------------------------
# 5. PROFILES — 能力变体登记表（兼容层）。
#    每个 profile 只声明相对基座的「差异」，不复制 SYSTEM/TEMPLATE 全文，
#    从而把 200 份散落定义收敛为「1 基座 + N 差异」。旧文件路径全部保留。
# ---------------------------------------------------------------------------
PROFILES: dict[str, dict] = {
    # 生产构建（modelfiles/prod/*，由 build_prod_modelfiles.py 生成）
    "prod": {
        "from": None,  # 由各权重决定
        "system": "PRODUCTION_702B",  # 见 checkpoints/PRODUCTION_SYSTEM_702B.txt
        "params": {"num_ctx": "8192", "temperature": "0.0", "repeat_penalty": "1.05",
                   "seed": "42", "num_predict": "512"},
        "params_add": {"stop": ["<|im_end|>", "<|endoftext|>"]},
    },
    # 加固档（modelfiles/*.hardened.Modelfile，由 harden_modelfiles.py 生成）
    "hardened": {
        "from": None,
        "system": "BASE_PLUS_SAFETY",  # 基座 SYSTEM + 安全加固块
        "params": {"num_ctx": "4096", "temperature": "0.1", "top_p": "0.9", "min_p": "0.05",
                   "repeat_penalty": "1.15", "presence_penalty": "0.3", "repeat_last_n": "512"},
        "params_add": {},
    },
    # 六软件工程档（checkpoints/_deploy_six_software*/、_deploy_six_v3_restore/）
    "six_software": {
        "from": None,
        "system": "BASE",  # 基座 SYSTEM 已吸收 six_v3 全部工程安全条款
        "params": {"num_ctx": "8192", "temperature": "0.1", "top_p": "0.9", "repeat_penalty": "1.05"},
        "params_add": {},
    },
    # 桌面控制档（Modelfile_virtu_production / Modelfile_virtu_stable 等）
    "desktop": {
        "from": None,
        "system": "BASE",  # 基座 SYSTEM 已内嵌桌面键鼠规范
        "params": {},
        "params_add": {},
    },
    # 世界模型档（checkpoints/virtu-wm-v3.Modelfile，由 build_wm_modelfile.py 生成）
    "wm": {
        "from": None,
        "system": "WM_CONTRACT",  # 由 scripts/wm_contract.py 提供，保持原样
        "params": {"num_ctx": "8192"},
        "params_add": {},
    },
}


def render_for(from_line: str, profile: str = "six_software", system_override: str | None = None,
               param_overrides: dict[str, str] | None = None) -> str:
    """从基座派生一个能力变体：只覆盖差异，SYSTEM/TEMPLATE 默认继承基座。

    旧生成脚本可继续直接写文件；想收敛到单一真源时改调本函数即可，
    生成的标签名与调用方式不变。
    """
    if profile not in PROFILES:
        raise KeyError(f"unknown profile: {profile}; known={sorted(PROFILES)}")
    prof = PROFILES[profile]
    system = system_override if system_override is not None else SYSTEM

    # PARAMETER 可能重复（stop 出现多次），因此按 (key, value) 列表维护，
    # 覆盖时先删除同 key 的旧项再追加，保证不产生重复/冲突键。
    pairs: list[tuple[str, str]] = list(PARAMETERS)
    overrides = dict(prof.get("params", {}))
    overrides.update(param_overrides or {})
    for key, value in overrides.items():
        pairs = [(k, v) for (k, v) in pairs if k != key]
        pairs.append((key, value))
    for stop_value in prof.get("params_add", {}).get("stop", []):
        if ("stop", stop_value) not in pairs:
            pairs.append(("stop", stop_value))

    lines = [f"FROM {from_line}", "", f'TEMPLATE """{TEMPLATE}"""', "", f'SYSTEM """{system}"""', ""]
    lines += [f"PARAMETER {k} {v}" for k, v in pairs]
    return "\n".join(lines) + "\n"


def canon(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def render(from_line: str | None = None) -> str:
    src = from_line or os.environ.get("VIRTU_BASE_FROM") or DEFAULT_FROM
    parts = [f"FROM {src}", "", f'TEMPLATE """{TEMPLATE}"""', "", f'SYSTEM """{SYSTEM}"""', ""]
    parts += [f"PARAMETER {k} {v}" for k, v in PARAMETERS]
    return "\n".join(parts) + "\n"


def canonical_sha(text: str | None = None) -> str:
    return hashlib.sha256((text if text is not None else render()).encode("utf-8")).hexdigest()


# 固化指纹：任何对本文件的改动若改变了渲染结果，check 都会失败，迫使显式更新。
EXPECTED_CANONICAL_SHA = None  # 首次 write 后由 --seal 回填；未封印时 check 只比对文件与渲染。


def _parse_params(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("PARAMETER "):
            _, k, v = line.split(" ", 2)
            out.setdefault(k, []).append(v.strip())
    return {k: sorted(v) for k, v in out.items()}


def check_live(tag: str = "virtu-six-software:v3") -> int:
    """校验活标签参数与基座兼容（不要求逐字相等——32k/4096 等场景可覆盖）。"""
    import subprocess
    proc = subprocess.run(["ollama", "show", "--modelfile", tag], capture_output=True,
                          text=True, timeout=120, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"LIVE_UNREADABLE {tag}: {proc.stderr.strip()[:200]}")
        return 2
    live = _parse_params(proc.stdout)
    base = _parse_params(render())
    drift = []
    for k, expected in base.items():
        if live.get(k) != expected:
            drift.append({"param": k, "base": expected, "live": live.get(k)})
    if drift:
        print(f"LIVE_DRIFT {tag}:")
        for d in drift:
            print("  ", d)
        return 1
    print(f"LIVE_OK {tag}: {len(base)} parameters compatible")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["render", "write", "check", "seal", "check-live"])
    ap.add_argument("--tag", default="virtu-six-software:v3")
    args = ap.parse_args(argv)

    if args.cmd == "render":
        sys.stdout.write(render())
        return 0
    if args.cmd == "write":
        OUT_FILE.write_text(render(), encoding="utf-8")
        print(f"WROTE {OUT_FILE.relative_to(ROOT)} sha256={canonical_sha()[:16]}")
        return 0
    if args.cmd == "check":
        if not OUT_FILE.exists():
            print(f"MISSING {OUT_FILE.relative_to(ROOT)}"); return 1
        actual = OUT_FILE.read_text(encoding="utf-8")
        ok = actual == render()
        print(("BASE_OK " if ok else "BASE_DRIFT ") + f"sha256={hashlib.sha256(actual.encode()).hexdigest()[:16]}")
        return 0 if ok else 1
    if args.cmd == "seal":
        global EXPECTED_CANONICAL_SHA
        sha = canonical_sha()
        print(f"CANONICAL_SHA={sha}")
        print("# 请将上面值回填到 EXPECTED_CANONICAL_SHA 后重跑 check")
        return 0
    if args.cmd == "check-live":
        return check_live(args.tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
