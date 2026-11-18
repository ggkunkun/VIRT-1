"""
virtu_real_backend.py — Virtu-CAD-CAM 真·大模型推理后端

把模型从「模板合成 / 假推理」升级为「真实自回归生成」。

设计要点
--------
1. 四种后端，按环境变量切换（默认 auto：本地优先，无本地算力时自动用云端真实模型）：
     - transformers : HuggingFace transformers + peft（base + LoRA），需要 torch + 显存，性能最强
     - llamacpp     : llama-cpp-python 加载 GGUF，CPU / Apple-Metal / CUDA 都能跑，本地最轻量
     - vllm_http    : 指向已运行的 vLLM / OpenAI 兼容服务（如 http://127.0.0.1:8001/v1）
     - cloud        : 转发到 OpenAI 兼容的云端真实模型（如阿里百炼/智谱），零本地算力即可用；
                     默认自动读取 ~/.workbuddy/models.json 里已有的国内可直连条目
2. 意图路由：
     - 普通聊天 -> base + 对话 LoRA（VIRTU_CONV_LORA，默认 turing_conversational_lora）
     - 制造/CAD 意图 -> 切换到 CAD LoRA（VIRTU_CAD_LORA，默认 cad_cam_six_software_lora）
3. 优雅降级：模型未就绪或依赖缺失时 available=False，桥返回明确的服务不可用错误。
4. 所有重量级依赖（torch / transformers / peft / llama_cpp）均「延迟导入」，
   所以即使这些包没装，本模块也能被 import 而不报错。

环境变量
--------
VIRTU_BACKEND      auto | transformers | llamacpp | vllm_http | cloud
VIRTU_MODEL_PATH   基座权重目录（transformers 用，应指向真实的 Qwen2.5/Qwen3 权重）
VIRTU_GGUF_PATH    GGUF 文件路径（llamacpp 用）
VIRTU_VLLM_URL     vLLM/OpenAI 兼容端点，如 http://127.0.0.1:8001/v1
VIRTU_CLOUD_BASE_URL  云端 OpenAI 兼容 base（如 https://dashscope.aliyuncs.com/compatible-mode/v1）
VIRTU_CLOUD_API_KEY   云端 API Key（缺省自动读 ~/.workbuddy/models.json）
VIRTU_CLOUD_MODEL     云端模型名（如 qwen3.8-max-0902）
VIRTU_VISION_MODE     auto | local | cloud（auto：本地权重存在则优先本地，否则云端）
VIRTU_VISION_LOCAL_PATH 本地视觉权重目录，默认 models/Qwen3-VL-2B-Instruct
VIRTU_VIDEO_MAX_FRAMES 视频抽帧上限，默认 16
VIRTU_VIDEO_MAX_SIDE   视频帧最长边，默认 640
VIRTU_VIDEO_MAX_SECONDS 只处理前 N 秒，默认 30
VIRTU_VISION_BASE_URL 云端视觉模型 OpenAI 兼容 base（缺省自动发现智谱 glm-4.5v）
VIRTU_VISION_API_KEY  云端视觉模型 API Key（缺省复用 models.json 里的智谱 key）
VIRTU_VISION_MODEL    云端视觉模型名，默认 glm-4.5v
VIRTU_CONV_LORA    对话 LoRA 目录（可选）
VIRTU_CAD_LORA     CAD LoRA 目录（可选）
VIRTU_DEVICE       auto | cuda | cpu（transformers 用）
VIRTU_MAX_TOKENS   生成上限，默认 1024
VIRTU_TEMPERATURE  采样温度，默认 0.8
"""

import os
import re
import sys
import json
import math
import base64
import io
import threading
import urllib.request
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

CAD_KEYWORDS = [
    "cad", "cam", "cae", "solidworks", "nx", "ug", "autocad", "vericut",
    "cimco", "斯沃", "数控", "宏程序", "外径", "内径", "直径", "孔", "槽",
    "模具", "轮模", "叶轮", "齿轮", "刀具", "对刀", "仿真", "建模", "尺寸",
    "材料", "五轴", "车削", "铣削", "加工", "g代码", "gcode", "lisp", "vba",
    "g54", "g71", "g70", "fanuc", "siemens", "西门子", "发那科", "设计",
    "参数", "建模", "生成", "制造", "图纸", "公差", "gdt", "注塑", "cnc",
]


def _env(name, default=None):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


# --- prompt 预算与 num_ctx 阶梯 -------------------------------------------------
# 2026-11-06 实测标定：16 个 cadcam_* 工具 schema = 11,492 字符，配 61 字符题面，
# 服务端报 prompt = 4779 tokens（已含 chat template 开销）⇒ ≈2.42 字符/token。
# 旧写法 `need_4k = bool(tools or ...) ; ctx = 4096 if need_4k else 2048` 把"带工具"
# 一律钉死在 4096，于是任何带完整工具面的请求都被 Ollama 直接 400 拒掉
# （"request (4779 tokens) exceeds the available context size (4096 tokens)"）。
# 除数取 2.2（比实测更保守）：宁可多开一档 KV，也不要让请求进不去。
# 上限 8192：实测完整工具面约 4779 tokens，8192 已覆盖；12288/16384 两档只会把
# KV 从 0.60 GiB 抬到 1.20 GiB（q8_0，36 层×8 kv 头×128），在 6 GiB 卡上纯属浪费，
# 且卸载跑满时会让整机进 swap。需要更长上下文时显式传 num_ctx，不要靠阶梯爬。
_CTX_LADDER = (2048, 4096, 8192)
_CHARS_PER_TOKEN = 2.2


def _estimate_prompt_tokens(messages, tools):
    """服务端 token 计数的本地近似（字符数/2.2，含工具 schema 与已有 tool_calls）。"""
    chars = 0
    for m in (messages or []):
        chars += len(str(m.get("content", "") or ""))
        chars += len(str(m.get("tool_calls", "") or ""))
        chars += len(str(m.get("name", "") or ""))
    if tools:
        chars += len(json.dumps(tools, ensure_ascii=False))
    return int(chars / _CHARS_PER_TOKEN) + 64


def _next_ctx_up(current):
    for c in _CTX_LADDER:
        if c > (current or 0):
            return c
    return None


def _plan_ctx(messages, tools, num_predict=0):
    want = _estimate_prompt_tokens(messages, tools) + int(num_predict or 0) + 256
    for c in _CTX_LADDER:
        if c >= want:
            return c
    return _CTX_LADDER[-1]


def _resolve_ctx(messages, tools, num_predict):
    """VIRTU_NUM_CTX 仍可整体覆写（留给人工压/放），否则按 token 估选阶梯。"""
    return int(_env("VIRTU_NUM_CTX", str(_plan_ctx(messages, tools, num_predict))))




# Preferred local tags, in order.  The *tag* is part of the artifact identity:
# ``virtu-master:v4`` and ``virtu-master:latest`` are different weights, so a
# discovered name must never be truncated to its stem (that silently served
# whatever ``:latest`` happened to point at).
_PREFERRED_OLLAMA_MODELS = (
    "virtu-ties-v1", "virtu-master:v4", "virtu-production:v3",
    "qwen3:8b", "virtu-toolcall:latest", "virtu-omni-8b:v2",
)


def resolve_ollama_model(names, env_model=""):
    """Pick the exact tag to serve from ``/api/tags`` names; None when empty."""
    names = [n for n in names if n]
    if not names:
        return None

    def match(target):
        if target in names:
            return target
        prefixed = sorted(n for n in names if n.startswith(target + ":"))
        return prefixed[0] if prefixed else None

    if env_model:
        found = match(env_model)
        if found:
            return found
    for candidate in _PREFERRED_OLLAMA_MODELS:
        found = match(candidate)
        if found:
            return found
    return names[0]


def _vllm_text_model():
    return _env("VIRTU_VLLM_MODEL", "virtu-ties-v1:latest")


def _vllm_tool_model():
    return _env("VIRTU_TOOL_MODEL", "virtu-ties-v1:latest")


class VisionUnavailable(RuntimeError):
    """图片请求到达但没有任何可用的视觉模型配置。"""


def _import_vision_stack():
    """Import torch/transformers for the vision channel.

    The bridge is launched with the global Python on this box (no torch), while
    the project venv carries torch 2.6 + transformers 5.22. Only the vision path
    borrows the venv site-packages; text/tool paths stay on the global packages.
    """
    import sys
    try:
        import torch
    except ModuleNotFoundError:
        venv_site = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 ".venv", "Lib", "site-packages")
        if not os.path.isdir(venv_site):
            raise
        if venv_site not in sys.path:
            sys.path.insert(0, venv_site)
        import torch
    from transformers import AutoProcessor
    try:
        from transformers import Qwen3VLForConditionalGeneration as ModelCls
    except ImportError:
        from transformers import AutoModelForImageTextToText as ModelCls
    return torch, AutoProcessor, ModelCls


def _is_vision_id(model_id):
    mid = (model_id or "").lower()
    return any(tag in mid for tag in (
        "-vl", "vl-", "vl_", "-4v", "-4.5v", "vision", "gpt-4o", "gemini-", "omni"))


IMAGE_TYPES = ("image_url", "input_image", "image")
VIDEO_TYPES = ("video_url", "input_video", "video")


def _has_image(messages):
    for m in messages or []:
        content = m.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") in IMAGE_TYPES:
                    return True
    return False


def _has_video(messages):
    for m in messages or []:
        content = m.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") in VIDEO_TYPES:
                    return True
    return False


_CALC_HINTS = ("计算", "求", "换算", "公式", "保留", "公差", "转速", "进给",
               "体积", "质量", "=", "＝")


def _last_user_text(messages):
    for message in reversed(messages or []):
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(str(item.get("text", "")) for item in content
                            if isinstance(item, dict))
        return ""
    return ""


_TOOLCALL_HINTS = ("JSON 工具", "输出 JSON", "输出一个 JSON", "工具调用",
                   "cadcam_", "execute_vba", "validate_macro")
_TOOL_ALIASES = {
    "cadcam_validate": "cadcam_cimco_validate",
    "cadcam_cimco": "cadcam_cimco_validate",
}
_ACTION_ALIASES = {
    "validate_macro_b": "validate_macro",
    "run_macro_b_profile": "validate_macro",
}


def _is_toolcall_prompt(text):
    t = text or ""
    return any(h in t for h in _TOOLCALL_HINTS) or (
        any(s in t for s in ("CIMCO", "SOLIDWORKS", "NX", "VERICUT", "AutoCAD", "斯沃"))
        and ("输出 JSON" in t or "JSON" in t)
    )


def _is_call_payload(value):
    """A single tool-call object, or a non-empty array whose elements are all calls."""
    if isinstance(value, dict):
        return "tool" in value or "arguments" in value
    if isinstance(value, list) and value:
        return all(isinstance(item, dict) and ("tool" in item or "arguments" in item)
                   for item in value)
    return False


def _parse_tool_payload(text):
    """Return the first JSON value in ``text`` that is a call object or an array of calls.

    Previously only the span from the first ``{`` to the last ``}`` was parsed, so a
    correct ``[{...},{...}]`` array was sliced into ``{...},{...}`` (invalid JSON) and
    mis-read as "no tool call was made". Scanning every opener with ``raw_decode``
    recognises the array and lets a correct multi-call answer survive untouched.
    """
    if not isinstance(text, str) or "tool" not in text:
        return None
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if _is_call_payload(value):
            return value
    return None


def _looks_like_tool_json(text):
    return _parse_tool_payload(text) is not None


def _normalize_tool_obj(obj):
    if not isinstance(obj, dict):
        return obj
    tool = obj.get("tool") or obj.get("name")
    if isinstance(tool, str) and tool in _TOOL_ALIASES:
        obj["tool"] = _TOOL_ALIASES[tool]
        obj.pop("name", None)
    args = obj.get("arguments")
    if isinstance(args, dict):
        action = args.get("action")
        if action in _ACTION_ALIASES:
            args["action"] = _ACTION_ALIASES[action]
        obj["arguments"] = args
    return obj


_VBA_CODE_KV_RE = re.compile(r"vba_code\s*[=＝：:]\s*(?P<code>Sub[\s\S]*?End\s+Sub)", re.I)
_VBA_CODE_FENCE_RE = re.compile(r"```(?:vba|vb)?[ \t]*\r?\n?(?P<code>[^`]+?)```", re.S | re.I)
_VBA_CODE_BLOCK_RE = re.compile(
    r"(?is)(?P<code>Sub\s+[A-Za-z_]\w*\s*\([^)]*\)[\s\S]*?End\s+Sub)")


def _extract_vba_code(text):
    """Copy a VBA macro the prompt literally contains; never synthesise a stub."""
    for pattern in (_VBA_CODE_KV_RE, _VBA_CODE_FENCE_RE, _VBA_CODE_BLOCK_RE):
        match = pattern.search(text or "")
        if match:
            code = match.group("code").strip()
            if code:
                return code
    return None


def _cimco_action(text):
    """The action the prompt itself names; None when it names neither."""
    low = (text or "").lower()
    if "launch" in low or "背绘" in text or "打开" in text:
        return "launch"
    if "validate" in low or "校验" in text or "验证" in text:
        return "validate_macro"
    return None


def _compile_toolcall_from_prompt(text):
    """Compile a call from fields the prompt states explicitly; None means "do not answer".

    The previous version filled a missing input with an invented default
    (``runs/macro.nc``, ``part_name="part"``, ``"Sub main()\\nEnd Sub"``, ``runs/nx.py``).
    That turned a response containing *no* tool call into a complete JSON call, so an
    empty answer could be scored full marks: a fake pass.  Every field compiled here is
    copied from the prompt; when a required argument is absent the caller keeps the
    model's original answer untouched (fail-closed).
    """
    t = text or ""
    if "CIMCO" in t:
        action = _cimco_action(t)
        path_m = re.search(r"(runs/[A-Za-z0-9_./\\-]+\.nc|models/[A-Za-z0-9_./\\-]+\.\w+)", t)
        if not (action and path_m):
            return None
        return {"tool": "cadcam_cimco_validate",
                "arguments": {"action": action,
                              "nc_file_path": path_m.group(1).replace("\\", "/")}}
    if "SOLIDWORKS" in t and re.search(r"VBA|vba", t):
        part_m = re.search(r"part_name\s*[=＝：:]\s*([A-Za-z0-9_\-]+)", t)
        code = _extract_vba_code(t)
        if not (part_m and code):
            return None
        return {"tool": "cadcam_solidworks_model",
                "arguments": {"action": "execute_vba", "part_name": part_m.group(1),
                              "vba_code": code}}
    if re.search(r"cadcam_nx_journal", t) and re.search(r"run_journal", t):
        sp = re.search(r"script_path\s*[=＝：:]\s*([A-Za-z0-9_./\\-]+)", t)
        if not sp:
            return None
        return {"tool": "cadcam_nx_journal",
                "arguments": {"action": "run_journal", "script_path": sp.group(1)}}
    return None


def _pcd_chord_problem(text):
    """Bolt-circle chord: D*sin(180°/z) in degrees."""
    if not text or not any(h in text for h in ("弦长", "孔心距", "分度圆")):
        return None
    if "sin" not in text.lower() and "弦长公式" not in text:
        return None
    d = _unique_assignment(re.compile(
        r"(?:分度圆直径|节圆直径|Ø|⌀|Φ|φ)[^0-9\-]{0,8}(?P<d>\d+(?:\.\d+)?)"), text)
    z_m = re.search(r"(?:均布|均分)\s*(\d+)\s*个", text) or re.search(
        r"(?<![A-Za-z])z\s*[=＝:：]\s*(\d+)", text)
    z = float(z_m.group(1)) if z_m else None
    if not (d and z and z >= 2):
        return None
    chord = d * math.sin(math.radians(180.0 / z))
    step = 360.0 / z
    return [("弦长", f"chord = {d:g}*sin(180°/{z:g}) = {chord:.1f} mm", chord),
            ("角向间隔", f"step = 360/{z:g} = {step:.1f} deg", step)]


def _gcode_arc_problem(text):
    """G02/G03: center = start + (I,J); sweep from start to end."""
    if not text:
        return None
    move = re.search(
        r"G0(?P<dir>[23])\s*X(?P<xe>[-+]?\d+(?:\.\d+)?)\s*Y(?P<ye>[-+]?\d+(?:\.\d+)?)"
        r"\s*I(?P<i>[-+]?\d+(?:\.\d+)?)\s*J(?P<j>[-+]?\d+(?:\.\d+)?)",
        text, re.I)
    start = re.search(
        r"(?:位于|起点)\s*\(\s*(?P<xs>[-+]?\d+(?:\.\d+)?)\s*,\s*(?P<ys>[-+]?\d+(?:\.\d+)?)\s*\)",
        text)
    if not (move and start):
        return None
    xs, ys = float(start.group("xs")), float(start.group("ys"))
    xe, ye = float(move.group("xe")), float(move.group("ye"))
    i, j = float(move.group("i")), float(move.group("j"))
    cx, cy = xs + i, ys + j
    radius = math.hypot(i, j)
    if radius <= 0:
        return None
    a0 = math.atan2(ys - cy, xs - cx)
    a1 = math.atan2(ye - cy, xe - cx)
    ccw = move.group("dir") == "3"
    sweep = a1 - a0
    if ccw and sweep <= 0:
        sweep += 2 * math.pi
    if (not ccw) and sweep >= 0:
        sweep -= 2 * math.pi
    sweep_deg = abs(math.degrees(sweep))
    arc_len = radius * abs(sweep)
    return [
        ("圆心X", f"center_x = {xs:g}+{i:g} = {cx:.1f}", cx),
        ("圆心角", f"sweep = {sweep_deg:.1f} deg", sweep_deg),
        ("弧长", f"arc = R*|θ| = {radius:.1f}*{abs(sweep):.4f} = {arc_len:.2f} mm", arc_len),
    ]


def _is_calculation_query(messages):
    """True for explicit numeric/formula questions.

    Qwen3-8B is measurably prompt-sensitive: injecting any system persona makes
    it skip the denominator (509.3 -> 1273.2/1000.0). For pure calculation we
    therefore send only the user's formula and values, while normal conversation
    keeps the caller's system prompt untouched.
    """
    text = _last_user_text(messages)
    if not text:
        return False
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", text)
    if len(numbers) < 2:
        return False
    has_calc_hint = any(hint in text for hint in _CALC_HINTS)
    has_operator = any(op in text for op in ("*", "×", "÷", "/", "π", "公式"))
    return has_calc_hint and has_operator


_SPINDLE_HINTS = ("主轴转速", "转速", "r/min", "rpm", "RPM", "spindle",
                  "转多快", "1000*Vc", "1000·Vc", "1000Vc", "1000*V", "1000*vc")
_FEED_HINTS = ("进给速度", "每分钟进给", "工作台进给", "走多快", "feed rate", "Vf", "vf")
_MRR_HINTS = ("材料去除率", "去除率", "金属切除率", "MRR")
_TIME_HINTS = ("走刀时间", "工序时间", "加工时间", "切削时间", "cycle time",
               "时间", "T=L/Vf", "T = L/Vf")

# Word-labelled inputs (直径 80 / 每齿进给 0.2) may be followed loosely by their
# value; bare symbols (D, f, z, n, V, ap, ae, L) must carry an explicit "=/:" or the
# match is prose or a formula term, not an assignment -- "Vf=f*z*n，结果保留 1 位"
# would otherwise read feed-per-tooth as 1.
_VC_RE = re.compile(
    r"(?:Vc|VC|vc|切削速度|线速度)[^0-9\-，,；;。\n\r直径外径转速进给齿数切深]{0,10}(?P<v>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])V(?![A-Za-z])\s*[=＝:：]\s*(?P<v2>\d+(?:\.\d+)?)")
_D_RE = re.compile(
    r"(?:直径|外径|Ø|⌀|Φ|φ|diameter)[^0-9\-]{0,12}(?P<d>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])[Dd](?![A-Za-z])\s*[=＝:：]\s*(?P<d2>\d+(?:\.\d+)?)")
_FZ_RE = re.compile(
    r"(?:每齿进给(?:量)?|每齿|feed per tooth)[^0-9\-]{0,12}(?P<f>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])f(?![A-Za-z])\s*[=＝:：]\s*(?P<f2>\d+(?:\.\d+)?)")
_Z_RE = re.compile(
    r"(?:齿数|刀齿)[^0-9\-]{0,8}(?P<z>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])z(?![A-Za-z])\s*[=＝:：]\s*(?P<z2>\d+(?:\.\d+)?)"
    r"|(?P<z3>\d+(?:\.\d+)?)\s*(?:个)?\s*(?:齿|teeth|flutes)")
_N_RE = re.compile(
    r"(?:主轴转速|转速)[^0-9\-]{0,10}(?P<n>\d+(?:\.\d+)?)\s*(?:r/?min|RPM|rpm)"
    r"|(?<![A-Za-z])n(?![A-Za-z])\s*[=＝:：]\s*(?P<n2>\d+(?:\.\d+)?)\s*(?:r/?min|RPM|rpm)")
_AP_RE = re.compile(
    r"(?:背吃刀量|切深)[^0-9\-]{0,10}(?P<ap>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])ap(?![A-Za-z])\s*[=＝:：]\s*(?P<ap2>\d+(?:\.\d+)?)")
_AE_RE = re.compile(
    r"(?:铣削宽度|侧吃刀量|行距)[^0-9\-]{0,10}(?P<ae>\d+(?:\.\d+)?)"
    r"|(?<![A-Za-z])ae(?![A-Za-z])\s*[=＝:：]\s*(?P<ae2>\d+(?:\.\d+)?)")
_VFGIVEN_RE = re.compile(
    r"(?:进给速度|工作台进给|每分钟进给)[^0-9\-]{0,10}(?P<vf>\d+(?:\.\d+)?)\s*(?:mm/?min|毫米/分)"
    r"|Vf\s*[=＝:：]\s*(?P<vf2>\d+(?:\.\d+)?)\s*(?:mm/?min|毫米/分)")
_L_RE = re.compile(
    r"(?:行程长度|走刀长度|总行程)[^0-9\-]{0,10}(?P<l>\d+(?:\.\d+)?)\s*(?:mm|毫米)"
    r"|(?<![A-Za-z])L(?![A-Za-z])\s*[=＝:：]\s*(?P<l2>\d+(?:\.\d+)?)\s*(?:mm|毫米)")

# A value that the prompt itself transforms (lookup table, material factor) is not
# an explicit input: recomputing from the un-transformed table entry would append a
# "[确定性核算] 以此为准" line that contradicts the correct answer.
_TRANSFORMED_RE = re.compile(
    r"系数|档位|档表|档1|查表|按表|每提高一档|折减|乘\s*0?\.\d|×\s*0?\.\d|\*\s*0?\.\d")


def _unique_assignment(pattern, text):
    """Return the value a pattern assigns, or None if absent or ambiguous.

    Ambiguity vetoes the formula outright: picking one of two diameters and
    publishing it as authoritative is worse than not checking at all.
    """
    values = []
    for match in pattern.finditer(text):
        for captured in match.groups():
            if captured is None:
                continue
            value = float(captured)
            if value > 0 and value not in values:
                values.append(value)
    return values[0] if len(values) == 1 else None


def _spindle_speed_problem(messages):
    """Return (Vc, D, n) when the user asks for spindle speed from Vc and D."""
    text = _last_user_text(messages)
    if not text or not any(hint in text for hint in _SPINDLE_HINTS):
        return None
    if _TRANSFORMED_RE.search(text):
        return None
    vc, d = _unique_assignment(_VC_RE, text), _unique_assignment(_D_RE, text)
    if not d:
        try:
            from virtu_omni.memory import get_working_memory
            wm = get_working_memory("bridge_production_session")
            fact_d = wm.get_fact("outer_diameter")
            if fact_d and isinstance(fact_d, (int, float)):
                d = float(fact_d)
        except Exception:
            pass
    if not d and messages:
        for m in reversed(messages[:-1]):
            m_txt = m.get("content", "")
            if isinstance(m_txt, str):
                cand_d = _unique_assignment(_D_RE, m_txt)
                if cand_d:
                    d = cand_d
                    break
    if not (vc and d):
        return None
    return vc, d, 1000.0 * vc / (math.pi * d)


_CUTTING_SPEED_HINTS = ("切削速度", "线速度", "求vc", "求Vc", "求切削速度", "求线速度")


def _cutting_speed_problem(messages):
    """Return (D, n, Vc) when the user asks for cutting speed from D and n."""
    text = _last_user_text(messages)
    if not text or not any(hint in text for hint in _CUTTING_SPEED_HINTS):
        return None
    if _TRANSFORMED_RE.search(text):
        return None
    # If the user already assigned Vc, they are not asking for Vc
    if _unique_assignment(_VC_RE, text) is not None:
        return None
    d, n = _unique_assignment(_D_RE, text), _unique_assignment(_N_RE, text)
    if not d:
        try:
            from virtu_omni.memory import get_working_memory
            wm = get_working_memory("bridge_production_session")
            fact_d = wm.get_fact("outer_diameter")
            if fact_d and isinstance(fact_d, (int, float)):
                d = float(fact_d)
        except Exception:
            pass
    if not d and messages:
        for m in reversed(messages[:-1]):
            m_txt = m.get("content", "")
            if isinstance(m_txt, str):
                cand_d = _unique_assignment(_D_RE, m_txt)
                if cand_d:
                    d = cand_d
                    break
    if not (d and n):
        return None
    vc = (math.pi * d * n) / 1000.0
    return d, n, vc


_EQ_RE = re.compile(
    r"(?P<expr>[0-9π×÷+\-*/().\s]{5,})\s*[=≈]\s*(?P<num>[-+]?\d+(?:\.\d+)?)")
_NUM_ONLY_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _safe_eval_expression(expr):
    cleaned = (expr.replace("π", "pi").replace("×", "*").replace("÷", "/")
               .replace("（", "(").replace("）", ")"))
    if not re.fullmatch(r"[0-9pi+\-*/().\s]+", cleaned):
        return None
    if len(_NUM_ONLY_RE.findall(cleaned)) < 2:
        return None
    try:
        value = eval(cleaned, {"__builtins__": {}}, {"pi": math.pi})
    except Exception:  # noqa: BLE001
        return None
    return float(value) if isinstance(value, (int, float)) else None


def _fix_explicit_equation(text):
    matches = list(_EQ_RE.finditer(text))
    if len(matches) != 1:
        return text
    match = matches[0]
    computed = _safe_eval_expression(match.group("expr"))
    if computed is None or not math.isfinite(computed):
        return text
    raw_result = match.group("num")
    try:
        original = float(raw_result)
    except ValueError:
        return text
    if abs(computed - original) <= max(0.005, abs(computed) * 0.002):
        return text
    decimals = len(raw_result.split(".", 1)[1]) if "." in raw_result else 0
    corrected = f"{computed:.{decimals}f}" if decimals else str(int(round(computed)))
    return text[:match.start("num")] + corrected + text[match.end("num"):]


def _numeric_problems(messages):
    """Every formula recomputable from explicitly assigned prompt inputs.

    n -> Vf -> MRR/T chain: a machining-card question states Vc, D, f, z and asks for
    all of them, so Vf uses the n computed above when the prompt never states n, and
    falls back to a stated n when there is no Vc/D pair. Values the prompt itself
    transforms (hardness table, material factor) are vetoed -- recomputing from the
    un-transformed table entry would publish a wrong answer as authoritative.
    """
    text = _last_user_text(messages)
    if not text:
        return []
    problems = []
    transformed = bool(_TRANSFORMED_RE.search(text))

    n_value = None
    spindle = _spindle_speed_problem(messages)
    if spindle:
        vc, d, n_value = spindle
        problems.append(("主轴转速",
                         f"n = 1000·Vc/(π·D) = 1000×{vc:g}/(π×{d:g}) = {n_value:.1f} r/min",
                         n_value))
    elif not transformed:
        n_value = _unique_assignment(_N_RE, text)

    cutting = _cutting_speed_problem(messages)
    if cutting:
        d_c, n_c, vc_c = cutting
        problems.append(("切削速度",
                         f"Vc = π·D·n/1000 = π×{d_c:g}×{n_c:g}/1000 = {vc_c:.2f} m/min",
                         vc_c))

    if not transformed and n_value and any(h in text for h in _FEED_HINTS):
        fz, z = _unique_assignment(_FZ_RE, text), _unique_assignment(_Z_RE, text)
        if fz and z and z >= 1:
            vf = fz * z * n_value
            problems.append(("进给速度",
                             f"Vf = f·z·n = {fz:g}×{z:g}×{n_value:.1f} = {vf:.1f} mm/min",
                             vf))
        else:
            vf = _unique_assignment(_VFGIVEN_RE, text)
    else:
        vf = _unique_assignment(_VFGIVEN_RE, text) if not transformed else None

    if vf and any(h in text for h in _MRR_HINTS):
        ap, ae = _unique_assignment(_AP_RE, text), _unique_assignment(_AE_RE, text)
        if ap and ae:
            mrr = ap * ae * vf
            problems.append(("材料去除率",
                             f"MRR = ap·ae·Vf = {ap:g}×{ae:g}×{vf:.1f} = {mrr:.1f} mm³/min",
                             mrr))

    if vf and any(h in text for h in _TIME_HINTS):
        length = _unique_assignment(_L_RE, text)
        if length:
            duration = length / vf
            problems.append(("走刀时间",
                             f"T = L/Vf = {length:g}/{vf:.1f} = {duration:.2f} min",
                             duration))
    chord = _pcd_chord_problem(text)
    if chord:
        problems.extend(chord)
    arc = _gcode_arc_problem(text)
    if arc:
        problems.extend(arc)
    try:
        from virtu_omni.serving.numeric_repair import numeric_problems as _extra_problems
        extra = _extra_problems(text)
    except Exception:  # noqa: BLE001 - guard must never break generation
        extra = []
    seen = {(name, round(value, 9)) for name, _, value in problems}
    for name, expr, value in extra:
        key = (name, round(value, 9))
        if key not in seen:
            seen.add(key)
            problems.append((name, expr, value))
    return problems


def _number_present(text, value):
    return any(abs(float(x) - value) <= max(0.005, abs(value) * 0.002)
               for x in _NUM_ONLY_RE.findall(text))


def _apply_numeric_corrections(text, problems):
    missing = [p for p in problems if not _number_present(text, p[2])]
    if not missing:
        return text
    stripped = text.strip()
    if len(stripped) <= 80 and len(_NUM_ONLY_RE.findall(stripped)) <= 2 * len(missing):
        # Replacing discards the original, so publish *all* recomputed values,
        # not just the missing ones (otherwise a correct X would be dropped
        # while repairing a wrong Y).
        return "\n".join(expr for _, expr, _ in problems)
    joined = "；".join(expr for _, expr, _ in missing)
    return stripped + f"\n\n[确定性核算] {joined}（以此为准）"


def _verify_arithmetic_response(text, messages=None):
    """Fix slipped arithmetic, Vc/D -> spindle-speed, and world_state physical solver recomputation.

    The explicit-equation pass is unchanged. The formula pass recomputes only when
    the user actually supplied every input, so it cannot invent a formula for
    unrelated chat. Tool-call JSON is never rewritten into world_state.
    """
    if not isinstance(text, str):
        return text
    user_prompt = _last_user_text(messages) if messages else ""
    try:
        from virtu_omni.serving.answer_pipeline import clean_served_answer
        text = clean_served_answer(user_prompt, text).text
    except Exception:
        pass
    text = _fix_explicit_equation(text)

    if _is_toolcall_prompt(user_prompt):
        payload = _parse_tool_payload(text)
        if payload is not None:
            # A parseable object OR an array of call objects is already answered: normalise
            # tool/action aliases only, keep the field names the model wrote, and never
            # replace a correct batch answer with one compiled call.
            if isinstance(payload, list):
                normalized = [_normalize_tool_obj(item) for item in payload]
            else:
                normalized = _normalize_tool_obj(payload)
            return json.dumps(normalized, ensure_ascii=False)
        compiled = _compile_toolcall_from_prompt(user_prompt)
        if compiled:
            return json.dumps(compiled, ensure_ascii=False)
        # Fail-closed: no call in the answer and nothing fully derivable from the prompt
        # means there is nothing to say. Never fall through to the arithmetic repair,
        # which would append text to an answer that made no call at all.
        return text

    # 只在模型真的输出了 world_state，或用户给了【场景】时走物理求解器。
    # 禁止扫描 system/history：世界模型契约文本含 world_state，会把知识题全部改写成 invalid JSON。
    wm_turn = ("【场景】" in user_prompt) or ("\"world_state\"" in text) or (
        "world_state" in text and "derivation" in text)
    if wm_turn and not _is_toolcall_prompt(user_prompt):
        try:
            sys_scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
            if sys_scripts not in sys.path:
                sys.path.insert(0, sys_scripts)
            from anti_hallucination_guard import Guard, parse_json_candidate
            g = Guard(evidence_required=False)
            res = g.run(text, prompt=user_prompt)
            if res.action in ("corrected", "accept") and res.corrected:
                obj, _ = parse_json_candidate(text)
                if isinstance(obj, dict) and ("tool" in obj or "arguments" in obj):
                    return json.dumps(_normalize_tool_obj(obj), ensure_ascii=False)
                if isinstance(obj, dict):
                    if "world_state" in obj:
                        obj["world_state"] = res.corrected
                    else:
                        obj = {"world_state": res.corrected}
                    if res.reference:
                        obj.setdefault("verification", {"source": "deterministic_solver", "resolved": True})
                    return json.dumps(obj, ensure_ascii=False)
                return json.dumps({"world_state": res.corrected}, ensure_ascii=False)
        except Exception:
            pass

    if not messages:
        return text
    return _apply_numeric_corrections(text, _numeric_problems(messages))


class VirtuRealModel:
    def __init__(self):
        self.backend = (_env("VIRTU_BACKEND") or "auto").lower()
        self.model_path = _env("VIRTU_MODEL_PATH")
        self.gguf_path = _env("VIRTU_GGUF_PATH")
        self.vllm_url = _env("VIRTU_VLLM_URL")
        self.cloud_base = _env("VIRTU_CLOUD_BASE_URL")
        self.cloud_key = _env("VIRTU_CLOUD_API_KEY")
        self.cloud_model = _env("VIRTU_CLOUD_MODEL")
        self.vision_base = _env("VIRTU_VISION_BASE_URL")
        self.vision_key = _env("VIRTU_VISION_API_KEY")
        self.vision_model = _env("VIRTU_VISION_MODEL")
        self.vision_mode = (_env("VIRTU_VISION_MODE") or "auto").lower()
        self.vision_local_path = _env(
            "VIRTU_VISION_LOCAL_PATH",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "models", "Qwen3-VL-2B-Instruct"))
        self._local_vl = None
        self._local_vl_error = ""
        self._local_vl_lock = threading.Lock()
        self._cloud_candidates = []
        self._vision_candidates = []
        self.conv_lora = _env("VIRTU_CONV_LORA")
        self.cad_lora = _env("VIRTU_CAD_LORA")
        self.device = (_env("VIRTU_DEVICE") or "auto").lower()
        self.max_tokens = int(_env("VIRTU_MAX_TOKENS", "1024"))
        self.temperature = float(_env("VIRTU_TEMPERATURE", "0.8"))
        self.ollama_url = _env("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = _env("VIRTU_OLLAMA_MODEL")
        self.available = False
        self.error = ""
        self._model = None
        self._tok = None
        self._resolved = None  # 实际选中的后端
        self._last_model_used = None
        self.last_usage = None
        self.last_thought = ""
        self.thinking_mode = (_env("VIRTU_THINKING_MODE") or "auto").lower()
        self._generation_lock = threading.RLock()
        self._load()
        self._load_vision_config()

    def _should_enable_thinking(self, messages, tools=None, explicit_think=None) -> bool:
        """自适应判断当前请求是否开启深度思考 (Reasoning / CoT 模式)。"""
        if explicit_think is not None:
            return bool(explicit_think)
        mode = (_env("VIRTU_THINKING_MODE") or self.thinking_mode or "auto").lower()
        if mode in ("always", "true", "1", "on"):
            return True
        if mode in ("off", "false", "0"):
            return False

        # auto 模式：自适应路由
        user_text = _last_user_text(messages)
        if not user_text:
            return False

        # 1. 显式工程推理与数值计算（机加工艺、切削参数、几何公差、材料力学）
        if _is_calculation_query(messages) or bool(_numeric_problems(messages)):
            return True

        # 2. 深度思考与结构化任务拆解诱导词（先推导规划，拒绝盲目试错穷举）
        think_cues = (
            "思考", "推导", "推演", "详细分析", "分步", "步骤", "为什么",
            "校核", "评估", "优化方案", "设计原理", "计算过程", "论证",
            "拆任务", "拆解", "分解", "规划", "设计", "排查", "修复", "建模",
            "编程", "全链", "自愈", "反思", "根因", "因果", "为什么失败",
            "排错", "诊断", "不变量", "约束", "求解", "工艺分析",
            "deep think", "step by step", "reasoning", "think", "decompose", "planning", "root cause", "rcfa"
        )
        if any(cue in user_text.lower() for cue in think_cues):
            return True

        # 3. 历史对话中包含工具执行失败或参数违规反馈（Repair Turn）：必须深度思考分析根因，禁止盲试穷举
        has_tool_rejection = any(
            m.get("role") == "tool" and any(k in str(m.get("content", "")).lower()
                                            for k in ("rejected", "violation", "error", "fail", "不合法", "违规", "冲突", "失败"))
            for m in (messages or [])
        )
        if has_tool_rejection:
            return True

        # 4. 带有工具调用 (tools) 时的细粒度分流：
        #    - 纯单步快速动作（启动、打开、单纯预检）：不开启思考以保持快速返回；
        #    - 复合工程工具任务（需要几何自洽、参数设计、多特征建模）：开启思考拆任务。
        if tools:
            # 简单工具快查动作白名单：单纯启动或查询，不思考
            simple_action_cues = ("启动", "打开", "关闭", "查询", "读取", "状态", "launch", "open", "status")
            if any(s in user_text for s in simple_action_cues) and len(user_text) < 40 and not any(k in user_text for k in ("建模", "法兰", "设计", "规划", "编写")):
                return False
            # 复合特征建模、法兰参数设计、全链调度：必须允许思考拆任务
            complex_tool_cues = ("建模", "法兰", "设计", "参数", "全链", "编写", "vba", "宏", "工程图", "标注")
            if any(c in user_text.lower() for c in complex_tool_cues):
                return True
            return False

        return False

    def identity(self):
        """Return safe runtime identity metadata; never include credentials or full paths."""
        backend = self._resolved or "unavailable"
        if backend == "ollama":
            text_model = self.ollama_model or "unknown"
            architecture = "reported by Ollama model metadata"
        elif backend == "cloud":
            text_model = self.cloud_model or "unknown"
            architecture = "remote provider model"
        elif backend == "vllm_http":
            text_model = _env("VIRTU_VLLM_MODEL", "server-selected")
            architecture = "remote OpenAI-compatible model"
        elif backend == "transformers":
            text_model = os.path.basename(os.path.normpath(self.model_path or "configured-model"))
            architecture = getattr(getattr(self._model, "config", None), "model_type", "configured Transformers model")
        elif backend == "llamacpp":
            text_model = os.path.basename(self.gguf_path or "configured-gguf")
            architecture = "GGUF model"
        else:
            text_model = "unavailable"
            architecture = "unknown"
        return {
            "compatibility_alias": "virtu-cad-cam-10b",
            "backend": backend,
            "text_model": text_model,
            "tool_model": _vllm_tool_model() if backend == "vllm_http" else None,
            "last_model_used": self._last_model_used,
            "architecture": architecture,
            "text_model_has_native_vision": False,
            "vision_channel": "separate configured vision backend",
        }

    # -- 系统提示 canary（供输出侧泄露闸） ---------------------------------
    _SYSTEM_CANARY_CACHE: dict = {}

    def system_canaries(self):
        """Verbatim system-prompt fragments of the served Ollama model.

        Returns the default canaries plus the model's own SYSTEM fragments so the
        leak gate catches leaks of the *served* prompt, not only the production
        default.  Returns None for non-Ollama backends or on any fetch failure
        (the gate then falls back to its built-in defaults).  Cached per model.
        """
        if self._resolved != "ollama" or not self.ollama_model:
            return None
        key = (self.ollama_url, self.ollama_model)
        if key in self._SYSTEM_CANARY_CACHE:
            return self._SYSTEM_CANARY_CACHE[key]
        from virtu_omni.serving.deception_gate import DEFAULT_CANARIES
        try:
            req = urllib.request.Request(
                self.ollama_url.rstrip("/") + "/api/show",
                data=json.dumps({"model": self.ollama_model}).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                system = json.load(r).get("system", "") or ""
        except Exception:
            return None
        frags = [f.strip() for f in re.split(r"[\n。；;]", system) if len(f.strip()) >= 12]
        canaries = tuple(dict.fromkeys(list(DEFAULT_CANARIES) + frags))
        self._SYSTEM_CANARY_CACHE[key] = canaries
        return canaries

    # -- 意图识别 ----------------------------------------------------------
    def _is_cad_intent(self, messages):
        chunks = []
        for message in messages or []:
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                chunks.append(content)
            elif isinstance(content, list):
                chunks.extend(str(item.get("text", "")) for item in content
                              if isinstance(item, dict) and item.get("type") == "text")
            elif isinstance(content, dict):
                chunks.append(str(content.get("text", "")))
        text = " ".join(chunks)
        t = text.lower()
        return any(k in t for k in CAD_KEYWORDS)

    # -- 加载 --------------------------------------------------------------
    def _load(self):
        try:
            if self.backend in ("auto", "transformers") and self.model_path:
                self._load_transformers()
                self._resolved = "transformers"
                self.available = True
                return
            if self.backend in ("auto", "llamacpp") and self.gguf_path:
                self._load_llamacpp()
                self._resolved = "llamacpp"
                self.available = True
                return
            if self.backend in ("auto", "vllm_http") and self.vllm_url:
                self._resolved = "vllm_http"
                self.available = True
                return
            if self.backend in ("auto", "ollama"):
                if self._probe_ollama():
                    self._resolved = "ollama"
                    self.available = True
                    return
            if self.backend in ("auto", "cloud"):
                if self._load_cloud_config():
                    self._resolved = "cloud"
                    self.available = True
                    return
            self.error = "no usable backend configured (set VIRTU_MODEL_PATH / VIRTU_GGUF_PATH / VIRTU_VLLM_URL / Ollama at 11434 / VIRTU_CLOUD_*)"
        except Exception as e:  # 任何加载失败都降级，不让桥崩溃
            self.error = f"{type(e).__name__}: {e}"
            self.available = False

    def _probe_ollama(self):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request(self.ollama_url.rstrip("/") + "/api/tags")
            with opener.open(req, timeout=3) as r:
                data = json.loads(r.read().decode("utf-8"))
            names = [m.get("name", "") for m in data.get("models", [])]
            resolved = resolve_ollama_model(names, self.ollama_model or "")
            if not resolved:
                return False
            self.ollama_model = resolved
            print(f"[virtu_backend] Auto-discovered local Ollama model: {self.ollama_model}")
            return True
        except Exception:
            return False

    def _load_transformers(self):
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from virtu_eval import mem_budget as mb

        # torch_dtype="auto" keeps on-disk precision: an 8B bf16 dir is ~16 GB of
        # commit, more than this box's physical RAM. Refuse before it thrashes.
        mb.require_hf_fit(self.model_path, device=self.device)

        base = AutoModelForCausalLM.from_pretrained(
            self.model_path, torch_dtype="auto",
            device_map=self.device if self.device != "auto" else "auto",
        )
        tok = AutoTokenizer.from_pretrained(self.model_path)
        model = base
        # 防御：合并产物已把 LoRA 烘焙进权重（目录带 merge_receipt.json），
        # 此时再挂 conv/cad LoRA 会造成双重叠加。无论环境变量是否误传，都跳过。
        import os as _os
        already_merged = _os.path.exists(
            _os.path.join(self.model_path, "merge_receipt.json"))
        if already_merged and (self.conv_lora or self.cad_lora):
            print(f"[virtu_backend] 检测到已合并模型，忽略运行时 LoRA "
                  f"(conv={self.conv_lora}, cad={self.cad_lora})，避免双重叠加")
            self.conv_lora = None
            self.cad_lora = None
        self._adapter_names = set()
        first_name = "chat" if self.conv_lora else "cad"
        first_path = self.conv_lora or self.cad_lora
        if first_path:
            model = PeftModel.from_pretrained(base, first_path, adapter_name=first_name)
            self._adapter_names.add(first_name)
        if self.conv_lora and self.cad_lora:
            model.load_adapter(self.cad_lora, adapter_name="cad")
            self._adapter_names.add("cad")
        model.eval()
        self._model, self._tok = model, tok

    def _load_llamacpp(self):
        from llama_cpp import Llama
        from virtu_eval import mem_budget as mb

        # -1 (full offload) puts every layer in VRAM: fine for a 4.6 GB dense Q4 on
        # a 6 GiB card, fatal for the 8.3 GB MoE. Derive the split from the GGUF and
        # the *currently free* VRAM; an explicit pin is still honoured but checked,
        # because pinning disables llama.cpp's own auto-fit and turns an over-fit
        # into a server crash rather than a graceful reduction.
        facts = mb.gguf_facts(self.gguf_path)
        env = mb.require_headroom()
        pinned = _env("VIRTU_N_GPU_LAYERS")
        if pinned is None or str(pinned).strip() == "":
            n_gpu = mb.max_offload_layers(facts, 4096, env=env)
        else:
            n_gpu = int(pinned)
            if n_gpu < 0:
                n_gpu = facts["block_count"] + 1   # -1 means full offload; still check it
            proj = mb.project(facts, 4096, n_gpu)
            if proj["vram_mib"] + mb.VRAM_RESERVE_MIB > env["gpu_free_mib"]:
                raise mb.BudgetError(
                    "VIRTU_N_GPU_LAYERS=%s needs %d MiB but only %d MiB free; "
                    "safe ceiling is %d"
                    % (pinned, proj["vram_mib"], env["gpu_free_mib"],
                       mb.max_offload_layers(facts, 4096, env=env)))
        self._model = Llama(
            model_path=self.gguf_path,
            n_ctx=4096,
            n_gpu_layers=n_gpu,
            verbose=False,
        )

    def _load_cloud_config(self):
        """配置云端转发后端。优先用环境变量，否则自动从 WorkBuddy 的
        models.json 里挑一个国内可直连的自定义模型（dashscope / bigmodel）。"""
        if not (self.cloud_base and self.cloud_key and self.cloud_model):
            b, k, m = self._discover_cloud_from_workbuddy()
            self.cloud_base = self.cloud_base or b
            self.cloud_key = self.cloud_key or k
            self.cloud_model = self.cloud_model or m
        if not (self.cloud_base and self.cloud_key and self.cloud_model):
            return False
        self.cloud_base = self.cloud_base.rstrip("/")
        self._cloud_candidates = [(self.cloud_base, self.cloud_key, self.cloud_model)]
        for cand in self._cloud_candidates_from_workbuddy():
            if cand not in self._cloud_candidates:
                self._cloud_candidates.append(cand)
        return True

    @staticmethod
    def _cloud_candidates_from_workbuddy():
        """按 models.json 顺序收集可作文本兜底的条目（跳过本机桥自身）。"""
        out = []
        try:
            with open(os.path.expanduser("~/.workbuddy/models.json"), encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return out
        for m in cfg:
            url = (m.get("url") or "").rstrip("/")
            key = m.get("apiKey")
            mid = m.get("id") or ""
            if not (url and key and mid) or "127.0.0.1" in url:
                continue
            if not any(h in url for h in ("bigmodel", "dashscope", "nvidia")):
                continue
            if _is_vision_id(mid):
                continue
            out.append((url, key, mid))
        return out

    def _load_vision_config(self):
        """视觉通道独立于文本后端：本地纯文本模型 + 云端视觉模型可以共存。"""
        if self.vision_base and self.vision_key and self.vision_model:
            self._vision_candidates = [(self.vision_base.rstrip("/"),
                                        self.vision_key, self.vision_model)]
            return
        discovered = self._vision_candidates_from_workbuddy()
        if discovered:
            base, key, model = discovered[0]
            self.vision_base = self.vision_base or base
            self.vision_key = self.vision_key or key
            self.vision_model = self.vision_model or model
        self._vision_candidates = discovered

    @staticmethod
    def _vision_candidates_from_workbuddy():
        out = []
        try:
            with open(os.path.expanduser("~/.workbuddy/models.json"), encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return out
        # 智谱 key 可直接调用其视觉模型（models.json 里通常没有收录该条目）；
        # 实测 glm-4.5v 稳定，作为首选，其余同 key 的视觉条目作兜底。
        for m in cfg:
            url = m.get("url") or ""
            if "bigmodel" in url and m.get("apiKey"):
                out.append(("https://open.bigmodel.cn/api/paas/v4", m["apiKey"], "glm-4.5v"))
                break
        for m in cfg:
            url = (m.get("url") or "").rstrip("/")
            key = m.get("apiKey")
            mid = m.get("id") or ""
            if not (url and key) or "127.0.0.1" in url:
                continue
            if _is_vision_id(mid) and (url, key, mid) not in out:
                out.append((url, key, mid))
        return out

    @staticmethod
    def _discover_cloud_from_workbuddy():
        # 优先 dashscope（阿里百炼，国内稳定），其次 bigmodel（智谱免费接口易 429）
        order = ["dashscope", "bigmodel", "open.bigmodel"]
        path = os.path.expanduser("~/.workbuddy/models.json")
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return None, None, None
        for tag in order:
            for m in cfg:
                url = m.get("url", "")
                if tag in url and m.get("apiKey"):
                    return url.rstrip("/"), m["apiKey"], m.get("id")
        return None, None, None

    # -- 生成 --------------------------------------------------------------
    @contextmanager
    def _generation_slot(self):
        """Acquire the model lock with a bounded wait.

        A disconnected client can leave a long generation running; without a
        timeout every later request would queue forever behind it.
        """
        timeout = float(_env("VIRTU_GENERATION_LOCK_TIMEOUT", "300"))
        if not self._generation_lock.acquire(timeout=timeout):
            raise RuntimeError(
                f"backend busy: another generation held the model lock for more than {timeout:g}s")
        try:
            yield
        finally:
            self._generation_lock.release()

    def generate(self, messages, tools=None, max_tokens=None, temperature=None, think=None):
        with self._generation_slot():
            self.last_thought = ""
            old_max_tokens, old_temperature = self.max_tokens, self.temperature
            if max_tokens is not None:
                if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
                    raise ValueError("max_tokens must be an integer")
                if not 1 <= max_tokens <= 32768:
                    raise ValueError("max_tokens must be between 1 and 32768")
            if temperature is not None:
                if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                    raise ValueError("temperature must be a number")
                if not 0.0 <= temperature <= 2.0:
                    raise ValueError("temperature must be between 0 and 2")
            if max_tokens is not None:
                self.max_tokens = max_tokens
            if temperature is not None:
                self.temperature = temperature
            try:
                if think is not None:
                    return self._generate(messages, tools=tools, think=think)
                return self._generate(messages, tools=tools)
            finally:
                self.max_tokens, self.temperature = old_max_tokens, old_temperature

    def generate_stream(self, messages, tools=None, max_tokens=None, temperature=None, think=None):
        """流式自回归生成器，逐块实时产出思考 (thinking) 与文本 (content) 增量。"""
        with self._generation_slot():
            self.last_thought = ""
            old_max_tokens, old_temperature = self.max_tokens, self.temperature
            if max_tokens is not None:
                if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
                    raise ValueError("max_tokens must be an integer")
                if not 1 <= max_tokens <= 32768:
                    raise ValueError("max_tokens must be between 1 and 32768")
            if temperature is not None:
                if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                    raise ValueError("temperature must be a number")
                if not 0.0 <= temperature <= 2.0:
                    raise ValueError("temperature must be between 0 and 2")
            if max_tokens is not None:
                self.max_tokens = max_tokens
            if temperature is not None:
                self.temperature = temperature
            try:
                for chunk in self._generate_stream(messages, tools=tools, think=think):
                    yield chunk
            finally:
                self.max_tokens, self.temperature = old_max_tokens, old_temperature

    def _generate_stream(self, messages, tools=None, think=None):
        self.last_usage = None
        self.last_thought = ""
        if _has_image(messages) or _has_video(messages):
            res = self._gen_vision(messages)
            yield {"type": "content", "delta": res}
            return
        if not self.available:
            raise RuntimeError(f"backend unavailable: {self.error}")
        cad = self._is_cad_intent(messages)
        if self._resolved == "ollama":
            messages = self._with_internet(messages, tools=tools)
            for chunk in self._gen_ollama_stream(messages, cad, tools=tools, think=think):
                yield chunk
            return
        res = self._generate(messages, tools=tools, think=think)
        if isinstance(res, tuple):
            text, _ = res
        else:
            text = res
        thought = self.last_thought
        if thought:
            yield {"type": "thinking", "delta": thought}
        if text:
            yield {"type": "content", "delta": text}

    def _with_internet(self, messages, tools=None):
        """所有后端统一联网：把实时检索资料以 system 注记注入，不改用户原文。

        跳过场景：视觉输入、工具调用请求（避免污染工具 JSON）、已注入过的消息。
        任何检索失败都原样返回，模型行为与未联网时完全一致。
        """
        if tools is not None or _has_image(messages) or _has_video(messages):
            return messages
        if _is_toolcall_prompt(_last_user_text(messages)):
            return messages
        try:
            from virtu_omni.internet.augmentation import augment_messages
            augmented, _citations = augment_messages(messages)
            return augmented
        except Exception:
            return messages

    def _generate(self, messages, tools=None, think=None):
        self.last_usage = None
        self.last_thought = ""
        if _has_image(messages) or _has_video(messages):
            if tools:
                raise RuntimeError("Tool calling with image/video input is not supported by the configured vision channel")
            res = self._gen_vision(messages)
            return (res, None) if tools is not None else res
        if not self.available:
            raise RuntimeError(f"backend unavailable: {self.error}")
        cad = self._is_cad_intent(messages)
        messages = self._with_internet(messages, tools=tools)
        if self._resolved == "ollama":
            return self._gen_ollama(messages, cad, tools=tools, think=think)
        if self._resolved == "transformers":
            return self._gen_transformers(messages, cad, tools=tools, think=think)
        if self._resolved == "llamacpp":
            return self._gen_llamacpp(messages, cad, tools=tools, think=think)
        if self._resolved == "vllm_http":
            return self._gen_vllm(messages, cad, tools=tools, think=think)
        if self._resolved == "cloud":
            return self._gen_cloud(messages, cad, tools=tools, think=think)
        raise RuntimeError(f"unknown backend {self._resolved}")

    def _record_usage(self, prompt_tokens, completion_tokens):
        """Stash the generator's token counts for the response layer.

        Only real reported counts are stored; a missing pair stays None so the
        bridge can never publish an estimate as if it were a measurement.
        """
        if prompt_tokens is None and completion_tokens is None:
            self.last_usage = None
            return
        total = None
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total = prompt_tokens + completion_tokens
        self.last_usage = {"prompt_tokens": prompt_tokens,
                           "completion_tokens": completion_tokens,
                           "total_tokens": total}

    def _chat_with_room(self, chat, **kwargs):
        """Call Ollama, recovering from one specific fragile failure.

        Measured 2026-11-01: with max_tokens=220 a tool turn picked the correct tool
        (cadcam_vericut_simulate) but the arguments were cut mid-JSON, and llama-server
        rejected the whole request - "Ollama API HTTP 500: invalid tool call arguments
        ... unexpected end of JSON input" - which the bridge surfaced as a hard 500.
        Widening the budget makes the same call succeed (verified at 700/1024 with
        identical tool name and parseable arguments). Any other error still propagates.
        """
        base = kwargs.get("num_predict") or self.max_tokens
        # 放宽预算只做一次。原写法用 `attempt < 3` 计数、却把 base 冻在循环外，
        # 于是第三次仍算出同一个 768 再试一遍——花的是一次白跑的完整前向。
        # tests/test_tool_call_retry.py::test_retry_that_still_fails_propagates 钉住这点。
        widened_once = False
        for attempt in (1, 2, 3):
            try:
                return chat(**kwargs)
            except RuntimeError as exc:
                msg = str(exc)
                if "exceeds the available context size" in msg:
                    up = _next_ctx_up(kwargs.get("num_ctx"))
                    if up is None or attempt == 3:
                        raise
                    print("[virtu_backend] prompt 超出 num_ctx=%s（本地估 %d tokens），"
                          "升到 %s 重试" % (kwargs.get("num_ctx"),
                                            _estimate_prompt_tokens(kwargs.get("messages"),
                                                                    kwargs.get("tools")), up), flush=True)
                    kwargs = dict(kwargs, num_ctx=up)
                    continue
                if "invalid tool call arguments" in msg:
                    if widened_once:
                        raise
                    widened = max(base * 3, 768)
                    print("[virtu_backend] 工具调用 JSON 被 %s token 预算截断，"
                          "放宽到 %s 后重试一次" % (base, widened), flush=True)
                    kwargs = dict(kwargs, num_predict=widened)
                    widened_once = True
                    continue
                raise

    def _gen_ollama(self, messages, cad, tools=None, think=None):
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from scripts.ollama_toolcall_client import chat
        ctx = _resolve_ctx(messages, tools, self.max_tokens)
        self._last_model_used = self.ollama_model
        enable_think = self._should_enable_thinking(messages, tools=tools, explicit_think=think)
        res = self._chat_with_room(
            chat,
            model=self.ollama_model,
            messages=messages,
            tools=tools,
            temperature=self.temperature,
            num_ctx=ctx,
            num_predict=self.max_tokens,
            think=enable_think,
        )
        self._record_usage(res.get("prompt_eval_count"), res.get("eval_count"))
        self.last_thought = res.get("thinking") or ""
        # 输出层诊断口径（2026-11-07）：JSON 腿走 grammar、退化重复、工具腿正文丢弃
        self.last_output_diag = {
            "json_mode": res.get("json_mode"),
            "json_ok": res.get("json_ok"),
            "json_unwrap_key": res.get("json_unwrap_key"),
            "json_truncated": res.get("json_truncated"),
            "degenerate": res.get("degenerate"),
            "discarded_content": res.get("discarded_content") or "",
            "content_raw": res.get("content_raw") or "",
            "done_reason": (res.get("raw") or {}).get("done_reason"),
        }
        if tools is not None:
            return res.get("content", ""), res.get("tool_calls")
        # 结构化请求：返回解包后的合法 JSON（拆掉模型自套的 {"tools":[...]} 容器），
        # 下游不必再判断"裸数组 / 单键对象"两种形态。
        if res.get("json_ok") and res.get("json_value") is not None:
            return json.dumps(res["json_value"], ensure_ascii=False), None
        text = res.get("content", "")
        return _verify_arithmetic_response(text, messages)

    def _gen_transformers(self, messages, cad, tools=None, think=None):
        has_tool_history = any(
            m.get("role") == "tool" or "tool_calls" in m for m in (messages or []))
        names = getattr(self, "_adapter_names", set())
        desired = "cad" if cad and "cad" in names else "chat"
        if desired not in names and names:
            desired = next(iter(names))
        if desired in names and hasattr(self._model, "set_adapter"):
            self._model.set_adapter(desired)
        template_kwargs = {"tokenize": False, "add_generation_prompt": True}
        if tools:
            if not callable(getattr(self._tok, "apply_chat_template", None)):
                raise RuntimeError("Transformers tokenizer does not support chat templates/tool schemas")
            template_kwargs["tools"] = [tool.get("function", tool) for tool in tools]
        try:
            prompt = self._tok.apply_chat_template(messages, **template_kwargs)
        except Exception as exc:
            if tools:
                raise RuntimeError(f"Transformers backend cannot render tool schemas: {exc}") from exc
            raise
        inputs = self._tok(prompt, return_tensors="pt").to(self._model.device)
        out = self._model.generate(
            **inputs,
            max_new_tokens=self.max_tokens,
            temperature=self.temperature,
            do_sample=self.temperature > 0,
            top_p=0.9,
        )
        raw_text = self._tok.decode(
            out[0][inputs.input_ids.shape[1]:], skip_special_tokens=False
        ).strip()
        from scripts.ollama_toolcall_client import extract_thinking, parse_tool_calls
        clean_text, thought = extract_thinking(raw_text)
        self.last_thought = thought
        if tools is not None or has_tool_history:
            calls = parse_tool_calls(clean_text)
            if calls:
                return "", calls
            return (clean_text, None) if tools is not None else clean_text
        return clean_text

    def _format_llamacpp(self, messages, cad):
        sys_note = (
            "你是一个精通 CAD/CAM/数控制造的工业助手，同时也能像普通人一样自然聊天。"
            if cad else
            "你是一个友好、自然的对话助手。"
        )
        buf = f"<|im_start|>system\n{sys_note}<|im_end|>\n"
        for m in messages:
            role = m.get("role", "user")
            role = "assistant" if role == "assistant" else ("system" if role == "system" else "user")
            buf += f"<|im_start|>{role}\n{m.get('content','')}<|im_end|>\n"
        buf += "<|im_start|>assistant\n"
        return buf

    def _gen_llamacpp(self, messages, cad, tools=None, think=None):
        has_tool_history = any(
            m.get("role") == "tool" or "tool_calls" in m for m in (messages or []))
        if tools or has_tool_history:
            create = getattr(self._model, "create_chat_completion", None)
            if not callable(create):
                raise RuntimeError("llama.cpp backend does not support native tool-call conversations")
            try:
                kwargs = {"messages": messages, "max_tokens": self.max_tokens,
                          "temperature": self.temperature}
                if tools:
                    kwargs.update(tools=tools, tool_choice="auto")
                response = create(**kwargs)
                message = response["choices"][0]["message"]
                calls = message.get("tool_calls") or None
                raw_c = message.get("content") or ""
                from scripts.ollama_toolcall_client import extract_thinking
                clean_c, thought = extract_thinking(raw_c)
                self.last_thought = message.get("reasoning_content") or thought or ""
                result = (clean_c, calls)
                return result if tools is not None else result[0]
            except Exception as exc:
                raise RuntimeError(f"llama.cpp tool conversation failed: {exc}") from exc
        prompt = self._format_llamacpp(messages, cad)
        res = self._model(
            prompt, max_tokens=self.max_tokens, temperature=self.temperature,
            top_p=0.9, stop=["<|im_end|>"],
        )
        raw_text = res["choices"][0]["text"].strip()
        from scripts.ollama_toolcall_client import extract_thinking
        clean_text, thought = extract_thinking(raw_text)
        self.last_thought = thought or ""
        return clean_text

    def _gen_vllm(self, messages, cad, tools=None, think=None):
        numeric_query = (_is_calculation_query(messages)
                         or bool(_numeric_problems(messages)))
        # Only the initial schema-bearing turn belongs to the specialist. The
        # post-execution summary has no tools and should use the general model.
        tool_turn = bool(tools)
        if tool_turn:
            # Matches the virtu-toolcall training distribution. The merged general
            # models catastrophically forget arithmetic, so tools get a specialist.
            sys_note = ("你是 Virtu 工业智能体。需要产出可执行代码时，必须通过工具调用完成，"
                        "不要凭空输出代码。先解析意图，再调用对应软件的代码生成工具。")
            model = _vllm_tool_model()
            caller_sys = [str(m.get("content", "")) for m in messages if m.get("role") == "system"]
            combined_sys = "\n\n".join(caller_sys) if caller_sys else sys_note
            if "你是 Virtu" not in combined_sys:
                combined_sys = sys_note + "\n\n" + combined_sys
            payload_msgs = [{"role": "system", "content": combined_sys}] + [m for m in messages if m.get("role") != "system"]
        else:
            # Do not inject a synthetic persona into a base instruct model: it
            # measurably perturbs arithmetic inputs. Preserve the caller's system
            # prompt for normal chat, but strip it for explicit calculations.
            model = _vllm_text_model()
            payload_msgs = list(messages)
            if numeric_query:
                payload_msgs = [m for m in payload_msgs if m.get("role") != "system"]
        self._last_model_used = model
        # Ollama's native API is the production path on this machine. Reuse the
        # client that already handles proxy bypass, think/PAD cleanup and the
        # non-standard tool_call fallback instead of returning raw OpenAI text.
        if "11434" in self.vllm_url:
            from scripts.ollama_toolcall_client import chat
            enable_think = self._should_enable_thinking(payload_msgs, tools=tools, explicit_think=think)
            res = self._chat_with_room(
                chat,
                model=model,
                messages=payload_msgs,
                tools=tools,
                temperature=self.temperature,
                num_ctx=_resolve_ctx(payload_msgs, tools, self.max_tokens),
                num_predict=self.max_tokens,
                think=enable_think,
            )
            self._record_usage(res.get("prompt_eval_count"), res.get("eval_count"))
            self.last_thought = res.get("thinking") or ""
            if tools is not None:
                return res.get("content", ""), res.get("tool_calls")
            text = res.get("content", "")
            return _verify_arithmetic_response(text, messages)

        payload = {
            "model": model,
            "messages": payload_msgs,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        enable_think = self._should_enable_thinking(payload_msgs, tools=tools, explicit_think=think)
        if enable_think:
            payload["enable_thinking"] = True
            payload["thinking"] = {"type": "enabled"}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.vllm_url.rstrip("/") + "/chat/completions",
            data=data, headers={"Content-Type": "application/json",
                                **({"Authorization": "Bearer " + _env("VIRTU_VLLM_API_KEY")}
                                   if _env("VIRTU_VLLM_API_KEY") else {})},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode("utf-8"))
        upstream_usage = resp.get("usage") or {}
        self._record_usage(upstream_usage.get("prompt_tokens"),
                           upstream_usage.get("completion_tokens"))
        message = resp["choices"][0]["message"]
        from scripts.ollama_toolcall_client import extract_thinking, parse_tool_calls
        raw_text = message.get("content") or ""
        calls = message.get("tool_calls") or parse_tool_calls(raw_text)
        clean_text, thought = extract_thinking(raw_text)
        reasoning = message.get("reasoning_content") or message.get("reasoning") or thought or ""
        self.last_thought = reasoning
        if tools is not None:
            return clean_text, calls
        return _verify_arithmetic_response(clean_text, messages)

    def _gen_ollama_stream(self, messages, cad, tools=None, think=None):
        numeric_query = (_is_calculation_query(messages)
                         or bool(_numeric_problems(messages)))
        tool_turn = bool(tools)
        if tool_turn:
            sys_note = ("你是 Virtu 工业智能体。需要产出可执行代码时，必须通过工具调用完成，"
                        "不要凭空输出代码。先解析意图，再调用对应软件的代码生成工具。")
            model = _vllm_tool_model()
            payload_msgs = ([{"role": "system", "content": sys_note}]
                            + [m for m in messages if m.get("role") != "system"])
        else:
            model = _vllm_text_model()
            payload_msgs = list(messages)
            if numeric_query:
                payload_msgs = [m for m in payload_msgs if m.get("role") != "system"]
        self._last_model_used = model

        if "11434" in self.vllm_url:
            from scripts.ollama_toolcall_client import chat_stream
            enable_think = self._should_enable_thinking(payload_msgs, tools=tools, explicit_think=think)
            accum_thought = []
            for chunk in chat_stream(
                model=model,
                messages=payload_msgs,
                tools=tools,
                temperature=self.temperature,
                num_ctx=_resolve_ctx(payload_msgs, tools, self.max_tokens),
                num_predict=self.max_tokens,
                think=enable_think,
            ):
                if chunk["type"] == "thinking":
                    accum_thought.append(chunk["delta"])
                    yield chunk
                elif chunk["type"] == "content":
                    yield chunk
                elif chunk["type"] == "done":
                    self._record_usage(chunk.get("prompt_eval_count"), chunk.get("eval_count"))
                    self.last_thought = "".join(accum_thought)
            return

        res = self._gen_ollama(messages, cad, tools=tools, think=think)
        if isinstance(res, tuple):
            text, _ = res
        else:
            text = res
        if self.last_thought:
            yield {"type": "thinking", "delta": self.last_thought}
        if text:
            yield {"type": "content", "delta": text}

    def _gen_cloud(self, messages, cad, tools=None, think=None):
        """转发到云端真实模型。直接透传 WorkBuddy 传来的 messages（含其 system
        prompt），不覆盖，保证对话自然；云端通用大模型本身具备 CAD/CAM 知识。
        候选按 models.json 顺序逐个尝试，某个端点欠费/限流时自动切下一个。"""
        return self._chat_with_candidates(self._cloud_candidates, messages, 60, tools=tools, think=think)

    def _gen_vision(self, messages):
        """图片请求走独立视觉通道：auto 模式本地权重优先，失败再走云端。"""
        self._last_model_used = "vision-channel"
        local_err = None
        if self.vision_mode in ("auto", "local"):
            if self._local_vision_present():
                try:
                    return self._gen_local_vision(messages)
                except Exception as e:
                    local_err = e
                    print(f"[virtu_backend] local vision failed: {type(e).__name__}: {e}")
                    if self.vision_mode == "local":
                        raise VisionUnavailable(f"本地视觉模型不可用：{e}") from e
            elif self.vision_mode == "local":
                raise VisionUnavailable(f"本地视觉权重不存在：{self.vision_local_path}")

        if _has_video(messages):
            reason = (f"本地失败：{local_err}" if local_err else
                      ("当前模式为 cloud" if self.vision_mode == "cloud"
                       else "本地权重不存在"))
            raise VisionUnavailable(
                f"视频只支持本地视觉模型，云端视觉接口不支持视频（{reason}）")

        if not self._vision_candidates:
            detail = f"；本地失败：{local_err}" if local_err else ""
            raise VisionUnavailable(
                "未配置视觉模型：设置 VIRTU_VISION_BASE_URL / VIRTU_VISION_API_KEY / "
                "VIRTU_VISION_MODEL，或在 ~/.workbuddy/models.json 中提供智谱 key" + detail)
        try:
            # 云端视觉模型多为推理模型，预算过小会全被思考耗尽、content 为空
            return self._chat_with_candidates(
                self._vision_candidates, messages, 60,
                max_tokens=self.max_tokens)
        except Exception as e:
            raise VisionUnavailable(f"视觉模型调用失败：{type(e).__name__}: {e}") from e

    def _local_vision_present(self):
        p = self.vision_local_path
        try:
            return bool(p and os.path.isdir(p)
                        and os.path.exists(os.path.join(p, "config.json"))
                        and any(f.endswith(".safetensors") for f in os.listdir(p)))
        except OSError:
            return False

    def _ensure_local_vl(self):
        if self._local_vl is not None:
            return self._local_vl
        if self._local_vl_error:
            raise VisionUnavailable(self._local_vl_error)
        path = self.vision_local_path
        try:
            torch, AutoProcessor, ModelCls = _import_vision_stack()

            processor = AutoProcessor.from_pretrained(path)
            model = None
            if torch.cuda.is_available():
                try:
                    from transformers import BitsAndBytesConfig
                    qc = BitsAndBytesConfig(
                        load_in_4bit=True, bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.float16)
                    model = ModelCls.from_pretrained(
                        path, quantization_config=qc, device_map="auto",
                        low_cpu_mem_usage=True)
                except Exception as e:
                    print(f"[virtu_backend] local VL 4bit failed: {e}; retry fp16")
            if model is None:
                target = "auto" if torch.cuda.is_available() else "cpu"
                try:
                    model = ModelCls.from_pretrained(
                        path, dtype=torch.float16, device_map=target,
                        low_cpu_mem_usage=True)
                except TypeError:
                    model = ModelCls.from_pretrained(
                        path, torch_dtype=torch.float16, device_map=target,
                        low_cpu_mem_usage=True)
                except Exception as e:
                    print(f"[virtu_backend] local VL fp16 failed ({e}); CPU bf16")
                    model = ModelCls.from_pretrained(
                        path, dtype=torch.bfloat16, device_map="cpu",
                        low_cpu_mem_usage=True)
            model.eval()
            self._local_vl = (model, processor)
            print(f"[virtu_backend] local VL loaded: {path}")
            return self._local_vl
        except Exception as e:
            self._local_vl_error = f"本地视觉模型加载失败：{type(e).__name__}: {e}"
            raise VisionUnavailable(self._local_vl_error) from e

    @staticmethod
    def _decode_image(url):
        from PIL import Image
        if not isinstance(url, str) or not url:
            return None
        try:
            if url.startswith("data:"):
                raw = base64.b64decode(url.split(",", 1)[1])
            elif url.startswith(("http://", "https://")):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    raw = r.read()
            else:
                return None
            img = Image.open(io.BytesIO(raw))
            img.load()
            img = img.convert("RGB")
            img.thumbnail((1280, 1280))
            return img
        except Exception:
            return None

    def _decode_video(self, url):
        """把视频源按时间均匀抽帧成 RGB numpy 列表，供本地视觉模型使用。"""
        if not isinstance(url, str) or not url:
            return [], None
        try:
            import av
            import numpy as np
        except ImportError:
            print("[virtu_backend] 缺少 av/numpy，无法解析视频")
            return [], None
        container = None
        try:
            if url.startswith("data:"):
                raw = base64.b64decode(url.split(",", 1)[1])
                container = av.open(io.BytesIO(raw), mode="r")
            elif url.startswith(("http://", "https://")):
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                container = av.open(io.BytesIO(raw), mode="r")
            elif os.path.isfile(url):
                container = av.open(url, mode="r")
            else:
                return [], None

            max_frames = max(1, int(_env("VIRTU_VIDEO_MAX_FRAMES", "16")))
            max_side = max(224, int(_env("VIRTU_VIDEO_MAX_SIDE", "640")))
            max_seconds = max(0.5, float(_env("VIRTU_VIDEO_MAX_SECONDS", "30")))

            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            fps = float(stream.average_rate or 10) or 10.0
            duration = None
            if stream.duration is not None and stream.time_base is not None:
                duration = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                duration = container.duration / 1e6

            if duration:
                span = min(max(duration, 0.01), max_seconds)
                count = min(max_frames, max(1, int(span * min(fps, 10))))
                # 视频最后一帧的 pts 通常是 duration - 1/fps，目标点向内收一帧
                last_t = max(span - 1.0 / max(min(fps, 10), 1), 0.0)
                targets = [last_t * i / max(count - 1, 1) for i in range(count)]
            else:
                span = max_frames / min(fps, 10)
                count = max_frames
                targets = [span * i / max(count - 1, 1) for i in range(count)]

            frames = []
            ti = 0
            for idx, frame in enumerate(container.decode(stream)):
                if ti >= len(targets):
                    break
                if frame.pts is not None and stream.time_base is not None:
                    t = float(frame.pts * stream.time_base)
                else:
                    t = idx / fps
                if t > max_seconds:
                    break
                while ti < len(targets) and t >= targets[ti]:
                    img = frame.to_image().convert("RGB")
                    img.thumbnail((max_side, max_side))
                    frames.append(np.asarray(img, dtype=np.uint8))
                    ti += 1
            meta = {"fps": (len(frames) - 1) / span if len(frames) > 1 and span > 0 else fps,
                    "duration": span,
                    "total_num_frames": len(frames)}
            return frames, meta
        except Exception as e:
            print(f"[virtu_backend] video decode failed: {type(e).__name__}: {e}")
            return [], None
        finally:
            try:
                if container is not None:
                    container.close()
            except Exception:
                pass

    @staticmethod
    def _media_url(item, key):
        url = item.get(key, item.get("url"))
        if isinstance(url, dict):
            url = url.get("url")
        if not url and isinstance(item.get("source"), dict):
            src = item["source"]
            url = src.get("url")
            if not url and src.get("data"):
                media = src.get("media_type", "application/octet-stream")
                url = "data:%s;base64,%s" % (media, src["data"])
        return url

    def _prepare_vl_messages(self, messages):
        prepared, images, videos = [], [], []
        for m in messages or []:
            role = m.get("role")
            if role not in ("system", "user", "assistant"):
                continue
            content = m.get("content")
            parts = []
            if isinstance(content, (str, dict)):
                items = [content]
            elif isinstance(content, list):
                items = content
            else:
                items = []
            for item in items:
                if isinstance(item, str):
                    parts.append({"type": "text", "text": item})
                elif isinstance(item, dict):
                    kind = item.get("type")
                    if kind in IMAGE_TYPES:
                        img = self._decode_image(self._media_url(item, "image_url"))
                        if img is not None:
                            images.append(img)
                            parts.append({"type": "image"})
                    elif kind in VIDEO_TYPES:
                        frames, meta = self._decode_video(self._media_url(item, "video_url"))
                        if frames:
                            videos.append({"frames": frames, "meta": meta})
                            parts.append({"type": "video"})
                        else:
                            parts.append({"type": "text", "text": "[视频未能解析]"})
                    elif kind == "text" or "text" in item:
                        parts.append({"type": "text", "text": str(item.get("text", ""))})
            if parts:
                prepared.append({"role": role, "content": parts})
        return prepared, images, videos

    def _gen_local_vision(self, messages):
        import torch
        with self._local_vl_lock:
            model, processor = self._ensure_local_vl()
            prepared, images, videos = self._prepare_vl_messages(messages)
            if not images and not videos:
                raise VisionUnavailable("本地视觉模型未收到可解析的图片或视频")
            text = processor.apply_chat_template(
                prepared, tokenize=False, add_generation_prompt=True)
            kwargs = {"text": [text], "return_tensors": "pt"}
            if images:
                kwargs["images"] = images
            if videos:
                kwargs["videos"] = [v["frames"] for v in videos]
                kwargs["video_metadata"] = [v["meta"] for v in videos]
            inputs = processor(**kwargs)
            device = next(model.parameters()).device
            inputs = {k: (v.to(device) if hasattr(v, "to") else v)
                      for k, v in inputs.items()}
            with torch.inference_mode():
                out = model.generate(
                    **inputs, max_new_tokens=min(int(self.max_tokens), 512),
                    do_sample=False)
            gen = out[:, inputs["input_ids"].shape[1]:]
            answer = processor.batch_decode(gen, skip_special_tokens=True)[0].strip()
            if not answer:
                raise VisionUnavailable("本地视觉模型输出为空")
            return answer

    def _chat_with_candidates(self, candidates, messages, timeout, max_tokens=None, tools=None, think=None):
        last = None
        for base, key, model in candidates:
            # 本机 TLS 偶发 EOF（schannel/代理链路），非 HTTP 错误时再试一次
            for attempt in (1, 2):
                try:
                    result = self._post_chat(base, key, model, messages, timeout,
                                             max_tokens, tools=tools, think=think)
                    text, tool_calls = result
                    if text or tool_calls:
                        return (text, tool_calls) if tools is not None else text
                    last = RuntimeError("empty content")
                    break
                except Exception as e:
                    last = e
                    print(f"[virtu_backend] {model} failed (try {attempt}): "
                          f"{type(e).__name__}: {e}")
                    if type(e).__name__ == "HTTPError":
                        break
        raise RuntimeError(f"all candidates failed; last: {type(last).__name__}: {last}")

    def _post_chat(self, base, key, model, messages, timeout, max_tokens=None, tools=None, think=None):
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": int(max_tokens or self.max_tokens),
            "temperature": self.temperature,
            "stream": False,
        }
        enable_think = self._should_enable_thinking(messages, tools=tools, explicit_think=think)
        if enable_think:
            body["enable_thinking"] = True
            body["thinking"] = {"type": "enabled"}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        from scripts.ollama_toolcall_client import (extract_thinking, json_intent,
                                                    normalize_tool_calls)
        # 结构化请求同样走服务端 grammar（OpenAI 兼容的 response_format）；
        # 上游若不认这个字段会在下面回落到裸请求。
        if not tools and json_intent(messages, None) and not enable_think:
            body["response_format"] = {"type": "json_object"}
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if "response_format" not in body or exc.code != 400:
                raise
            dropped = json.loads(payload.decode("utf-8"))
            dropped.pop("response_format", None)
            req = urllib.request.Request(
                base.rstrip("/") + "/chat/completions",
                data=json.dumps(dropped).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + key,
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
        choices = resp.get("choices") or [{}]
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict))
        clean_content, inline_thought = extract_thinking(str(content))
        thought_parts = [t.strip() for t in (reasoning, inline_thought) if t and t.strip()]
        self.last_thought = "\n\n".join(thought_parts)
        calls = normalize_tool_calls(message.get("tool_calls") or None)
        return ("" if calls else clean_content.strip()), calls


# 单例：模型只加载一次
_backend_singleton = None


def get_backend():
    global _backend_singleton
    if _backend_singleton is None:
        _backend_singleton = VirtuRealModel()
    return _backend_singleton
