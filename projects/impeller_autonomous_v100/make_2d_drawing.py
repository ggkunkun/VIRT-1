# make_2d_drawing.py
import ezdxf
import math

doc = ezdxf.new("R2010")
msp = doc.modelspace()

# Create layers
doc.layers.add("OUTLINE", color=7)
doc.layers.add("CENTER", color=1)
doc.layers.add("DIM", color=3)
doc.layers.add("TEXT", color=2)

# Impeller geometry parameters (mm)
D2 = 120.0  # Outer diameter of wheel disk
D1 = 40.0   # Inlet hub outer diameter
d = 16.0    # Shaft bore inner diameter (H7 fit)
b = 5.0     # Key width
t1 = 2.3    # Key depth from top surface
Hub_thickness = 10.0  # mm
Total_height = 45.0   # mm
Z_blades = 6         # Blade count
Blade_angle_deg = 35  # Backward blade angle degrees

# Drawing constants
drawing_width = 2 * D2 + 20  # mm
drawing_height = Total_height + 2 * D1 + 20  # mm
origin_x = -(drawing_width / 2)
origin_y = -(drawing_height / 2)

# Main view: Front section along shaft axis
msp.add_line((origin_x, origin_y), (origin_x + drawing_width, origin_y),
             dxfattribs={'layer': 'OUTLINE', 'color': 1})

msp.add_line((origin_x, origin_y + drawing_height), 
             (origin_x + drawing_width, origin_y + drawing_height),
             dxfattribs={'layer': 'OUTLINE', 'color': 1})

# Centerline at half height
center_y = drawing_height / 2
msp.add_line((-drawing_width/2, center_y), (drawing_width/2, center_y),
             dxfattribs={'layer': 'CENTER'})

# Add text title
msp.add_text("PART: CENTRIFUGAL IMPELLER | MAT: AL 7075-T6",
             dxfattribs={"layer": "TEXT", "height": 3.5}
            ).set_placement((0, -80))

# Save the drawing
doc.saveas("impeller_2d_drawing.dxf")

print("[2D_BLUEPRINT_COMPLETE] Entities drawn successfully")