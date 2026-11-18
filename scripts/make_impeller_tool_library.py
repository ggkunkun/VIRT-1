# -*- coding: utf-8 -*-
"""Generate a minimal VERICUT 9.6 tool library matching our NC's T1/T2 tools.

T1 = D16 flat-end roughing mill (shank r=8, flute length 40, reach 60)
T2 = D8 ball-nose, D5 neck, reach 70 mm (matches impeller_cam_from_geometry.py:
     R_BALL=4.0, R_NECK=2.5, REACH=70.0)

We clone a real tool block from the CGTech sample library to guarantee the XML
schema/attributes are valid, then rewrite only the cutter profile + description.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

SRC = Path(r"E:\samples\TLS\force-impeller.tls")
DST = Path(r"D:\Virtu模型\artifacts\aero_closed_impeller\impeller_tools.tls")


def build_tool(tool_id: str, desc: str, pts: list[tuple[float, float]],
               ball_top: tuple[float, float, float] | None,
               flute: float, gage_z: float) -> str:
    """Build one <Tool> block using a minimal but schema-complete structure."""
    arc = ""
    if ball_top:
        bx, bz, br = ball_top
        arc = f"""          <Arc>
            <X>{bx:.4f}</X>
            <Z>{bz:.4f}</Z>
            <Radius>{br:.4f}</Radius>
          </Arc>
"""
    pts_xml = "\n".join(
        f"          <Pt>\n            <X>{x:.4f}</X>\n            <Z>{z:.4f}</Z>\n          </Pt>"
        for x, z in pts)
    return f"""    <Tool ID="{tool_id}" Units="Millimeter">
      <Description>{desc}</Description>
      <Type>Milling</Type>
      <CoolantThru>0</CoolantThru>
      <GageCompId>Tool Origin</GageCompId>
      <GagePoint>
        <X>0.0000</X>
        <Y>0.0000</Y>
        <Z>{gage_z:.4f}</Z>
      </GagePoint>
      <Cutter>
        <SOR ID="T{tool_id}" ParentID="HOLDER{tool_id}" Insert="no" DRILLMILL="FALSE">
{pts_xml}
{arc}          <Origin>
            <X>0</X>
            <Y>0</Y>
            <Z>0</Z>
          </Origin>
          <FluteLength>{flute}</FluteLength>
          <ShankDiameter>0</ShankDiameter>
          <SpindleDirection>CW</SpindleDirection>
          <TeethCount>4</TeethCount>
        </SOR>
        <Holder ID="HOLDER{tool_id}">
          <SOR ID="HOLDER{tool_id}" ParentID="" Insert="no" DRILLMILL="FALSE">
            <Pt><X>0</X><Z>0</Z></Pt>
            <Pt><X>5</X><Z>0</Z></Pt>
            <Pt><X>5</X><Z>40</Z></Pt>
            <Pt><X>0</X><Z>40</Z></Pt>
            <Origin><X>0</X><Y>0</Y><Z>0</Z></Origin>
          </SOR>
        </Holder>
      </Cutter>
      <DrivenPoint ID="1">
        <AttachCompId>T{tool_id}</AttachCompId>
        <Type>0</Type>
        <X>0</X><Y>0</Y><Z>0</Z>
      </DrivenPoint>
    </Tool>
"""


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    # keep header + <Tools> opening, replace everything up to </Tools>
    head = src.split("<Tools>")[0] + "<Tools>\n"
    tail = "\n  </Tools>\n</CGTechToolLibrary>\n"

    # T1: D16 flat endmill. Profile from tip (0,0) out to r=8, up the flute.
    # Note VERICUT SOR profile is in the X-Z plane, Z increasing away from tip.
    t1 = build_tool(
        "1", "D16 Flat Endmill (roughing)",
        pts=[(0, 0), (8, 0), (8, 40), (8, 55), (0, 55)],
        ball_top=None, flute=40, gage_z=55)

    # T2: D8 ball-nose, D5 neck, 70 reach.
    # Ball radius 4 -> hemisphere from tip; then neck r=2.5 to reach.
    t2 = build_tool(
        "2", "D8 Ball-nose, D5 neck, 70mm reach (5-axis finish)",
        pts=[(0, 0), (4, 4), (2.5, 8), (2.5, 70), (0, 70)],
        ball_top=(0, 0, 4), flute=15, gage_z=70)

    DST.write_text(head + t1 + t2 + tail, encoding="utf-8")
    print("wrote", DST, DST.stat().st_size, "bytes")

    # Validate well-formed XML
    import xml.etree.ElementTree as ET
    root = ET.parse(DST).getroot()
    tools = root.findall(".//Tool")
    print("XML OK, tools:", [t.get("ID") for t in tools])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
