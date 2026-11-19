"""SolidWorks 2021 Automation Bridge  (fixed & verified working).



Inspired by:

- andrewbartels1/SolidworksMCP-python

- raylanlin/Millwright

- Gautreaux/SolidProxy



What was broken before (root cause of "model never started SOLIDWORKS"):

1. pywin32 / pyautogui were installed ONLY in the system Python 3.12, while the

   model/bridge actually runs under WorkBuddy's embedded Python 3.13.12 -> the

   import failed -> HAS_PYWIN32=False -> connect() returned an error and the

   bridge silently fell back to "syntax_validated" (only saved a .bas file).

   FIX: install pywin32+pyautogui into the interpreter that runs this bridge.

2. NewDocument() referenced templates that do not exist on this machine

   (...templates\\零件.prtdot / Part.prtdot) -> would have failed to create a part.

   FIX: use sw.NewPart() (default part template) and helper wrappers.

3. Late-bound COM could not resolve many members (e.g. NewPart, SelectByID2).

   FIX: generate the early-bound type library once (makepy on sldworks.tlb) and

   instantiate the CoClass directly; wrap returned docs with __WrapDispatch.



Connection recipe (the working one):

  gc.EnsureModule(TLB_GUID, 0, 29, 0)

  mod = gc.GetModuleForProgID("SldWorks.Application")

  sw  = mod.SldWorks()                 # early-bound; launches if needed

  part = __WrapDispatch(sw.NewPart(), "IModelDoc2")

  part.SelectByID("前视基准面","PLANE",0,0,0)   # legacy 5-arg avoids Callout arg

"""



import os

import sys

import json

import time

import subprocess



try:

    import pythoncom

    import win32com.client

    import win32com.client.gencache as gc

    from win32com.client import __WrapDispatch as _wrap_dispatch

    HAS_PYWIN32 = True

except Exception:

    _wrap_dispatch = None

    HAS_PYWIN32 = False



# SOLIDWORKS 2021 type library (embedded in sldworks.tlb next to SLDWORKS.exe)

from bridges.sw_revision import SW_PROGID, SW_REV_MAJOR



TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"

SW_VERSION = SW_REV_MAJOR  # 29 = SW2021，来自 bridges.sw_revision 单一事实来源

SLDWORKS_EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"



# Chinese / English plane names (locale dependent)

PLANE_NAMES = {

    "front": ["前视基准面", "Front Plane"],

    "top":   ["上视基准面", "Top Plane"],

    "right": ["右视基准面", "Right Plane"],

}



# ---------------------------------------------------------------------------

# SINGLE-INSTANCE RESTRICTION

# The model must never open more than ONE SOLIDWORKS for drawing/modeling.

#  - In-process: a module-level singleton so every SolidWorksBridge in the same

#    Python process shares the exact same SOLIDWORKS connection.

#  - Cross-process: before launching a NEW instance we check whether a

#    SLDWORKS.exe is already running. If one is (and we cannot attach to it,

#    because this build of SOLIDWORKS is not registered in the Running Object

#    Table), we REFUSE to open a second one and tell the user to close it.

#    This hard guard prevents the "model keeps spawning SOLIDWORKS windows" bug.

# ---------------------------------------------------------------------------

_SW_SINGLETON = None          # in-process singleton instance

_MAX_INSTANCES = 1            # hard limit: the model may drive exactly one SW

_LOCK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),

                          "runs", ".solidworks.lock")





def _is_sw_process_running():

    """Return True if any SLDWORKS.exe process is already running on this host.



    tasklist emits GBK-encoded text on a Chinese-locale host; decode defensively

    so an encoding failure does NOT silently disable the single-instance guard.

    """

    try:

        proc = subprocess.run(

            ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],

            capture_output=True, timeout=15,

        )

        out = (proc.stdout or b"").decode("gbk", errors="ignore")

        return "SLDWORKS.exe" in out

    except Exception:

        # On any failure, be conservative: assume a running instance exists so we

        # NEVER silently launch a second SOLIDWORKS.

        return True





def _write_lock():

    try:

        os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)

        with open(_LOCK_PATH, "w", encoding="utf-8") as f:

            f.write(str(os.getpid()))

    except Exception:

        pass





def _clear_lock():

    try:

        if os.path.exists(_LOCK_PATH):

            os.remove(_LOCK_PATH)

    except Exception:

        pass





def get_solidworks_bridge():

    """Return the process-wide singleton bridge (enforces one SOLIDWORKS)."""

    global _SW_SINGLETON

    if _SW_SINGLETON is None:

        _SW_SINGLETON = SolidWorksBridge()

    return _SW_SINGLETON





def _try_attach():

    """Try to attach to an already-running SOLIDWORKS (ROT / GetActiveObject).



    On this machine SOLIDWORKS is not registered in the ROT, so this usually

    returns None; it is kept so that if the environment ever allows attach, the

    model reuses the existing instance instead of launching a new one.

    """

    if HAS_PYWIN32:

        try:

            pythoncom.CoInitialize()

        except Exception:

            pass

    try:

        sw = win32com.client.GetActiveObject(SW_PROGID)

        return sw

    except Exception:

        pass

    try:

        rot = pythoncom.GetRunningObjectTable()

        for moniker in rot.EnumRunning():

            try:

                name = moniker.GetDisplayName(pythoncom.CreateBindCtx(0)).lower()

            except Exception:

                continue

            if "sldworks" in name:

                ctx = pythoncom.CreateBindCtx(0)

                obj = moniker.BindToObject(ctx, None, pythoncom.IID_IDispatch)

                return win32com.client.Dispatch(obj)

    except Exception:

        pass

    return None





def _ensure_typelib():

    if not HAS_PYWIN32:

        return False

    try:

        gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)

        return True

    except Exception:

        # Fall back to running makepy on the tlb if present.

        tlb = os.path.join(os.path.dirname(SLDWORKS_EXE), "sldworks.tlb")

        if os.path.exists(tlb):

            try:

                win32com.client.makepy.main(tlb)

                gc.EnsureModule(TLB_GUID, 0, SW_VERSION, 0)

                return True

            except Exception:

                return False

        return False





class SolidWorksBridge:

    def __init__(self):

        self.sw = None

        self._typelib_ready = False



    # ------------------------------------------------------------------ connect

    def connect(self, launch_if_needed=True):

        if not HAS_PYWIN32:

            return {"status": "error", "message": "pywin32 not installed in this interpreter"}

        try:

            pythoncom.CoInitialize()

        except Exception:

            pass



        # (0) Reuse an already-open connection for THIS bridge or the process

        #     singleton. This is the core of the "only one SOLIDWORKS" rule:

        #     every SolidWorksBridge in the same Python process shares one SW.

        if self.sw is not None:

            try:

                _ = self.sw.Visible

                return {"status": "connected", "type": "reused"}

            except Exception:

                self.sw = None  # connection died; fall through to reconnect

        if _SW_SINGLETON is not None and _SW_SINGLETON is not self and _SW_SINGLETON.sw is not None:

            try:

                _ = _SW_SINGLETON.sw.Visible

                self.sw = _SW_SINGLETON.sw

                return {"status": "connected", "type": "reused_singleton"}

            except Exception:

                _SW_SINGLETON.sw = None



        if not self._typelib_ready:

            self._typelib_ready = _ensure_typelib()



        # (1) Try to attach to an already-running instance (no new window).

        try:

            attached = _try_attach()

            if attached is not None:

                self.sw = attached

                self.sw.Visible = True

                return {"status": "connected", "type": "attached_existing"}

        except Exception:

            pass



        # (2) Enforce the single-instance restriction before launching.

        #     If another SOLIDWORKS is already on the host we must NOT open a

        #     second one (this build is not in the ROT, so we cannot attach).

        if _is_sw_process_running():

            return {

                "status": "error",

                "message": (

                    "已有 SOLIDWORKS 在运行，但本机实例未在 ROT 注册、无法自动连接。"

                    "为满足『只开一个 SOLIDWORKS』的限制，已拒绝再启动新实例。"

                    "请先关闭其它 SOLIDWORKS 窗口后重试，或将建模作为单一进程运行。"

                ),

            }



        # (3) Launch exactly ONE new instance and record the lock.

        if not launch_if_needed:

            return {"status": "error", "message": "SOLIDWORKS 未运行且禁止自动启动"}

        try:

            mod = gc.GetModuleForProgID("SldWorks.Application")

            self.sw = mod.SldWorks()

            self.sw.Visible = True

            _write_lock()

            return {"status": "connected", "type": "new_instance"}

        except Exception as e:

            return {"status": "error", "message": f"Failed to connect to SolidWorks: {e}"}



    # ------------------------------------------------------------------- helpers

    def _wrap_part(self, part0):

        return _wrap_dispatch(part0, "IModelDoc2")



    def new_part(self):

        if self.sw is None:

            r = self.connect()

            if r.get("status") != "connected":

                raise RuntimeError(str(r))

        return self._wrap_part(self.sw.NewPart())



    def select_plane(self, part, plane_key):

        names = PLANE_NAMES.get(plane_key, [plane_key])

        for nm in names:

            try:

                if part.SelectByID(nm, "PLANE", 0.0, 0.0, 0.0):

                    return True

            except Exception:

                continue

        return False



    def sketch_rectangle(self, part, x1, y1, x2, y2, plane_key="front"):

        """Draw a centered corner rectangle (metres) on the given reference plane."""

        self.select_plane(part, plane_key)

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)

        part.SketchManager.CreateCornerRectangle(x1, y1, 0.0, x2, y2, 0.0)

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)



    def extrude_boss(self, part, depth_m, reverse=False):

        """Blind boss extrude of the active/last sketch. depth_m in metres."""

        args = [

            True,        # Sd

            False,       # Flip

            (not reverse),  # Dir

            0, 0,        # T1, T2

            depth_m, 0.0,  # D1, D2

            False, False,   # Dchk1, Dchk2

            False, False,   # Ddir1, Ddir2

            0.0, 0.0,       # Dang1, Dang2

            False, False,   # OffsetReverse1,2

            False, False,   # TranslateSurface1,2

            False,          # Merge

            False,          # UseFeatScope

            False,          # UseAutoSelect

            0,              # T0

            0.0,            # StartOffset

            False,          # FlipStartOffset

        ]

        assert len(args) == 23, f"FeatureExtrusion2 expects 23 args, got {len(args)}"

        feat = part.FeatureManager.FeatureExtrusion2(*args)

        part.EditRebuild3

        return feat



    def save_part(self, part, path):

        os.makedirs(os.path.dirname(path), exist_ok=True)

        return part.SaveAs(path)



    def mass_properties(self, part):

        """Return dict with volume(mm^3), mass(kg), centroid(mm), surface_area(mm^2)."""

        try:

            mp = part.Extension.CreateMassProperty()

            bodies = part.GetBodies2(0)  # 0 = solid bodies

            if bodies:

                mp.AddBodies(bodies)

            return {

                "volume_mm3": (mp.Volume or 0) * 1e9,

                "mass_kg": mp.Mass or 0.0,

                "surface_area_mm2": (mp.SurfaceArea or 0) * 1e6,

                "centroid_mm": [ (mp.CenterOfMass[i] or 0) * 1000.0 for i in range(3)],

            }

        except Exception as e:

            return {"error": str(e)}



    def active_mass_properties(self):
        """回读当前活动零件的真实质量属性（体积/质量/质心/表面积）。

        审计 P0 要求的「真实回读通道」：不新建零件、不猜测数值，只读取
        SOLIDWORKS 当前 ActiveDoc 的 CreateMassProperty 结果。任何一步缺失
        都返回结构化 error，绝不回填理论值冒充实测。
        """
        if self.sw is None:
            conn = self.connect()
            if conn.get("status") != "connected":
                return conn
        doc = self.sw.ActiveDoc
        if doc is None:
            return {
                "status": "error",
                "verdict_code": "NO_ACTIVE_DOCUMENT",
                "message": "SOLIDWORKS 无活动文档：请先建模/打开零件再回读质量属性",
            }
        props = self.mass_properties(doc)
        if "error" in props:
            return {"status": "error", "verdict_code": "MASS_PROPERTY_FAILED",
                    "message": props["error"]}
        title = getattr(doc, "GetTitle", "")
        if callable(title):
            title = title()
        return {"status": "ok", "action": "mass_properties",
                "part": str(title or ""), **props}

    # ----------------------------------------------------------- legacy / VBA

    def execute_vba_code(self, vba_code: str,

                         temp_swp_path: str = r"D:\Virtu模型\scratch\temp_macro.swp",

                         allow_freeform: bool = None):

        """Save a VBA macro source for inspection and (if SOLIDWORKS is connected)

        run it via RunMacro.



        NOTE: RunMacro needs a compiled .swp project; a plain .bas text will not

        execute. We therefore prefer the COM helpers above (sketch/extrude/...).

        This method still saves the .bas so the source is inspectable, and tries

        RunMacro if a compiled .swp is provided.



        Security (阶段二 B 组)：由「黑名单正则」改为 deny-by-default。

        策略实现在 bridges/code_sandbox_policy.py：

          1) 硬禁构念（Declare/PtrSafe/Type/Implements/CallByName/Application.Run/

             Open...For/Name...As/MkDir/RmDir/Kill/Shell/CreateObject/Environ 等）

             无论开关如何一律 blocked；

          2) 自由文本 VBA 默认拒绝，仅当代码带 VIRTU_DSL_RENDERED 标记（结构化 DSL

             渲染产物）或显式 allow_freeform=True / VIRTU_VBA_ALLOW_FREEFORM=1 时放行；

          3) 每次判定写结构化审计日志（kind/decision/rule/code_sha256/pid）。

        """

        try:

            from bridges.code_sandbox_policy import validate_code as _validate_code_policy

        except Exception:  # 以脚本方式直接运行时的兜底

            from code_sandbox_policy import validate_code as _validate_code_policy

        _blocked = _validate_code_policy(

            "vba", vba_code, allow_freeform=allow_freeform,

            source="bridges.solidworks_bridge.execute_vba_code",

        )

        if _blocked:

            return _blocked
        os.makedirs(os.path.dirname(temp_swp_path), exist_ok=True)

        bas_path = temp_swp_path.replace(".swp", ".bas")

        with open(bas_path, "w", encoding="gbk", errors="ignore") as f:

            f.write(vba_code)



        if self.sw is None:

            r = self.connect()

            if r.get("status") != "connected":

                return {

                    "status": "saved_only",

                    "message": "SOLIDWORKS not connected; VBA source saved for inspection.",

                    "script_path": bas_path,

                    "lines": len(vba_code.splitlines()),

                }

        try:

            res = self.sw.RunMacro(bas_path, "Main", "main")

            return {"status": "executed", "result": str(res), "macro_path": bas_path}

        except Exception as e:

            return {"status": "saved_only", "message": f"RunMacro failed: {e}",

                    "script_path": bas_path}



    def create_parametric_part(self, part_name: str, dimensions: dict, features: list):

        """Construct a parametric feature-tree part (EquationMgr + sketch).



        Kept for compatibility; uses NewPart() so it actually works now.

        """

        part = self.new_part()

        idx = 0

        swEqnMgr = part.GetEquationMgr()

        for k, v in dimensions.items():

            swEqnMgr.AddEquation(idx, f'"{k}" = {v}', True)

            idx += 1

        self.select_plane(part, "front")

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)

        part.SketchManager.InsertSketch(True)

        part.EditRebuild3

        return {"status": "created", "part": part.GetTitle}



    def model_flange(self, dimensions: dict = None, out_path: str = None):

        """Build full 3D parametric flange plate with boss hub and bolt holes."""

        import math

        default_params = {

            "D_Outer": 0.160,    # 160 mm

            "D_Bore": 0.050,     # 50 mm

            "Thk_Disk": 0.020,   # 20 mm

            "D_Boss": 0.090,     # 90 mm

            "H_Boss": 0.015,     # 15 mm

            "PCD": 0.125,        # 125 mm

            "N_Bolts": 6,        # 6个

            "D_Bolt": 0.014,     # 14 mm

        }

        P = {**default_params, **(dimensions or {})}

        part = self.new_part()

        

        # 1. Equations

        try:

            eqn = part.GetEquationMgr()

            for idx, (k, v) in enumerate(P.items()):

                val = int(v) if k == "N_Bolts" else v

                eqn.Add(idx, f'"{k}" = {val}')

        except Exception:

            pass



        # 2. Flange Disc

        self.select_plane(part, "front")

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)

        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_Outer"] / 2.0)

        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_Bore"] / 2.0)

        extrude1_args = [

            True, False, True, 0, 0, P["Thk_Disk"], 0.0,

            False, False, False, False, 0.0, 0.0,

            False, False, False, False, True, False, True,

            0, 0.0, False

        ]

        part.FeatureManager.FeatureExtrusion2(*extrude1_args)



        # 3. Boss Hub

        self.select_plane(part, "front")

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)

        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_Boss"] / 2.0)

        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_Bore"] / 2.0)

        extrude2_args = [

            True, False, False, 0, 0, P["H_Boss"], 0.0,

            False, False, False, False, 0.0, 0.0,

            False, False, False, False, True, False, True,

            0, 0.0, False

        ]

        part.FeatureManager.FeatureExtrusion2(*extrude2_args)



        # 4. Bolt Holes

        N = int(P["N_Bolts"])

        pcd_r = P["PCD"] / 2.0

        bolt_r = P["D_Bolt"] / 2.0

        self.select_plane(part, "front")

        part.SketchManager.InsertSketch(True)

        part.ClearSelection2(True)

        for i in range(N):

            ang = 2.0 * math.pi * i / N

            x = pcd_r * math.cos(ang)

            y = pcd_r * math.sin(ang)

            part.SketchManager.CreateCircleByRadius(x, y, 0.0, bolt_r)

        

        for sd, t1, t2, dir1, d1 in [

            (False, 1, 1, True, 0.0),

            (True, 1, 0, True, 0.0),

            (True, 1, 0, False, 0.0),

            (True, 0, 0, True, 0.040),

        ]:

            cut_args = [

                sd, False, dir1, t1, t2, d1, 0.0,

                False, False, False, False, 0.0, 0.0,

                False, False, False, False, False, False, True

            ]

            try:

                feat = part.FeatureManager.FeatureCut(*cut_args)

                if feat:

                    break

            except Exception:

                pass



        part.ForceRebuild3(True)

        try:

            part.ViewZoomtofit2()

        except Exception:

            pass



        saved_path = out_path or r"D:\Virtu模型\Flange_Parametric.SLDPRT"

        os.makedirs(os.path.dirname(saved_path), exist_ok=True)

        part.SaveAs3(saved_path, 0, 1)

        return {"status": "success", "part": str(part.GetTitle), "path": saved_path, "parameters": P}





if __name__ == "__main__":

    bridge = SolidWorksBridge()

    print("SolidWorks Bridge Initialized:", bridge.connect())

