# -*- coding: utf-8 -*-
"""bridges/code_sandbox_policy.py — deny-by-default policy for free-form VBA / AutoLISP.

审计要求（阶段二 B 组）：VBA/LISP 沙箱由「黑名单正则」改为「默认拒绝」。

本模块的契约：

1. **deny-by-default**：自由文本代码默认**拒绝**。只有两种情况放行：
   a) 代码带结构化渲染标记 ``VIRTU_DSL_RENDERED``（由本仓 DSL 渲染器产出）；
   b) 调用方显式打开 freeform 开关（``allow_freeform=True``，或环境变量
      ``VIRTU_VBA_ALLOW_FREEFORM=1`` / ``VIRTU_LISP_ALLOW_FREEFORM=1``）。
2. **硬禁清单**：即使在开关打开的情况下，命中硬禁构造仍然 blocked。硬禁覆盖
   ``Declare/PtrSafe/Lib/Implements/Type...End Type/CallByName/Application.Run/
   Shell/CreateObject/GetObject/Kill/MkDir/RmDir/Open...For/Name...As/Environ``
   以及 Win32 绑定、脚本宿主、注册表、SendKeys、COM 后期绑定等能力。
3. **审计**：每次判定写一条 ``key=value`` 结构化日志；设置
   ``VIRTU_CODE_AUDIT_LOG`` 时额外追加 JSONL 落盘（只追加，不覆盖）。

本模块只依赖标准库，可被 ``bridges/*`` 与 ``virtu_omni/security/*`` 双侧复用。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("virtu_omni.bridges.code_sandbox_policy")

DSL_RENDERED_MARKER = "VIRTU_DSL_RENDERED"
VBA_FREEFORM_ENV = "VIRTU_VBA_ALLOW_FREEFORM"
LISP_FREEFORM_ENV = "VIRTU_LISP_ALLOW_FREEFORM"
CODE_AUDIT_LOG_ENV = "VIRTU_CODE_AUDIT_LOG"

_TRUTHY = {"1", "true", "yes", "on", "y", "enabled"}


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in _TRUTHY


# ---------------------------------------------------------------------------
# 硬禁清单（命中即 blocked，与 freeform 开关无关）
# ---------------------------------------------------------------------------

# (rule_name, compiled_pattern, human_readable)
VBA_DENY_RULES: List[Tuple[str, "re.Pattern[str]", str]] = [
    ("declare_api", re.compile(r"\bDeclare\b", re.I),
     "Win32 API 声明（Declare/Lib）"),
    ("ptrsafe", re.compile(r"\bPtrSafe\b", re.I), "PtrSafe API 声明"),
    ("lib_reference", re.compile(r"\bLib\s+\"", re.I), "外部 DLL 引用（Lib \"...\"）"),
    ("implements", re.compile(r"^\s*Implements\b", re.I | re.M), "Implements 接口实现"),
    ("type_block", re.compile(r"^\s*(?:Public\s+|Private\s+)?Type\s+[A-Za-z_]\w*", re.I | re.M),
     "Type...End Type 结构体定义（常用于声明 API 参数）"),
    ("callbyname", re.compile(r"\bCallByName\b", re.I), "CallByName 后期绑定调用"),
    ("application_run", re.compile(r"\bApplication\s*\.\s*Run\b", re.I), "Application.Run 外部宏调用"),
    ("shell", re.compile(r"\bShell\b", re.I), "Shell 启动外部进程"),
    ("createobject", re.compile(r"\bCreateObject\b", re.I), "CreateObject COM/脚本对象创建"),
    ("getobject", re.compile(r"\bGetObject\b", re.I), "GetObject COM 对象获取"),
    ("kill", re.compile(r"\bKill\b", re.I), "Kill 删除文件"),
    ("mkdir", re.compile(r"\bMkDir\b", re.I), "MkDir 创建目录"),
    ("rmdir", re.compile(r"\bRmDir\b", re.I), "RmDir 删除目录"),
    ("chdir", re.compile(r"\bChDir\b", re.I), "ChDir 切换工作目录"),
    ("environ", re.compile(r"\bEnviron\$?\b", re.I), "Environ 读取环境变量"),
    ("file_io", re.compile(r"\bOpen\b[^\r\n]*\bFor\s+(?:Output|Append|Binary|Input|Random)\b", re.I),
     "Open ... For Output/Append 文件写入"),
    ("file_rename", re.compile(r"^\s*Name\s+\S[^\r\n]*\s+As\s+", re.I | re.M), "Name ... As 文件改名"),
    ("filesystemobject", re.compile(r"\bFileSystemObject\b", re.I), "FileSystemObject 文件系统对象"),
    ("script_host", re.compile(r"\b(?:WScript|WshShell|WSH)\b", re.I), "Windows 脚本宿主对象"),
    ("direct_exe", re.compile(
        r"\b(?:cmd|powershell|pwsh|wscript|cscript|mshta|rundll32|regsvr32|certutil|bitsadmin)"
        r"(?:\.exe)?\b", re.I), "直接引用可执行程序/脚本宿主"),
    ("win32_binding", re.compile(
        r"\b(?:LoadLibrary\w*|GetProcAddress|WinExec|ShellExecute\w*|URLDownloadToFile\w*|"
        r"CreateProcess\w*|VirtualAlloc\w*)\b", re.I), "Win32 进程/内存操作 API"),
    ("ado_stream", re.compile(r"\b(?:ADODB|ADOMD)\b", re.I), "ADODB 流对象（可写任意文件）"),
    ("scripting_lib", re.compile(r"\bScripting\s*\.\s*", re.I), "Scripting.* COM 库引用"),
    ("excel4_macro", re.compile(r"\bExecuteExcel4Macro\b", re.I), "Excel4 宏调用"),
    ("registry", re.compile(r"\bReg(?:Read|Write|CreateKey\w*|SetValue\w*|DeleteKey\w*)\b", re.I),
     "注册表读写"),
    ("sendkeys", re.compile(r"\bSendKeys\b", re.I), "SendKeys 键盘注入"),
    ("wmi", re.compile(r"\b(?:Win32_Process|SWbemLocator|WbemScripting)\b", re.I), "WMI 进程操控"),
]

# (rule_name, compiled_pattern, human_readable)
LISP_DENY_RULES: List[Tuple[str, "re.Pattern[str]", str]] = [
    ("startapp", re.compile(r"\bstartapp\b", re.I), "startapp 启动外部程序"),
    ("shell_command", re.compile(
        r"\(\s*(?:vl-cmdf|command)\b[^\r\n]*\"[^\"]*\b(?:shell|cmd|powershell|pwsh|explorer|"
        r"regedit|format|del|erase|rd|rmdir|copy|move)\b", re.I), "command/shell 调用外部命令"),
    ("vl_file_delete", re.compile(r"\bvl-file-delete\b", re.I), "vl-file-delete 删除文件"),
    ("vl_file_copy", re.compile(r"\bvl-file-copy\b", re.I), "vl-file-copy 复制文件"),
    ("vl_file_rename", re.compile(r"\bvl-file-rename\b", re.I), "vl-file-rename 文件改名"),
    ("vl_directory_files", re.compile(r"\bvl-directory-files\b", re.I), "vl-directory-files 目录枚举"),
    ("vl_registry", re.compile(r"\bvl-registry-(?:read|write|delete)\b", re.I), "注册表读写"),
    ("vlax_invoke", re.compile(r"\bvlax-invoke(?:-method)?\b", re.I), "vlax-invoke COM 方法调用"),
    ("vlax_object", re.compile(
        r"\bvlax-(?:create-object|get-or-create-object|create-object-from)\b", re.I),
     "vlax COM 对象创建"),
    ("vl_load_com", re.compile(r"\bvl-load-com\b", re.I), "vl-load-com 打开 COM 通道"),
    ("arxload", re.compile(r"\b(?:arxload|xload|vlisp-compile)\b", re.I), "加载外部 ARX/编译模块"),
    ("load_external", re.compile(r"\(\s*load\s*\"", re.I), "load 加载外部 LISP 文件"),
    ("eval_dynamic", re.compile(r"\(\s*eval\b", re.I), "eval 动态执行字符串"),
    ("dos_legacy", re.compile(r"\bdos_[a-z_]+\b", re.I), "dos_* 遗留系统调用"),
    ("file_write", re.compile(r"\(\s*(?:open|close|write-line|write-char|read-line)\b", re.I),
     "文件读写 IO 函数"),
]

_RULES: Dict[str, List[Tuple[str, "re.Pattern[str]", str]]] = {
    "vba": VBA_DENY_RULES,
    "lisp": LISP_DENY_RULES,
}

_VERDICT = {
    "vba": {"deny": "VBA_DENY_LIST_VIOLATION", "freeform": "VBA_FREEFORM_DISABLED",
            "legacy": "VBA_SECURITY_VIOLATION"},
    "lisp": {"deny": "LISP_DENY_LIST_VIOLATION", "freeform": "LISP_FREEFORM_DISABLED",
             "legacy": "AUTOLISP_SECURITY_VIOLATION"},
}


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------

def code_digest(code: str) -> str:
    """内容指纹：同一段代码任何时刻得到同一值，可据此回查审计记录。"""
    raw = (code or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


def audit_decision(kind: str, decision: str, code: str, rule: Optional[str] = None,
                   source: str = "", freeform: Optional[bool] = None,
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """记录一次代码沙箱判定。返回本次写入的结构化记录（便于上层回显）。"""
    record: Dict[str, Any] = {
        "event": "code_sandbox_decision",
        "kind": kind,
        "decision": decision,
        "rule": rule,
        "source": source,
        "code_sha256": code_digest(code),
        "code_len": len(code or ""),
        "freeform": freeform,
        "pid": os.getpid(),
    }
    if extra:
        record.update(extra)

    logger.info(
        "code_sandbox_decision kind=%s decision=%s rule=%s source=%s code_sha256=%s "
        "code_len=%s freeform=%s pid=%s",
        record["kind"], record["decision"], record["rule"], record["source"],
        record["code_sha256"], record["code_len"], record["freeform"], record["pid"],
    )

    path = os.environ.get(CODE_AUDIT_LOG_ENV)
    if path:
        try:
            parent = os.path.dirname(os.path.abspath(path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:  # 审计落盘失败不能影响判定本身
            logger.warning("code_audit_log_write_failed path=%s error=%s", path, exc)
    return record


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------

def is_dsl_rendered(code: str) -> bool:
    """代码是否由本仓结构化 DSL 渲染器产出（带标记即视为可信产物）。"""
    return DSL_RENDERED_MARKER in (code or "")


def find_deny_violation(kind: str, code: str) -> Optional[Tuple[str, str]]:
    """只做硬禁判定，不涉及 freeform 开关。返回 (rule, 命中片段) 或 None。"""
    rules = _RULES.get(kind)
    if rules is None:
        raise ValueError(f"unsupported code kind: {kind}")
    text = code or ""
    if not text.strip():
        return None
    for rule_name, pattern, _desc in rules:
        m = pattern.search(text)
        if m:
            snippet = (m.group(0) or "").strip()
            return rule_name, snippet[:80]
    return None


def _rule_description(kind: str, rule_name: str) -> str:
    for name, _p, desc in _RULES.get(kind, []):
        if name == rule_name:
            return desc
    return rule_name


def validate_code(kind: str, code: str, allow_freeform: Optional[bool] = None,
                  source: str = "") -> Optional[Dict[str, Any]]:
    """deny-by-default 代码校验。

    Returns:
        None 表示放行；dict 表示 blocked（含 verdict_code / rule / detail）。
    """
    if kind not in _RULES:
        raise ValueError(f"unsupported code kind: {kind}")

    text = code or ""
    verdicts = _VERDICT[kind]
    env_name = VBA_FREEFORM_ENV if kind == "vba" else LISP_FREEFORM_ENV
    effective_freeform = _env_flag(env_name, False) if allow_freeform is None else bool(allow_freeform)

    if not text.strip():
        return None

    # 1. 硬禁清单：与开关无关
    hit = find_deny_violation(kind, text)
    if hit:
        rule_name, snippet = hit
        audit_decision(kind, "blocked", text, rule=rule_name, source=source,
                       freeform=effective_freeform, extra={"snippet": snippet})
        return {
            "status": "blocked",
            "verdict_code": verdicts["deny"],
            "policy": "deny_by_default",
            "rule": rule_name,
            "rule_description": _rule_description(kind, rule_name),
            "snippet": snippet,
            "code_sha256": code_digest(text),
            "freeform_allowed": effective_freeform,
            "message": (f"{kind.upper()} 代码命中硬禁构念 [{rule_name}] "
                        f"（{_rule_description(kind, rule_name)}），已按 deny-by-default 策略拒绝。"),
        }

    # 2. 结构化渲染产物视为可信
    if is_dsl_rendered(text):
        audit_decision(kind, "allowed_dsl", text, rule=None, source=source,
                       freeform=effective_freeform)
        return None

    # 3. 自由文本：默认拒绝，需显式开关
    if not effective_freeform:
        audit_decision(kind, "blocked_freeform", text, rule=None, source=source,
                       freeform=effective_freeform)
        return {
            "status": "blocked",
            "verdict_code": verdicts["freeform"],
            "policy": "deny_by_default",
            "rule": "freeform_disabled",
            "code_sha256": code_digest(text),
            "freeform_allowed": False,
            "message": (f"{kind.upper()} 自由文本执行默认关闭（deny-by-default）。"
                        f"请改用结构化 DSL 渲染路径（代码带 {DSL_RENDERED_MARKER} 标记），"
                        f"或显式设置 {env_name}=1 打开自由文本开关后重试。"),
        }

    audit_decision(kind, "allowed_freeform", text, rule=None, source=source,
                   freeform=effective_freeform)
    return None


def render_dsl_marker(kind: str, name: str) -> str:
    """生成结构化渲染标记注释，供 DSL 渲染器拼在产物首行。"""
    safe_name = re.sub(r"[^A-Za-z0-9_.\-]", "_", str(name or "dsl"))
    if kind == "vba":
        return f"' {DSL_RENDERED_MARKER}: {safe_name}"
    return f";; {DSL_RENDERED_MARKER}: {safe_name}"
