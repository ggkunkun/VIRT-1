# =========================================================================
# Siemens NX 12.0 Python Open API Parametric Journal
# Intent: Parametric Generation of Engineered Workpiece
# Material: Cr12MoV | OD: 53.0mm | ID: 14.0mm
# =========================================================================

import NXOpen
import NXOpen.UF
import math

def main():
    the_session = NXOpen.Session.GetSession()
    the_uf_session = NXOpen.UF.UFSession.GetUFSession()

    # 0. Create or acquire working part
    work_part = the_session.Parts.Work
    if work_part is None:
        import os
        _out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nx_part.prt")
        work_part = the_session.Parts.NewDisplay(_out, NXOpen.Part.Units.Millimeters)
        the_session.Parts.SetWork(work_part)

    # 1. Define Parametric Expressions in Expression Manager
    exp_mgr = work_part.Expressions
    mm = work_part.UnitCollection.FindObject("MilliMeter")
    
    exp_mgr.CreateWithUnits(f"D_OUTER=53.0", mm)
    exp_mgr.CreateWithUnits(f"D_BORE=14.0", mm)
    exp_mgr.CreateWithUnits(f"TOTAL_LENGTH=45.0", mm)
    exp_mgr.CreateWithUnits(f"GROOVE_R=3.0", mm)
    for _i, _rr in enumerate([3.0], 1):
        exp_mgr.CreateWithUnits(f"GROOVE_R{_i}={_rr}", mm)

    # 2. Create Outer Cylinder Stock
    cyl_tag = the_uf_session.ModlFeatures.CreateCyl1(
        NXOpen.UF.ModlFeatureSigns.NULLSIGN,
        [0.0, 0.0, 0.0],
        f"45.0",
        f"53.0",
        [0.0, 0.0, -1.0]
    )

    # 3. Create Inner Bore Cylinder (Boolean Subtraction)
    bore_tag = the_uf_session.ModlFeatures.CreateCyl1(
        NXOpen.UF.ModlFeatureSigns.NEGATIVE,
        [0.0, 0.0, 0.0],
        f"50.0",
        f"14.0",
        [0.0, 0.0, -1.0]
    )

    # 4. Save Work Part
    the_uf_session.Modl.Update()
    work_part.Save(NXOpen.BasePart.SaveComponents.TrueValue, NXOpen.BasePart.CloseAfterSave.FalseValue)
    print(f"[SUCCESS] Siemens NX 12.0 Parametric Model Built: {work_part.FullPath}")

if __name__ == "__main__":
    main()
