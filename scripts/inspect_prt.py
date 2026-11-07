# -*- coding: utf-8 -*-
import sys
import NXOpen
import NXOpen.UF

def main():
    the_session = NXOpen.Session.GetSession()
    the_uf_session = NXOpen.UF.UFSession.GetUFSession()
    
    out_file = r"D:\Virtu模型\runs\inspect_prt_result.txt"
    prt_path = r"E:\迅雷下载\分享数模20-77套UG夹具图档\77 (1).prt"
    
    lines = []
    lines.append(f"Opening part: {prt_path} ...")
    
    try:
        part, load_status = the_session.Parts.OpenBaseDisplay(prt_path)
    except Exception as e:
        lines.append(f"Error opening part: {e}")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return
        
    lines.append(f"Part opened successfully: {part.FullPath}")
    lines.append(f"Part Name: {part.Leaf}")
    lines.append(f"Part Units: {'Millimeters' if part.PartUnits == NXOpen.BasePart.Units.Millimeters else 'Inches'}")
    
    # 1. Check if assembly
    root_comp = part.ComponentAssembly.RootComponent
    if root_comp is not None:
        children = root_comp.GetChildren()
        lines.append(f"\n=== ASSEMBLY DETECTED ===")
        lines.append(f"Root Component: {root_comp.Name}")
        lines.append(f"Total Direct Children Components: {len(children)}")
        for idx, child in enumerate(children[:30]):
            try:
                lines.append(f"  [{idx+1}] Name: {child.Name} | Prototype: {child.Prototype.Leaf if child.Prototype else 'None'}")
            except Exception as ce:
                lines.append(f"  [{idx+1}] Child: {child.Name} (err: {ce})")
    else:
        lines.append("\n=== PIECE PART (Multi-body part file) ===")
        
    # 2. Total Bodies & Overall Bounding Box
    body_list = list(part.Bodies)
    lines.append(f"\n=== SOLID BODIES COUNT: {len(body_list)} ===")
    
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')
    
    body_summaries = []
    for idx, body in enumerate(body_list):
        try:
            bbox = the_uf_session.Modl.AskBoundingBoxExact(body.Tag, NXOpen.Tag.Null)
            min_x = min(min_x, bbox[0])
            min_y = min(min_y, bbox[1])
            min_z = min(min_z, bbox[2])
            max_x = max(max_x, bbox[3])
            max_y = max(max_y, bbox[4])
            max_z = max(max_z, bbox[5])
            
            dx = bbox[3] - bbox[0]
            dy = bbox[4] - bbox[1]
            dz = bbox[5] - bbox[2]
            faces = body.GetFaces()
            edges = body.GetEdges()
            body_summaries.append((idx+1, len(faces), len(edges), dx, dy, dz, body.Layer, body.Tag))
        except Exception as e:
            pass
            
    if min_x != float('inf'):
        lines.append(f"\n=== OVERALL FIXTURE BOUNDING BOX ===")
        lines.append(f"X range: [{min_x:.2f}, {max_x:.2f}] mm -> Total Length X = {max_x - min_x:.2f} mm")
        lines.append(f"Y range: [{min_y:.2f}, {max_y:.2f}] mm -> Total Width  Y = {max_y - min_y:.2f} mm")
        lines.append(f"Z range: [{min_z:.2f}, {max_z:.2f}] mm -> Total Height Z = {max_z - min_z:.2f} mm")

    lines.append(f"\nTop 20 Largest Solid Components (by bounding box volume):")
    sorted_bodies = sorted(body_summaries, key=lambda b: b[3]*b[4]*b[5], reverse=True)
    for rank, (b_idx, n_faces, n_edges, dx, dy, dz, layer, tag) in enumerate(sorted_bodies[:20]):
        vol_approx = (dx * dy * dz) / 1000.0 # cm^3
        lines.append(f"  #{rank+1:02d} Body_{b_idx:03d} (Tag={tag}, Layer={layer:02d}): Size = {dx:.1f} x {dy:.1f} x {dz:.1f} mm | Faces={n_faces} Edges={n_edges} | BBox Vol={vol_approx:.1f} cm3")

    # 3. Features Inspection
    feat_list = list(part.Features)
    lines.append(f"\n=== FEATURES COUNT: {len(feat_list)} ===")
    feat_types = {}
    for feat in feat_list:
        try:
            ft = feat.GetFeatureType()
        except:
            try:
                ft = feat.FeatureType
            except:
                ft = "DumbSolid/Imported"
        feat_types[ft] = feat_types.get(ft, 0) + 1
    lines.append(f"Feature Types Breakdown: {feat_types}")

    # 4. Layer Breakdown
    layer_counts = {}
    for b in body_list:
        layer_counts[b.Layer] = layer_counts.get(b.Layer, 0) + 1
    lines.append("\nLayer Distribution (Layer ID -> Body Count):")
    for lyr in sorted(layer_counts.keys()):
        lines.append(f"  Layer {lyr:03d}: {layer_counts[lyr]} bodies")

    # 5. Drawing Sheets
    sheets = list(part.DrawingSheets)
    lines.append(f"\n=== DRAWING SHEETS (2D Drafting): {len(sheets)} ===")
    for s in sheets:
        lines.append(f"  Sheet: {s.Name} | {s.Length:.1f} x {s.Height:.1f} mm (Scale: {s.Scale})")

    # 6. Expressions
    expr_list = list(part.Expressions)
    lines.append(f"\n=== EXPRESSIONS: {len(expr_list)} ===")
    for exp in expr_list[:15]:
        try:
            lines.append(f"  {exp.Name} = {exp.RightHandSide}")
        except:
            pass

    out_text = "\n".join(lines)
    print(out_text)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(out_text)
    print(f"\nSaved inspection to {out_file}")

if __name__ == "__main__":
    main()
