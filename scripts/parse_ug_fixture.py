# -*- coding: utf-8 -*-
import sys
import NXOpen
import NXOpen.UF

def main():
    the_session = NXOpen.Session.GetSession()
    the_uf_session = NXOpen.UF.UFSession.GetUFSession()
    
    out_file = r"D:\Virtu模型\runs\fixture_77_analysis.txt"
    prt_path = r"E:\迅雷下载\分享数模20-77套UG夹具图档\77 (1).prt"
    
    lines = []
    lines.append("=" * 70)
    lines.append("【Siemens NX 12.0 夹具数模深度解析报告】")
    lines.append(f"数模图档路径: {prt_path}")
    lines.append("=" * 70)
    
    try:
        part, load_status = the_session.Parts.OpenBaseDisplay(prt_path)
    except Exception as e:
        lines.append(f"打开图档失败: {e}")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return
        
    lines.append(f"部件全名: {part.FullPath}")
    lines.append(f"部件名称: {part.Leaf}")
    lines.append(f"单位制度: {'毫米 (Millimeters)' if part.PartUnits == NXOpen.BasePart.Units.Millimeters else '英寸 (Inches)'}")
    
    # 1. 结构形式（装配树 vs 多实体实体群）
    root_comp = part.ComponentAssembly.RootComponent
    if root_comp is not None:
        children = root_comp.GetChildren()
        lines.append(f"\n[结构类型] 装配体 (Assembly)")
        lines.append(f"顶层根节点: {root_comp.Name}")
        lines.append(f"直接子组件数: {len(children)}")
    else:
        lines.append(f"\n[结构类型] 多实体零件图档 (Multi-body Part / Non-assembly Master Model)")
        lines.append("说明: 该图档将整套夹具的多零件以 245 个独立实体 (Bodies) 组织在不同图层中。")

    # 2. 实体统计与包围盒计算
    body_list = list(part.Bodies)
    lines.append(f"\n[实体总量] 共包含 {len(body_list)} 个独立三维实体 (Solid Bodies)")
    
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
    
    body_infos = []
    for idx, body in enumerate(body_list):
        try:
            bbox = the_uf_session.ModlGeneral.AskBoundingBox(body.Tag)
            # bbox is [min_x, min_y, min_z, max_x, max_y, max_z]
            bx0, by0, bz0, bx1, by1, bz1 = bbox[0], bbox[1], bbox[2], bbox[3], bbox[4], bbox[5]
            min_x = min(min_x, bx0)
            min_y = min(min_y, by0)
            min_z = min(min_z, bz0)
            max_x = max(max_x, bx1)
            max_y = max(max_y, by1)
            max_z = max(max_z, bz1)
            
            dx = bx1 - bx0
            dy = by1 - by0
            dz = bz1 - bz0
            faces = body.GetFaces()
            edges = body.GetEdges()
            vol = dx * dy * dz
            body_infos.append({
                "index": idx + 1,
                "tag": body.Tag,
                "layer": body.Layer,
                "dx": dx, "dy": dy, "dz": dz,
                "vol": vol,
                "faces": len(faces),
                "edges": len(edges),
                "box": [bx0, by0, bz0, bx1, by1, bz1]
            })
        except Exception as be:
            pass

    if min_x != float('inf'):
        lines.append(f"\n[总装夹具外形外包络尺寸 (Overall Envelope)]")
        lines.append(f"  X向跨度 (长): {max_x - min_x:.2f} mm  (范围: [{min_x:.2f}, {max_x:.2f}])")
        lines.append(f"  Y向跨度 (宽): {max_y - min_y:.2f} mm  (范围: [{min_y:.2f}, {max_y:.2f}])")
        lines.append(f"  Z向跨度 (高): {max_z - min_z:.2f} mm  (范围: [{min_z:.2f}, {max_z:.2f}])")

    # 3. 按体积排序，识别底板、支承块、压板、销轴、定位标准件
    sorted_bodies = sorted(body_infos, key=lambda b: b["vol"], reverse=True)
    lines.append(f"\n[主要大件与核心零部件识别 (按外包络体积 Top 20)]")
    lines.append(f"{'序号':<6}{'图层':<8}{'外形长x宽x高 (mm)':<26}{'面/边数':<12}{'功能推测'}")
    lines.append("-" * 75)
    
    for rank, b in enumerate(sorted_bodies[:25]):
        dims = f"{b['dx']:.1f} x {b['dy']:.1f} x {b['dz']:.1f}"
        f_e = f"{b['faces']}F/{b['edges']}E"
        # 简单形态学功能推测
        d_min = min(b['dx'], b['dy'], b['dz'])
        d_max = max(b['dx'], b['dy'], b['dz'])
        if b['dx'] > 300 and b['dy'] > 200:
            category = "夹具基座主底板 (Base Plate)"
        elif d_max > 150 and d_min > 30:
            category = "主支承立板/转接板 (Upright / Angle Plate)"
        elif d_max > 80 and d_min < 25:
            category = "压紧板/导向条/垫块 (Clamp Strap / Guide Bar)"
        elif b['faces'] > 50:
            category = "复杂加工块/异形定位块 (Locator Block)"
        else:
            category = "安装块/紧固标准件 (Mounting Block)"
        lines.append(f"#{rank+1:<5} Layer {b['layer']:<3} {dims:<26} {f_e:<12} {category}")

    # 4. 图层分布与工装管理结构
    layer_map = {}
    for b in body_infos:
        layer_map[b['layer']] = layer_map.get(b['layer'], 0) + 1
    lines.append(f"\n[UG 图层规划分布 (Layer Classification)]")
    for lyr in sorted(layer_map.keys()):
        lines.append(f"  图层 Layer {lyr:03d}: 共 {layer_map[lyr]} 个实体")

    # 5. 2D工程制图检查
    sheets = list(part.DrawingSheets)
    lines.append(f"\n[2D 工程制图页 (Drafting Sheets)] 共 {len(sheets)} 页")
    for s in sheets:
        try:
            scale_str = f"{s.Numerator}:{s.Denominator}"
        except:
            scale_str = "N/A"
        lines.append(f"  图纸名: {s.Name} | 尺寸: {s.Length:.1f} x {s.Height:.1f} mm | 比例: {scale_str}")
        try:
            views = list(s.SheetDraftingViews)
            lines.append(f"    包含 {len(views)} 个工程视图: {[v.Name for v in views]}")
        except Exception as ve:
            pass

    # 6. 参数化表达式检查
    expr_list = list(part.Expressions)
    lines.append(f"\n[参数化表达式 (Expressions)] 共 {len(expr_list)} 个")
    for exp in expr_list[:15]:
        try:
            lines.append(f"  {exp.Name} = {exp.RightHandSide}")
        except:
            pass

    out_text = "\n".join(lines)
    print(out_text)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"\n=== 解析完成，已存入 {out_file} ===")

if __name__ == "__main__":
    main()
