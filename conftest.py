import sys
import os
import shutil
import socket
import tempfile
import urllib.request

import pytest

# Add root directory to sys.path for test discovery
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

# 仓库内 vendored 依赖：harness2 以源码形式放在 harness2_src/ 下（不是 pip 安装）。
# 不加入 sys.path 时 tests/test_virtu_harness2.py 等会在收集阶段直接 ImportError，
# 导致整套测试中断。这里显式挂载 vendor 根目录。
_VENDOR_HARNESS2 = os.path.join(_ROOT, "harness2_src")
if os.path.isdir(_VENDOR_HARNESS2) and _VENDOR_HARNESS2 not in sys.path:
    sys.path.insert(0, _VENDOR_HARNESS2)


def pytest_configure(config):
    """会话级 stdout/stderr 强制 UTF-8：本机控制台默认 cp936/gbk，
    用例打印 Ø、µm、─ 等字符会抛 UnicodeEncodeError 把真实断言淹没成假红
    （与 scripts/workbuddy_virtu_bridge.py::run_server 的处理同源）。"""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    """把 pytest 的临时根目录挪到系统 TEMP，并显式指定 basetemp。

    两个本机约束：
    1. 安全删除垫片拒绝对工作区内目录做 rmtree —— 旧的
       ``--basetemp=.pytest_tmp_fix`` 会让**所有**用例在 teardown 报 ERROR；
    2. 系统 TEMP 下的默认布局会创建 ``pytest-current`` 符号链接，Windows 上
       无权限时抛 ``PermissionError: [WinError 5]``。
    显式给 ``--basetemp`` 时 pytest 直接使用该目录、不建符号链接，两条都避开。
    """
    if not config.option.basetemp:
        config.option.basetemp = os.path.join(
            tempfile.gettempdir(), f"virtu_pytest_{os.getpid()}")


@pytest.fixture(autouse=True)
def _hermetic_internet(monkeypatch):
    """Unit tests never touch live web search unless a test explicitly enables it.

    ``virtu_router`` / ``virtu_real_backend`` / the serving server all augment
    prompts with live web evidence by default; hermetic tests must opt in.

    ``VIRTU_TRAINING_KB`` 是独立的本地知识注入开关：摄入的 VERICUT 官方培训
    知识在运行时默认会进 prompt，但测试会话必须关掉，否则
    ``test_internet_augmentation`` 里「离线时 prompt 必须原样返回」的断言会被
    本地知识打破。要验证该注入的测试需显式 monkeypatch 回 on。
    """
    monkeypatch.setenv("VIRTU_INTERNET", "off")
    monkeypatch.setenv("VIRTU_TRAINING_KB", "off")


# ---------------------------------------------------------------------------
# 会话级：禁止「真模型请求把整仓 pytest 挂死」
# ---------------------------------------------------------------------------
# 真因（2026-11-14 两次全仓实测）：deep_agent.chat 的 chat_timeout_s 默认 600 /
# REACT 预算 90，sleep_framework 的 model_caller 超时 90；本机 Ollama 能列模型但
# /api/chat 不返回，规划 + 验收（或梦境 + 稳态）两次调用就超过 --timeout=120，
# Windows 上 pytest-timeout 直接终止整个 pytest 进程，日志停在 "++++ Timeout ++++"
# 且没有 summary / FAILED 列表。逐文件打补丁治不了共享全局单例的 caller 泄漏。
# 这里只夹「指向本机 11434 的 /api/chat 生成请求」；/api/tags 探测、其他 HTTP
# 服务、以及所有显式不需要模型的路径一律不动。超时后产品代码走既有的诚实降级。
_OPENER_OPEN = urllib.request.OpenerDirector.open
_OLLAMA_TEST_TIMEOUT_S = float(os.environ.get("VIRTU_PYTEST_OLLAMA_TIMEOUT_S", "3") or 3)


def _bounded_opener_open(self, fullurl, data=None,
                         timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *args, **kwargs):
    url = getattr(fullurl, "full_url", None) or (fullurl if isinstance(fullurl, str) else "")
    if "11434" in url and "/api/chat" in url:
        base = timeout if isinstance(timeout, (int, float)) else _OLLAMA_TEST_TIMEOUT_S
        timeout = min(base, _OLLAMA_TEST_TIMEOUT_S)
    return _OPENER_OPEN(self, fullurl, data, timeout, *args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _hermetic_ollama_calls():
    urllib.request.OpenerDirector.open = _bounded_opener_open
    try:
        yield
    finally:
        urllib.request.OpenerDirector.open = _OPENER_OPEN


_DESKTOP_ENV_KEYS = (
    "VIRTU_DESKTOP_INPUT",
    "VIRTU_DESKTOP_INPUT_DRYRUN",
    "VIRTU_DESKTOP_KILL",
    "VIRTU_DESKTOP_STATE_DIR",
    "VIRTU_PYTEST_ACTIVE",
)


@pytest.fixture(scope="session", autouse=True)
def _isolate_desktop_input(tmp_path_factory):
    """测试会话内彻底切断真实键鼠总线。

    事故根因：``tests/test_computer_use_integration.py`` 会真的跑
    ``move(400,300)`` → ``click`` → ``type("OK")`` → ``ctrl+s`` → ``drag(10,10→50,50)``。
    任何一次 ``pytest tests/`` 都会把操作者的光标拽走、点一下、再拖一段——
    这就是"智能体突然失控抢鼠标"最稳定的复现路径。

    三道隔离：
    1. ``VIRTU_DESKTOP_INPUT=0`` + ``DRYRUN=1``：即使外部 shell 里开着授权，
       测试也不会向真实总线写事件；
    2. 状态目录指向 tmp：不会被生产环境的 STOP 文件误伤，也不往生产审计日志里灌测试噪声；
    3. ``VIRTU_PYTEST_ACTIVE=1``：给 ``input_guard`` 一个不依赖 ``sys.modules`` 的判据。

    要验证"真的会发事件"的路径，测试应 monkeypatch 底层 Win32 调用并断言调用序列，
    而不是放开这道闸门。
    """
    saved = {k: os.environ.get(k) for k in _DESKTOP_ENV_KEYS}
    state_dir = tmp_path_factory.mktemp("desktop_input")
    os.environ["VIRTU_DESKTOP_INPUT"] = "0"
    os.environ["VIRTU_DESKTOP_INPUT_DRYRUN"] = "1"
    os.environ.pop("VIRTU_DESKTOP_KILL", None)
    os.environ["VIRTU_DESKTOP_STATE_DIR"] = str(state_dir)
    os.environ["VIRTU_PYTEST_ACTIVE"] = "1"
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="session", autouse=True)
def _isolate_hindsight_storage(tmp_path_factory):
    """隔离测试期 Hindsight 持久化，避免 pytest 把临时实验记录写回生产 hindsight_banks.json。"""
    prev = os.environ.get("VIRTU_HINDSIGHT_PATH")
    mem_dir = tmp_path_factory.mktemp("hindsight_session")
    session_store = mem_dir / "hindsight_banks.json"
    real_store = os.path.join(_ROOT, "data", "memory", "hindsight_banks.json")
    if os.path.isfile(real_store):
        shutil.copy2(real_store, session_store)
    os.environ["VIRTU_HINDSIGHT_PATH"] = str(session_store)
    try:
        yield session_store
    finally:
        if prev is None:
            os.environ.pop("VIRTU_HINDSIGHT_PATH", None)
        else:
            os.environ["VIRTU_HINDSIGHT_PATH"] = prev


