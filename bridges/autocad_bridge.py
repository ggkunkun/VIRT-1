"""AutoCAD 2026 Automation Bridge.



Inspired by:

- U-C4N/Autocad-MCP (FastMCP live COM + headless ezdxf)

- daobataotie/CAD-MCP (Draw -> Inspect -> Correct loop)

- puran-water/autocad-mcp (AutoLISP + File IPC)

- ezdxf & pyautocad



Features:

- Live AutoCAD COM interface (AutoCAD.Application.25)

- Direct AutoLISP script generator and injection (.lsp)

- Headless DXF parsing and creation via ezdxf

- GD&T tolerance symbols, TitleBlock annotations, and multi-layer management

"""



import os

import sys

import json

import subprocess



try:

    import win32com.client

    HAS_PYWIN32 = True

except ImportError:

    HAS_PYWIN32 = False



try:

    import ezdxf

    HAS_EZDXF = True

except ImportError:

    HAS_EZDXF = False



AUTOCAD_EXE = r"D:\cad2026\AutoCAD 2026\acad.exe"





ACCORECONSOLE_EXE = r"D:\cad2026\AutoCAD 2026\accoreconsole.exe"





class AutoCADBridge:

    def __init__(self):

        self.acad_app = None

        self.accoreconsole_exe = ACCORECONSOLE_EXE



    def run_headless_script(self, script_path: str, dwg_path: str = None, timeout: int = 120):

        """Execute AutoLISP/SCR script headless via accoreconsole.exe."""

        if not os.path.exists(self.accoreconsole_exe):

            return {"status": "error", "message": f"accoreconsole not found: {self.accoreconsole_exe}"}

        if not os.path.exists(script_path):

            return {"status": "error", "message": f"Script not found: {script_path}"}



        cmd = [self.accoreconsole_exe, "/s", script_path]

        if dwg_path and os.path.exists(dwg_path):

            cmd.extend(["/i", dwg_path])



        try:

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            return {

                "status": "success" if res.returncode == 0 else "failed",

                "returncode": res.returncode,

                "stdout": res.stdout[-1000:],

                "stderr": res.stderr[-1000:],

            }

        except Exception as e:

            return {"status": "error", "message": str(e)}



    def connect(self):

        """Connect to active AutoCAD instance or launch it."""

        if not HAS_PYWIN32:

            return {"status": "error", "message": "pywin32 not installed"}

        try:

            import pythoncom

            pythoncom.CoInitialize()

        except Exception:

            pass

        try:

            self.acad_app = win32com.client.GetActiveObject("AutoCAD.Application")

            return {"status": "connected", "type": "active_instance"}

        except Exception:

            try:

                self.acad_app = win32com.client.Dispatch("AutoCAD.Application")

                self.acad_app.Visible = True

                return {"status": "connected", "type": "new_instance"}

            except Exception as e:

                return {"status": "error", "message": f"Failed to connect to AutoCAD: {e}"}



    def send_lisp_command(self, lisp_code: str):

        """Send AutoLISP expression to active AutoCAD document."""

        # Security sanitizer: block dangerous AutoLISP execution

        import re

        if re.search(r"(?i)\b(startapp|vl-file-delete|vl-file-copy|vl-file-rename|command\s+.*sh)\b", lisp_code or ""):

            return {

                "status": "blocked",

                "verdict_code": "AUTOLISP_SECURITY_VIOLATION",

                "message": "AutoLISP command contains disallowed system execution or file deletion functions.",

            }

        conn = self.connect()

        if conn.get("status") == "error":

            # Save to scratch file for manual or headless run

            scratch_path = r"D:\Virtu模型\scratch\temp_command.lsp"

            os.makedirs(os.path.dirname(scratch_path), exist_ok=True)

            with open(scratch_path, "w", encoding="utf-8") as f:

                f.write(lisp_code)

            return {

                "status": "saved_to_lsp",

                "message": "AutoCAD not active; AutoLISP script saved to scratch.",

                "path": scratch_path

            }



        try:

            doc = self.acad_app.ActiveDocument

            doc.SendCommand(f"{lisp_code}\n")

            return {"status": "executed", "code": lisp_code}

        except Exception as e:

            return {"status": "error", "message": str(e)}



    def create_headless_dxf(self, drawing_name: str, entities: list, output_path: str = None):

        """Generate high-precision DXF drawing using ezdxf without needing AutoCAD GUI."""

        if not HAS_EZDXF:

            return {"status": "error", "message": "ezdxf library not available"}



        if not output_path:

            output_path = rf"D:\Virtu模型\scratch\{drawing_name}.dxf"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)



        doc = ezdxf.new("R2018")

        msp = doc.modelspace()



        # Add layers

        doc.layers.add(name="OUTLINE", color=7)

        doc.layers.add(name="CENTER", color=1, linetype="CENTER")

        doc.layers.add(name="DIMENSION", color=3)



        for ent in entities:

            etype = ent.get("type")

            if etype == "circle":

                msp.add_circle(ent["center"], ent["radius"], dxfattribs={"layer": "OUTLINE"})

            elif etype == "line":

                msp.add_line(ent["start"], ent["end"], dxfattribs={"layer": ent.get("layer", "OUTLINE")})

            elif etype == "text":

                height = ent.get("height", 3.5)

                text_entity = msp.add_text(ent["text"], dxfattribs={"layer": "DIMENSION", "height": height})

                text_entity.set_placement(ent["pos"])



        doc.saveas(output_path)

        return {"status": "success", "dxf_path": output_path, "entities_count": len(entities)}





if __name__ == "__main__":

    bridge = AutoCADBridge()

    print("AutoCAD Bridge Initialized.")

