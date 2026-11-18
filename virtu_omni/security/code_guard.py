"""统一代码执行安全闸门：AST 静态校验 + 受限 builtins。

修复背景
--------
V-02（Harness 脚本 exec 无校验）与 V-03（QuietStar / FunSearch 沙箱可反射逃逸）
的共同根因是：执行不可信源码时只裁剪了 ``__builtins__``，却没有阻断
``obj.__class__.__mro__[...].__subclasses__()``、``__globals__``、``sys.modules``
之类的反射链。仅仅"少给几个内建函数"不构成沙箱。

本模块提供两件事：

1. :func:`validate_source` / :func:`assert_safe_source`
   —— 在 ``exec`` 之前用 AST 静态拒绝危险构造（dunder 属性、危险内建、
   白名单外的 import、``sys.modules`` 等反射入口）。
2. :func:`restricted_builtins`
   —— 生成真正裁剪过的内建表，并把 ``open`` 包装成"仅允许白名单根目录"。

三处调用点（``agent/super_agent.py``、``reasoning/quiet_star_sandbox.py``、
``evolution/funsearch_engine.py``）共用同一套规则，避免历史上"一处收紧、
另一处松懈"的分裂。

兼容性开关
----------
``VIRTU_CODE_GUARD`` 环境变量：

* 未设置 / ``enforce`` —— 默认，从严。
* ``audit`` —— 只记录违规不阻断（仅用于排查误伤，不要长期使用）。
* ``off`` —— 完全关闭（等同修复前的旧行为，明确不推荐）。
"""
from __future__ import annotations

import ast
import os
import tempfile
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "UnsafeCodeError",
    "DEFAULT_ALLOWED_MODULES",
    "guard_mode",
    "validate_source",
    "assert_safe_source",
    "restricted_builtins",
    "default_allowed_roots",
]

GUARD_ENV = "VIRTU_CODE_GUARD"

#: 允许被不可信代码 import 的顶层模块。默认只放"纯计算/纯数据"类，
#: 任何能触达文件系统、进程、网络、序列化反序列化的模块都不在列。
DEFAULT_ALLOWED_MODULES: FrozenSet[str] = frozenset({
    "sys", "json", "csv", "decimal", "fractions", "statistics", "math",
    "cmath", "random", "re", "string", "textwrap", "itertools", "functools",
    "collections", "dataclasses", "typing", "datetime", "time", "enum",
    "hashlib", "base64", "uuid", "pathlib", "io", "operator", "numbers",
    "copy", "heapq", "bisect", "array", "struct", "unicodedata", "traceback",
    "difflib", "pprint", "abc", "contextlib",
})

#: 直接调用的危险内建（名字层面）。
FORBIDDEN_CALLS: FrozenSet[str] = frozenset({
    "eval", "exec", "compile", "__import__", "open" , "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "hasattr",
    "memoryview", "object", "super", "staticmethod", "classmethod", "property",
})

#: 允许使用的内建（其余一律不注入）。
SAFE_BUILTIN_NAMES: Tuple[str, ...] = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "complex", "dict", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "hash", "hex", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "oct",
    "ord", "pow", "print", "range", "repr", "reversed", "round", "set",
    "slice", "sorted", "str", "sum", "tuple", "zip",
    # 异常类型：不可信脚本必然要 try/except，缺了这些会 NameError 误伤。
    "BaseException", "Exception", "ArithmeticError", "AssertionError",
    "AttributeError", "BufferError", "EOFError", "FileNotFoundError",
    "FloatingPointError", "ImportError", "IndexError", "KeyError",
    "LookupError", "MemoryError", "NameError", "NotImplementedError",
    "OSError", "OverflowError", "PermissionError", "RuntimeError",
    "StopIteration", "SyntaxError", "TypeError", "UnboundLocalError",
    "ValueError", "ZeroDivisionError", "Warning", "UserWarning",
    "DeprecationWarning", "RuntimeWarning", "RecursionError",
)

#: 属性访问黑名单里的"非 dunder 但同样致命"的名字。
#: ``sys.modules['os']`` 是绕过 import 白名单最常见的一条反射链。
FORBIDDEN_ATTRS: FrozenSet[str] = frozenset({
    "modules", "meta_path", "path_hooks", "path_importer_cache",
    "builtins", "loader", "loader_state", "f_globals", "f_locals",
    "f_builtins", "gi_frame", "cr_frame", "ag_frame", "tb_frame",
    "func_globals", "mro", "subclasses", "subclasshook", "cell_contents",
    "system", "popen", "spawn", "spawnl", "spawnv", "execl", "execv",
    "unlink", "rmdir", "removedirs", "rmtree", "putenv", "execvp", "execve",
})


class UnsafeCodeError(ValueError):
    """源码未通过安全校验。"""


def guard_mode() -> str:
    """Return ``enforce`` / ``audit`` / ``off``.  Default: enforce."""
    mode = str(os.environ.get(GUARD_ENV) or "").strip().lower()
    return mode if mode in ("enforce", "audit", "off") else "enforce"


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


#: 这些字符串方法的格式化字段可以直接做属性/下标反射，需要单独检查模板文本。
_FORMAT_STRING_ATTRS: FrozenSet[str] = frozenset({
    "format", "format_map", "vformat", "get_field", "get_value",
})

_TEMPLATE_FIELD_RE = None


def _has_template_reflection(blob: str) -> bool:
    """判断格式化模板里是否出现 ``{0.__class__}`` / ``{0[x]}`` 这类反射字段。"""
    global _TEMPLATE_FIELD_RE
    if not blob or "__" not in blob:
        return False
    if _TEMPLATE_FIELD_RE is None:
        import re as _re
        _TEMPLATE_FIELD_RE = _re.compile(r"\{[^{}]*__[^{}]*\}")
    return bool(_TEMPLATE_FIELD_RE.search(blob))


def _top_module(name: str) -> str:
    return (name or "").split(".")[0]


def default_allowed_roots() -> List[str]:
    """默认允许 ``open`` 落盘/读取的根目录。

    包含进程 CWD、项目根、临时目录。刻意不包含 ``C:\\Windows``、
    ``C:\\Program Files`` 等系统目录。
    """
    roots: List[str] = []
    for candidate in (
        os.getcwd(),
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        tempfile.gettempdir(),
    ):
        try:
            resolved = os.path.realpath(os.path.abspath(candidate))
        except OSError:
            continue
        if resolved and resolved not in roots:
            roots.append(resolved)
    return roots


def _path_within(candidate: str, roots: Sequence[str]) -> bool:
    try:
        real = os.path.realpath(os.path.abspath(candidate))
    except (OSError, ValueError):
        return False
    for root in roots:
        try:
            if os.path.normcase(os.path.commonpath((root, real))) == os.path.normcase(root):
                return True
        except (OSError, ValueError):
            continue
    return False


def validate_source(
    source: Any,
    *,
    allowed_modules: Optional[Iterable[str]] = None,
    allow_open: bool = True,
    extra_forbidden_calls: Iterable[str] = (),
) -> List[str]:
    """静态检查一段源码，返回违规描述列表（空列表即通过）。

    检查项：

    * ``Import`` / ``ImportFrom``：顶层模块必须在白名单内；禁止相对导入。
    * ``Attribute``：禁止 dunder 与 :data:`FORBIDDEN_ATTRS` 中的反射/破坏性名字。
    * ``Name``：禁止 dunder 名字（``__builtins__`` 等）。
    * ``Call``：禁止 :data:`FORBIDDEN_CALLS`（``allow_open`` 时放行 ``open``）。
    """
    violations: List[str] = []
    if isinstance(source, (bytes, bytearray)):
        try:
            source = source.decode("utf-8", "replace")
        except Exception:
            return ["源码无法解码为文本"]
    if not isinstance(source, str):
        return ["源码类型不是 str/bytes：%r" % type(source).__name__]

    try:
        tree = ast.parse(source, filename="<guarded>", mode="exec")
    except SyntaxError as exc:
        return ["语法错误，无法校验：%s" % exc]

    allowed = frozenset(allowed_modules) if allowed_modules is not None \
        else DEFAULT_ALLOWED_MODULES
    forbidden_calls = set(FORBIDDEN_CALLS)
    if allow_open:
        forbidden_calls.discard("open")
    forbidden_calls.update(extra_forbidden_calls)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _top_module(alias.name)
                if top not in allowed:
                    violations.append(
                        "第 %d 行：import %s 不在允许模块白名单内" % (node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if getattr(node, "level", 0):
                violations.append("第 %d 行：禁止相对导入（level=%s）" % (node.lineno, node.level))
            for alias in (node.names or []):
                if alias.name == "*":
                    violations.append("第 %d 行：禁止 from ... import *" % node.lineno)
            top = _top_module(node.module or "")
            if top and top not in allowed:
                violations.append(
                    "第 %d 行：from %s import ... 不在允许模块白名单内" % (node.lineno, node.module))
        elif isinstance(node, ast.Attribute):
            attr = node.attr or ""
            if _is_dunder(attr):
                violations.append("第 %d 行：禁止访问 dunder 属性 .%s" % (node.lineno, attr))
            elif attr in FORBIDDEN_ATTRS:
                violations.append("第 %d 行：禁止访问属性 .%s" % (node.lineno, attr))
        elif isinstance(node, ast.Name):
            name = node.id or ""
            if _is_dunder(name) and name not in ("__name__", "__doc__"):
                violations.append("第 %d 行：禁止引用 dunder 名字 %s" % (node.lineno, name))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in forbidden_calls:
                violations.append("第 %d 行：禁止调用 %s()" % (node.lineno, func.id))
            elif isinstance(func, ast.Attribute) and (func.attr or "") in forbidden_calls:
                violations.append("第 %d 行：禁止调用 .%s()" % (node.lineno, func.attr))
            # ``"{0.__class__.__mro__}".format(1)`` 这类格式化字符串反射：
            # AST 里没有任何 Attribute 节点，只有字符串常量，必须单独检查。
            attr = getattr(func, "attr", "") if isinstance(func, ast.Attribute) else ""
            if attr in _FORMAT_STRING_ATTRS:
                blobs = []
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Constant):
                    blobs.append(func.value.value)
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    if isinstance(arg, ast.Constant):
                        blobs.append(arg.value)
                for blob in blobs:
                    if isinstance(blob, str) and _has_template_reflection(blob):
                        violations.append(
                            "第 %d 行：禁止在格式化字符串中做属性反射（%r）"
                            % (node.lineno, blob[:60]))
                        break
    return violations


def assert_safe_source(source: Any, **kwargs: Any) -> None:
    """:func:`validate_source` 的抛异常版本。"""
    violations = validate_source(source, **kwargs)
    if violations:
        raise UnsafeCodeError("；".join(violations[:8]))


def restricted_builtins(
    *,
    allowed_roots: Optional[Sequence[str]] = None,
    allow_open: bool = True,
) -> Dict[str, Any]:
    """构造裁剪后的 ``__builtins__`` 字典。

    ``open`` 被替换为受目录约束的版本：只允许读写 :func:`default_allowed_roots`
    （或调用方传入的 ``allowed_roots``）之内的路径，越界直接 ``PermissionError``。
    """
    import builtins as _b

    table: Dict[str, Any] = {}
    for name in SAFE_BUILTIN_NAMES:
        if hasattr(_b, name):
            table[name] = getattr(_b, name)
    table["__build_class__"] = _b.__build_class__
    table["__name__"] = "virtu_guarded"
    table["True"] = True
    table["False"] = False
    table["None"] = None
    table["NotImplemented"] = NotImplemented
    table["Ellipsis"] = Ellipsis

    if allow_open:
        roots = list(allowed_roots) if allowed_roots else default_allowed_roots()
        real_open = _b.open

        def _guarded_open(file, mode="r", *args, **kwargs):  # noqa: A002
            target = os.fspath(file) if not isinstance(file, int) else None
            if target is None:
                raise PermissionError("禁止以文件描述符方式 open()")
            if not _path_within(target, roots):
                raise PermissionError(
                    "路径越界：%r 不在允许根目录内（%s）" % (target, ", ".join(roots)))
            return real_open(file, mode, *args, **kwargs)

        table["open"] = _guarded_open

    return table
