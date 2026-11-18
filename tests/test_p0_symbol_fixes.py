"""P0 缺陷修复的最小回归测试。

覆盖诊断报告《Virtu模型_工程诊断报告.md》§2.1–§2.5 的修复项：

1. ``_safe_torch_load`` 已定义并经 ``virtu_omni.security`` 导出，三处调用点已绑定；
2. ``scripts/workbuddy_virtu_bridge.py`` 的 ``query_params`` 在 ``do_GET`` 中已定义；
3. ``virtu_code/evaluation/benchmark.py`` 的 ``hashlib`` 已在模块层导入
   （原实现仅在 ``else`` 分支局部导入，使 ``except`` 分支必然 UnboundLocalError）；
4. ``Tuple`` / ``Union`` / ``List`` 类型导入已补齐，注解可被 ``typing.get_type_hints`` 解析；
5. 报告列出的 9 处语法错误文件可被 ``compile()`` 编译。

设计原则：只做最小、可证伪验证，不加载权重、不启动服务、不触网。
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import io
import os
import sys
import types
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# 1. _safe_torch_load 定义与导出
# --------------------------------------------------------------------------
def test_security_package_exports_safe_torch_load():
    """safe_torch_load 与历史下划线别名必须同时存在且指向同一实现。"""
    security = importlib.import_module("virtu_omni.security")
    assert hasattr(security, "safe_torch_load")
    assert hasattr(security, "_safe_torch_load")
    assert security._safe_torch_load is security.safe_torch_load
    assert "safe_torch_load" in getattr(security, "__all__", [])


class _FakeTorch(types.ModuleType):
    """最小 torch 替身，用于验证 weights_only 语义而不加载真实权重。"""

    def __init__(self, accept_weights_only=True, fail_weights_only=True):
        super().__init__("torch")
        self.accept_weights_only = accept_weights_only
        self.fail_weights_only = fail_weights_only
        self.calls = []

    def load(self, path, map_location=None, **kwargs):
        self.calls.append({"map_location": map_location, "kwargs": dict(kwargs)})
        if "weights_only" in kwargs and not self.accept_weights_only:
            raise TypeError("load() got an unexpected keyword argument 'weights_only'")
        if kwargs.get("weights_only") is True and self.fail_weights_only:
            raise RuntimeError("Unsupported global (pickle protocol) in weights_only mode")
        return {"weights_only": kwargs.get("weights_only")}


@pytest.fixture()
def weights_file(tmp_path):
    p = tmp_path / "dummy.pt"
    p.write_bytes(b"not-a-real-checkpoint")
    return p


def test_safe_torch_load_rejects_missing_and_directory(tmp_path, weights_file, monkeypatch):
    from virtu_omni.security import safe_torch_load

    monkeypatch.setitem(sys.modules, "torch", _FakeTorch(fail_weights_only=False))
    with pytest.raises(FileNotFoundError):
        safe_torch_load(tmp_path / "missing.pt")
    with pytest.raises(IsADirectoryError):
        safe_torch_load(tmp_path)


def test_safe_torch_load_uses_weights_only_by_default(weights_file, monkeypatch):
    from virtu_omni.security import safe_torch_load

    fake = _FakeTorch(fail_weights_only=False)
    monkeypatch.setitem(sys.modules, "torch", fake)
    result = safe_torch_load(weights_file, map_location="cpu")
    assert result["weights_only"] is True
    assert fake.calls[-1]["kwargs"]["weights_only"] is True
    assert fake.calls[-1]["map_location"] == "cpu"


def test_safe_torch_load_falls_back_with_warning(weights_file, monkeypatch):
    from virtu_omni.security import safe_torch_load

    fake = _FakeTorch(fail_weights_only=True)
    monkeypatch.setitem(sys.modules, "torch", fake)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = safe_torch_load(weights_file)
    assert result["weights_only"] is False
    assert [c["kwargs"]["weights_only"] for c in fake.calls] == [True, False]
    assert any(issubclass(w.category, RuntimeWarning) for w in caught)


def test_safe_torch_load_can_forbid_fallback(weights_file, monkeypatch):
    from virtu_omni.security import safe_torch_load

    monkeypatch.setitem(sys.modules, "torch", _FakeTorch(fail_weights_only=True))
    with pytest.raises(RuntimeError):
        safe_torch_load(weights_file, allow_legacy_pickle_fallback=False)


def test_safe_torch_load_supports_legacy_torch(weights_file, monkeypatch):
    """torch < 2.0 不接受 weights_only 关键字时应退回两参数调用。"""
    from virtu_omni.security import safe_torch_load

    fake = _FakeTorch(accept_weights_only=False, fail_weights_only=False)
    monkeypatch.setitem(sys.modules, "torch", fake)
    result = safe_torch_load(weights_file)
    assert result["weights_only"] is None
    assert fake.calls[-1]["kwargs"] == {}


@pytest.mark.parametrize(
    "relpath",
    [
        "virtu_omni/models/smelt_loader.py",
        "virtu_omni/training/trainer.py",
        "scripts/convert_smelt_folder.py",
    ],
)
def test_call_sites_bind_safe_torch_load(relpath):
    """三处调用点必须显式导入该符号，避免 NameError 回归。"""
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    bound = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("security.weights"):
            for alias in node.names:
                bound.append((alias.name, alias.asname))
    assert ("safe_torch_load", "_safe_torch_load") in bound, bound


@pytest.mark.parametrize(
    "module_name",
    ["virtu_omni.models.smelt_loader", "virtu_omni.training.trainer"],
)
def test_call_site_modules_resolve_symbol(module_name):
    """模块导入后命名空间内可解析 _safe_torch_load（torch 缺失时跳过）。"""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - 环境相关
        pytest.skip(f"import {module_name} failed: {type(exc).__name__}: {exc}")
    assert hasattr(module, "_safe_torch_load")
    assert module._safe_torch_load.__name__ == "safe_torch_load"


# --------------------------------------------------------------------------
# 2. query_params 未定义
# --------------------------------------------------------------------------
def _load_bridge_module():
    path = ROOT / "scripts" / "workbuddy_virtu_bridge.py"
    spec = importlib.util.spec_from_file_location("_p0_bridge_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_p0_bridge_probe"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bridge():
    try:
        return _load_bridge_module()
    except Exception as exc:  # pragma: no cover - 环境相关
        pytest.skip(f"bridge import failed: {type(exc).__name__}: {exc}")


def _make_handler(bridge, path):
    handler = object.__new__(bridge.OpenAIBaseHandler)
    handler.path = path
    handler._require_auth = lambda: True
    handler._send_cors_headers = lambda: None
    handler.send_response = lambda *a, **k: None
    handler.send_header = lambda *a, **k: None
    handler.end_headers = lambda: None
    handler.wfile = io.BytesIO()
    return handler


@pytest.mark.parametrize(
    "path,expect",
    [
        ("/v1/plugins/marketplace?q=flange&tag=cad&limit=7",
         {"query": "flange", "tag": "cad", "limit": 7}),
        ("/v1/plugins/marketplace", {"query": "", "tag": None, "limit": 20}),
    ],
)
def test_marketplace_query_params_parsed(bridge, path, expect):
    captured = {}

    class _Plugins:
        def search_marketplace(self, query=None, tag=None, limit=20):
            captured.update({"query": query, "tag": tag, "limit": limit})
            return []

    bridge.claude_plugins = _Plugins()
    handler = _make_handler(bridge, path)
    handler.do_GET()  # 修复前此处抛 NameError -> HTTP 500
    assert captured == expect
    assert handler.wfile.getvalue().decode("utf-8")


def test_plugins_list_query_params_parsed(bridge):
    captured = {}

    class _Plugins:
        def list_plugins(self, tag=None, installed_only=False, limit=50):
            captured.update({"tag": tag, "installed_only": installed_only, "limit": limit})
            return []

    bridge.claude_plugins = _Plugins()
    handler = _make_handler(bridge, "/v1/plugins/list?tag=cad&installed=true&limit=9")
    handler.do_GET()
    assert captured == {"tag": "cad", "installed_only": True, "limit": 9}


def test_computer_use_windows_visible_param(bridge):
    captured = {}

    class _ComputerUse:
        def execute_action(self, action, **kwargs):
            captured.update({"action": action, **kwargs})
            return {"ok": True, "windows": []}

    bridge.computer_use = _ComputerUse()
    handler = _make_handler(bridge, "/v1/computer-use/windows?visible=false")
    handler.do_GET()
    assert captured == {"action": "list_windows", "visible_only": False}


# --------------------------------------------------------------------------
# 3. hashlib 未导入（异常分支二次崩溃）
# --------------------------------------------------------------------------
def test_benchmark_imports_hashlib_at_module_level():
    source = (ROOT / "virtu_code" / "evaluation" / "benchmark.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_level = {
        alias.name.split(".")[0]
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "hashlib" in module_level


def test_benchmark_hashlib_available_in_except_branch(tmp_path, monkeypatch):
    """命中 except 分支时必须能算出 12 位摘要，而不是二次崩溃。"""
    provenance = pytest.importorskip("virtu_eval.provenance")

    source = (ROOT / "virtu_code" / "evaluation" / "benchmark.py").read_text(encoding="utf-8")
    lines = source.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "if output_dir:")
    end = next(i for i, l in enumerate(lines) if l.strip() == 'eval_summary["evidence_file"] = str(raw_file)')
    segment = "\n".join(lines[start:end + 1])

    monkeypatch.setattr(
        provenance.RunIdentity, "capture",
        staticmethod(lambda model_ids=None: (_ for _ in ()).throw(RuntimeError("store unavailable"))),
    )

    class _Arm:
        model_id = "regression-arm"

    namespace = {
        "Path": Path,
        "json": __import__("json"),
        "open": open,
        "hashlib": hashlib,
        "arm": _Arm(),
        "raw_rows": [{"lang": "python"}],
        "eval_summary": {},
        "output_dir": str(tmp_path),
    }
    exec(compile("def _probe():\n" + segment, "<benchmark-segment>", "exec"), namespace)
    namespace["_probe"]()

    run_id = namespace["eval_summary"]["run_id"]
    assert run_id.startswith("eval_")
    assert len(run_id) == len("eval_") + 12
    assert namespace["eval_summary"]["seal"] is not None


# --------------------------------------------------------------------------
# 4. 类型导入补齐
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "relpath,names",
    [
        ("virtu_omni/models/architecture.py", {"Union", "List"}),
        ("virtu_omni/computer_use/action.py", {"Tuple"}),
    ],
)
def test_typing_names_imported(relpath, names):
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            imported.update(alias.name for alias in node.names)
    missing = names - imported
    assert not missing, f"{relpath} 缺少 typing 导入: {missing}"


def test_annotations_resolve_via_get_type_hints():
    """注解真正可解析（from __future__ annotations 下 get_type_hints 会触发求值）。"""
    for module_name in ("virtu_omni.models.architecture", "virtu_omni.computer_use.action"):
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - 环境相关
            pytest.skip(f"import {module_name} failed: {exc}")
        for obj in vars(module).values():
            if isinstance(obj, type) and getattr(obj, "__module__", None) == module_name:
                try:
                    __import__("typing").get_type_hints(obj)
                except NameError as exc:
                    pytest.fail(f"{module_name}.{obj.__name__} 注解残留未定义符号: {exc}")
                except Exception:
                    pass


# --------------------------------------------------------------------------
# 5. 语法错误清理
# --------------------------------------------------------------------------
SYNTAX_FIXED_FILES = [
    "finalize_c.py",
    "generate_stepped_sleeve_artifacts.py",
    "run_flange_lifecycle_demo.py",
    "cloud_train_pack/build_high_score_corpus.py",
    "scripts/deploy_and_cleanup.py",
    "scripts/deploy_to_compshare.py",
    "scripts/merge_and_deploy_v100.py",
    "temp/run_ruler.py",
    "_bak_agentfix1_20261108_215112/tests/test_super_agent.py.HEAD.py",
]


@pytest.mark.parametrize("relpath", SYNTAX_FIXED_FILES)
def test_p0_syntax_errors_cleared(relpath):
    path = ROOT / relpath
    if not path.exists():
        pytest.skip(f"{relpath} 不存在")
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"{relpath} 仍含 UTF-8 BOM"
    compile(raw.decode("utf-8"), str(path), "exec")


def test_deploy_modelfile_renders_valid_ollama_template():
    """deploy_and_cleanup.py 的 Modelfile f-string 渲染后应输出合法 Go 模板。"""
    path = ROOT / "scripts" / "deploy_and_cleanup.py"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith('content = f"""'))
    end = next(i for i, l in enumerate(lines) if i > start and l.strip() == '"""')
    block = "\n".join(lines[start:end + 1])
    namespace = {"target_gguf_name": "virtu-master.gguf"}
    exec(compile("if True:\n" + block, "<modelfile>", "exec"), namespace)
    content = namespace["content"]
    assert content.startswith("FROM ./virtu-master.gguf")
    assert 'TEMPLATE """' in content
    assert '{"type": "function", "function": {{ .Function }}}' in content
    assert '{{- end }}"""' in content
    assert content.rstrip().endswith('"""')
