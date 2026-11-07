import json
import tempfile
import threading
import uuid
from pathlib import Path

from bridges import bridge_security


def test_bearer_authorization_fails_closed_and_accepts_exact_token():
    token = "unit-test-token-" + "x" * 48
    assert bridge_security.bearer_authorized("", token) is False
    assert bridge_security.bearer_authorized("Bearer wrong", token) is False
    assert bridge_security.bearer_authorized(f"Bearer {token}", token) is True
    assert bridge_security.bearer_authorized(f"Basic {token}", token) is False
    assert bridge_security.bearer_authorized(f"Bearer {token}x", token) is False
    assert bridge_security.bearer_authorized(f"Bearer {token}", "") is False


def test_path_guard_rejects_sibling_prefix_and_parent_traversal():
    root = Path("D:/Virtu模型")
    assert bridge_security.path_allowed("D:/Virtu模型/runs/safe/out.nc", root) is True
    assert bridge_security.path_allowed("D:/Virtu模型_evil/out.nc", root) is False
    assert bridge_security.path_allowed("D:/Virtu模型/../Windows/system.ini", root) is False
    assert bridge_security.path_allowed("", root) is True


def test_path_guard_rejects_symlink_escape_when_supported():
    with tempfile.TemporaryDirectory(prefix="virtu-sec-") as temp:
        root = Path(temp) / "workspace"
        outside = Path(temp) / "outside"
        root.mkdir()
        outside.mkdir()
        link = root / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        assert bridge_security.path_allowed(str(link / "secret.nc"), root) is False


def test_single_flight_blocks_parallel_work_and_releases_after_exception():
    lock = bridge_security.SingleFlight(name="VirtuSecurityTest-" + uuid.uuid4().hex)
    entered = threading.Event()
    release = threading.Event()
    result = []

    def holder():
        def operation():
            entered.set()
            release.wait(timeout=5)
            return "done"
        result.append(lock.run(operation))

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(timeout=5)
    blocked, payload = lock.run(lambda: "should not run")
    assert blocked is False
    assert "error" in payload
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert result == [(True, "done")]

    try:
        lock.run(lambda: (_ for _ in ()).throw(ValueError("expected")))
    except ValueError:
        pass
    assert lock.run(lambda: 42) == (True, 42)


def test_token_creation_reuses_strong_secret_without_exposing_it():
    with tempfile.TemporaryDirectory(prefix="virtu-token-") as temp:
        token_path = Path(temp) / "BridgeAuth" / "bridge_token"
        original_secure_path = bridge_security._secure_path
        bridge_security._secure_path = lambda *_args, **_kwargs: None
        try:
            first = bridge_security.ensure_bridge_token(token_path)
            second = bridge_security.ensure_bridge_token(token_path)
        finally:
            bridge_security._secure_path = original_secure_path
        assert len(first) >= 32
        assert first == second
        assert token_path.read_text(encoding="ascii").strip() == first


def test_workbuddy_sync_changes_only_local_virtu_entry_and_backs_up():
    with tempfile.TemporaryDirectory(prefix="virtu-models-") as temp:
        path = Path(temp) / "models.json"
        rows = [
            {"id": "other-model", "apiKey": "leave-this-alone", "url": "https://example.invalid/v1"},
            {"id": bridge_security.MODEL_ID, "apiKey": "old", "url": "http://127.0.0.1:8000/v1/chat/completions",
             "supportsToolCall": True, "name": "Virtu"},
        ]
        original = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode()
        path.write_bytes(original)

        assert bridge_security.sync_workbuddy_token("a" * 64, path) is True
        updated = json.loads(path.read_text(encoding="utf-8"))
        assert updated[0] == rows[0]
        assert updated[1]["apiKey"] == "a" * 64
        assert updated[1]["supportsToolCall"] is True
        assert path.with_suffix(".json.bak").read_bytes() == original
        assert bridge_security.sync_workbuddy_token("a" * 64, path) is False


def test_workbuddy_sync_rejects_ambiguous_or_nonlocal_entries():
    with tempfile.TemporaryDirectory(prefix="virtu-ambiguous-") as temp:
        path = Path(temp) / "models.json"
        path.write_text(json.dumps([{"id": bridge_security.MODEL_ID,
                                     "url": "https://remote.invalid/v1"}]), encoding="utf-8")
        try:
            bridge_security.sync_workbuddy_token("b" * 64, path)
        except RuntimeError as exc:
            assert "exactly one" in str(exc)
        else:
            raise AssertionError("ambiguous or nonlocal model entry must be rejected")
