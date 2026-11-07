import win32com.client, time, os

OUT = r"D:\Virtu模型\runs\cad_cam_chain\20261030_144849"
lsp = os.path.join(OUT, "03_AutoCAD_2026.lsp").replace("\\", "/")
dwg = os.path.join(OUT, "wheel_mold_drawing.dwg").replace("\\", "/")

try:
    acad = win32com.client.GetActiveObject("AutoCAD.Application")
except Exception as e:
    print("NO ACAD:", e); raise SystemExit(1)

acad.Visible = True
print("ACAD version:", acad.Version)

# ensure a drawing is open (Start tab has no ActiveDocument)
try:
    doc = acad.ActiveDocument
    ok = getattr(doc, "Name", "") != ""
except Exception:
    ok = False
if not ok:
    acad.Documents.Add()
    time.sleep(2.0)
    doc = acad.ActiveDocument
print("Active drawing:", doc.Name)

# load lisp (forward-slash path) and run the command
doc.SendCommand('(load "%s")\n' % lsp)
time.sleep(1.5)
doc.SendCommand("(c:DRAWWHEELMOLD)\n")
time.sleep(5.0)

# verify entities
try:
    cnt = doc.ModelSpace.Count
    print("MODELSPACE_ENTITY_COUNT=%d" % cnt)
except Exception as e:
    print("count err:", e); cnt = -1

try:
    lays = [l.Name for l in doc.Layers]
    print("LAYERS:", lays)
except Exception as e:
    print("layers err:", e)

try:
    doc.SaveAs(dwg)
    print("SAVED:", dwg, "| exists:", os.path.exists(dwg))
except Exception as e:
    print("save err:", e)

with open(os.path.join(OUT, "acad_result.txt"), "w") as f:
    f.write("ENTITY_COUNT=%d\n" % cnt)
    f.write("STATUS=OK\n")
print("DONE")
