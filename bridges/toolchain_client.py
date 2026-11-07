# -*- coding: utf-8 -*-
"""bridges/toolchain_client.py — High-Level Python SDK for CAD/CAM Agent Toolchain.

Can run either in direct local mode (in-process COM/CLI bindings) or remote mode
(connecting to a running bridge server via HTTP REST API).

Usage:
    # 1. Local in-process usage:
    from bridges.toolchain_client import CADCAMToolchainClient
    client = CADCAMToolchainClient()
    status = client.preflight()
    res = client.cimco.validate("#100=50.0\nM30")

    # 2. Remote HTTP mode:
    client = CADCAMToolchainClient(base_url="http://127.0.0.1:8000")
    res = client.dispatch("solidworks", "create_part", {"part_name": "pin"})
"""

import os
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.six_software_orchestrator import SixSoftwareOrchestrator


class _SoftwareSubClient:
    def __init__(self, parent: "CADCAMToolchainClient", software_name: str):
        self._parent = parent
        self._name = software_name

    def dispatch(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._parent.dispatch(self._name, action, params)

    def health(self) -> Dict[str, Any]:
        return self.dispatch("health")


class SolidWorksClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "solidworks")

    def connect(self) -> Dict[str, Any]:
        return self.dispatch("connect")

    def create_model(self, part_name: str, dimensions: Dict[str, Any], features: Optional[List[Any]] = None) -> Dict[str, Any]:
        return self.dispatch("create_parametric_part", {
            "part_name": part_name,
            "dimensions": dimensions,
            "features": features or [],
        })

    def execute_vba(self, vba_code: str) -> Dict[str, Any]:
        return self.dispatch("execute_vba", {"code": vba_code})


class SiemensNXClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "nx")

    def run_journal(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        return self.dispatch("run_journal", {"script_path": script_path, "args": args})

    def generate_script(self, part_name: str, expressions: Dict[str, Any]) -> Dict[str, Any]:
        return self.dispatch("create_parametric_model", {
            "part_name": part_name,
            "expressions": expressions,
        })


class AutoCADClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "autocad")

    def connect(self) -> Dict[str, Any]:
        return self.dispatch("connect")

    def send_lisp(self, lisp_code: str) -> Dict[str, Any]:
        return self.dispatch("send_lisp", {"code": lisp_code})

    def create_dxf(self, drawing_name: str, entities: List[Dict[str, Any]], output_path: Optional[str] = None) -> Dict[str, Any]:
        return self.dispatch("create_dxf", {
            "drawing_name": drawing_name,
            "entities": entities,
            "output_path": output_path,
        })

    def run_headless_script(self, script_path: str, dwg_path: Optional[str] = None) -> Dict[str, Any]:
        return self.dispatch("run_headless_script", {
            "script_path": script_path,
            "dwg_path": dwg_path,
        })


class CIMCOClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "cimco")

    def validate(self, nc_code: str) -> Dict[str, Any]:
        return self.dispatch("validate_macro", {"code": nc_code})

    def launch(self, nc_file_path: str) -> Dict[str, Any]:
        return self.dispatch("launch", {"nc_file_path": nc_file_path})


class VericutClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "vericut")

    def simulate(self, project_path: str, log_output_path: Optional[str] = None) -> Dict[str, Any]:
        return self.dispatch("run_simulation", {
            "project_path": project_path,
            "log_output_path": log_output_path,
        })

    def check_collision(self, log_path: str) -> Dict[str, Any]:
        return self.dispatch("check_collision", {"log_path": log_path})


class SSCNCClient(_SoftwareSubClient):
    def __init__(self, parent):
        super().__init__(parent, "sscnc")

    def launch(self) -> Dict[str, Any]:
        return self.dispatch("launch")

    def find_window(self) -> Dict[str, Any]:
        return self.dispatch("find_window")

    def calculate_offsets(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.dispatch("calculate_offsets", {"tools": tools})


class DesktopGUIClient:
    """Sub-client for Desktop GUI Perception and Window Control."""
    def __init__(self, parent: "CADCAMToolchainClient"):
        self._parent = parent

    def capture(self, output_path: Optional[str] = None, software: Optional[str] = None) -> Dict[str, Any]:
        return self._parent.dispatch_gui("capture", {"output_path": output_path, "software": software})

    def focus(self, software: str) -> Dict[str, Any]:
        return self._parent.dispatch_gui("focus", {"software": software})

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> Dict[str, Any]:
        return self._parent.dispatch_gui("click", {"x": x, "y": y, "button": button, "double": double})

    def type_text(self, text: str) -> Dict[str, Any]:
        return self._parent.dispatch_gui("type", {"text": text})

    def hotkey(self, keys: str) -> Dict[str, Any]:
        return self._parent.dispatch_gui("hotkey", {"keys": keys})

    def dismiss_dialogs(self) -> Dict[str, Any]:
        return self._parent.dispatch_gui("dismiss_dialogs", {})


class ChainClient:
    """Sub-client for the complete 6-software manufacturing pipeline."""
    def __init__(self, parent: "CADCAMToolchainClient"):
        self._parent = parent

    def run(self, wish: str, out_root: Optional[str] = None, skip: tuple = ()) -> Dict[str, Any]:
        return self._parent.run_chain(wish, out_root=out_root, skip=skip)


class CADCAMToolchainClient:
    """Unified Client entry point for the 6-Software Industrial Toolchain."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 300):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self._orchestrator = None if self.base_url else SixSoftwareOrchestrator()

        # Software sub-clients
        self.solidworks = SolidWorksClient(self)
        self.nx = SiemensNXClient(self)
        self.autocad = AutoCADClient(self)
        self.cimco = CIMCOClient(self)
        self.vericut = VericutClient(self)
        self.sscnc = SSCNCClient(self)
        self.gui = DesktopGUIClient(self)
        self.chain = ChainClient(self)

    def preflight(self) -> Dict[str, Any]:
        """Check status of all 6 applications, shortcut resolution, and processes."""
        if self.base_url:
            return self._http_get("/v1/cadcam/preflight")
        return self._orchestrator.preflight()

    def dispatch(self, software: str, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch action to specific software bridge."""
        params = params or {}
        if self.base_url:
            payload = {
                "target_software": software,
                "action": action,
                "parameters": params,
            }
            return self._http_post("/v1/cadcam/dispatch", payload)
        return self._orchestrator.dispatch(software, action, params)

    def dispatch_gui(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch desktop GUI perception or input action."""
        params = params or {}
        if self.base_url:
            payload = {"action": action, **params}
            return self._http_post("/v1/cadcam/gui", payload)
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        if action == "capture":
            return ctl.capture(output_path=params.get("output_path"), software=params.get("software"))
        elif action == "focus":
            return ctl.focus(params.get("software", ""))
        elif action == "click":
            return ctl.click(params.get("x", 0), params.get("y", 0), button=params.get("button", "left"), double=params.get("double", False))
        elif action == "type":
            return ctl.type_text(params.get("text", ""))
        elif action == "hotkey":
            return ctl.hotkey(params.get("keys", ""))
        elif action in ("dismiss", "dismiss_dialogs"):
            return ctl.dismiss_all_dialogs()
        return {"status": "error", "message": f"Unknown GUI action: {action}"}

    def run_chain(self, wish: str, out_root: Optional[str] = None, skip: tuple = ()) -> Dict[str, Any]:
        """Execute complete CAD/CAM manufacturing chain pipeline."""
        if self.base_url:
            payload = {"wish": wish, "out_root": out_root, "skip": list(skip)}
            return self._http_post("/v1/chain/run", payload)
        return self._orchestrator.run_full_chain(wish, out_root=out_root, skip=skip)

    def _http_get(self, endpoint: str) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "CADCAMToolchainClient"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(body)
            except Exception:
                return {"error": f"HTTP {e.code}: {body}"}
        except Exception as e:
            return {"error": str(e)}

    def _http_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=raw,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "CADCAMToolchainClient"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(body)
            except Exception:
                return {"error": f"HTTP {e.code}: {body}"}
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    client = CADCAMToolchainClient()
    pf = client.preflight()
    print("Python SDK Toolchain Client Initialized.")
    print(f"Preflight status: {pf['ready_count']}/{pf['total_software']} Ready")
    res = client.cimco.validate("#100=20.0\n#101=5.0\nWHILE [#101 LE #100] DO 1\n#101=#101+1\nEND 1\nM30")
    print("CIMCO Validation Result:", res["is_valid"], "Variables:", res["variables"])
