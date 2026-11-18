"""Local-only helpers for protecting the Virtu bridge and its WorkBuddy client."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
import hmac
import threading
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Any

MODEL_ID = "virtu-cad-cam-10b"
_SERVICE_TOKEN_DIR = "ServiceAuth"


def service_token_path(service: str) -> Path:
    """Return a per-service token path under the current user's private data dir."""
    if not service or not service.isascii() or not service.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Service name must contain only ASCII letters, digits, '-' or '_'")
    base = default_token_path().parent
    if base.name.casefold() == "bridgeauth":
        base = base.parent
    return base / _SERVICE_TOKEN_DIR / service / "bearer_token"


def ensure_service_token(service: str, env_var: str,
                        path: str | Path | None = None) -> str:
    """Load a strong environment token or create/reuse a private per-service token."""
    token = os.environ.get(env_var, "")
    if token:
        token = token.strip()
    else:
        token = ensure_bridge_token(path or service_token_path(service))
    if len(token) < 32 or any(ch.isspace() for ch in token):
        raise RuntimeError(f"{env_var} must contain at least 32 non-whitespace characters")
    return token


def bearer_authorized(header_value: str, expected_token: str) -> bool:
    """Validate a single Bearer credential without leaking comparison timing."""
    if not expected_token or not isinstance(header_value, str):
        return False
    scheme, separator, supplied = header_value.partition(" ")
    return bool(separator and scheme.lower() == "bearer" and supplied.strip()
                and hmac.compare_digest(supplied.strip(), expected_token))


def path_allowed(path: str, workspace_root: str | Path) -> bool:
    """Allow only paths whose resolved path-component prefix is the workspace."""
    if not path:
        return True
    root = os.path.realpath(os.path.abspath(os.fspath(workspace_root)))
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    candidate = os.path.realpath(os.path.abspath(candidate))
    try:
        return os.path.normcase(os.path.commonpath((root, candidate))) == os.path.normcase(root)
    except (OSError, ValueError):
        return False


class _NamedMutex:
    """Cross-process named mutex backed by the Win32 kernel object.

    A process-wide ``threading.Lock`` cannot serialize two *different* bridge
    processes that both try to drive SOLIDWORKS / NX / VERICUT.  A named kernel
    mutex is honored across every process in the session, which is what the
    desktop-resource guard actually needs.

    On a non-Windows host this is a no-op shim so callers can still import it.
    """

    def __init__(self, name: str):
        self.name = name
        self._mutex = None
        self._owned = False
        if os.name == "nt":
            try:
                k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                # Win32 HANDLE is 64-bit. Without explicit signatures ctypes
                # truncates the handle through its default c_int return type,
                # making every WaitForSingleObject fail and SingleFlight always
                # report "busy".
                k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                             wintypes.LPCWSTR]
                k32.CreateMutexW.restype = wintypes.HANDLE
                k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                k32.WaitForSingleObject.restype = wintypes.DWORD
                k32.ReleaseMutex.argtypes = [wintypes.HANDLE]
                k32.ReleaseMutex.restype = wintypes.BOOL
                k32.CloseHandle.argtypes = [wintypes.HANDLE]
                k32.CloseHandle.restype = wintypes.BOOL
                # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
                h = k32.CreateMutexW(None, False, name)
                if not h:
                    raise ctypes.WinError()
                self._mutex = h
                self._k32 = k32
            except Exception:
                self._mutex = None  # fall back to the in-process lock only

    def try_acquire(self, timeout_ms: int = 0) -> bool:
        if self._mutex is None:
            return False  # signals "use the in-process fallback"
        rc = self._k32.WaitForSingleObject(self._mutex, timeout_ms)
        # WAIT_OBJECT_0 (0) or WAIT_ABANDONED (0x80): we now own it.
        if rc in (0, 0x80):
            self._owned = True
            return True
        return False

    def release(self) -> None:
        if self._mutex is None or not self._owned:
            return
        self._k32.ReleaseMutex(self._mutex)
        self._owned = False

    def close(self) -> None:
        if self._mutex:
            self._k32.CloseHandle(self._mutex)
            self._mutex = None


class SingleFlight:
    """Best-effort single-flight guard for shared desktop/software resources.

    Serializes an operation so only one runs at a time.  On Windows the guard is
    honored **across processes** via a named kernel mutex (two separate bridge
    processes can no longer drive SOLIDWORKS / NX / VERICUT simultaneously);
    on other platforms it degrades to an in-process ``threading.Lock``.
    """

    def __init__(self, name: str = "VirtuBridgeSingleFlight"):
        self._local = threading.Lock()
        self._xproc = _NamedMutex(name) if os.name == "nt" else None
        self._held = False

    def _try_lock(self) -> bool:
        if not self._local.acquire(blocking=False):
            return False
        if self._xproc is not None and not self._xproc.try_acquire():
            self._local.release()
            return False
        return True

    def _unlock(self) -> None:
        if self._xproc is not None:
            self._xproc.release()
        self._local.release()

    def run(self, func, conflict_message="Another operation is already active"):
        if not self._try_lock():
            return False, {"error": conflict_message}
        try:
            return True, func()
        finally:
            self._unlock()

    def acquire(self) -> bool:
        ok = self._try_lock()
        if ok:
            # A rejected second acquire must not clear the owner's held flag,
            # otherwise release() becomes a no-op and the lock stays stuck.
            self._held = True
        return ok

    def release(self) -> None:
        if self._held:
            self._unlock()
            self._held = False


def _secure_path(path: Path, is_dir: bool) -> None:
    if os.name == "nt":
        principal = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
        if principal == "\\":
            raise RuntimeError("Cannot determine current Windows account for token ACL")
        args = ["icacls", str(path), "/inheritance:r", "/grant:r",
                f"{principal}:" + ("(OI)(CI)F" if is_dir else "F")]
        # icacls emits the Windows ANSI code page on Chinese systems. Decoding
        # its pipes as UTF-8 causes background reader-thread errors, so keep bytes.
        result = subprocess.run(args, capture_output=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0:
            raise RuntimeError("Unable to restrict bridge token ACL; refusing to continue")
    else:
        os.chmod(path, 0o700 if is_dir else 0o600)


def default_token_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Virtu" / "BridgeAuth" / "bridge_token"
    return Path.home() / ".local" / "share" / "Virtu" / "bridge_token"


def ensure_bridge_token(path: str | Path | None = None) -> str:
    """Read an existing strong token or create one atomically without printing it."""
    target = Path(path) if path is not None else default_token_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    _secure_path(target.parent, is_dir=True)
    try:
        with target.open("x", encoding="ascii") as stream:
            token = secrets.token_urlsafe(48)
            stream.write(token + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        token = target.read_text(encoding="ascii").strip()
    if len(token) < 32 or any(ch.isspace() for ch in token):
        raise RuntimeError(f"Bridge token file is invalid or too short: {target}")
    _secure_path(target, is_dir=False)
    return token


def _atomic_write(path: Path, payload: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def sync_workbuddy_token(token: str, config_path: str | Path | None = None) -> bool:
    """Set apiKey only on the local Virtu bridge entry; preserve every other field."""
    path = Path(config_path) if config_path is not None else Path.home() / ".workbuddy" / "models.json"
    if not path.exists():
        raise FileNotFoundError(f"WorkBuddy model configuration not found: {path}")
    raw = path.read_bytes()
    try:
        models: Any = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"WorkBuddy model configuration is invalid JSON: {path}") from exc
    if not isinstance(models, list):
        raise RuntimeError("WorkBuddy model configuration must be a JSON array")
    matches = [m for m in models if isinstance(m, dict) and m.get("id") == MODEL_ID
               and "127.0.0.1:8000" in str(m.get("url", ""))]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one local {MODEL_ID} endpoint, found {len(matches)}")
    if matches[0].get("apiKey") == token:
        return False
    matches[0]["apiKey"] = token
    encoded = (json.dumps(models, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if not path.with_suffix(path.suffix + ".bak").exists():
        _atomic_write(path.with_suffix(path.suffix + ".bak"), raw)
    _atomic_write(path, encoded)
    return True
