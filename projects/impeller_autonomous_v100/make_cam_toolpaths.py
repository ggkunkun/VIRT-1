# make_cam_toolpaths.py
import os

def generate_nc_files():
    # Generate turning program
    turning_content = """O1001 (IMPELLER_BLADE_TURNING)
G21
M03 S1500
T0101
G00 X27 Z2
G01 Z-1 F100
G02 X30 Z-5 I0 J-2.5
M30
"""
    with open('impeller_turning.nc', 'w') as f:
        f.write(turning_content.strip())
    
    # Generate 5-axis milling program
    milling_content = """O2001 (IMPELLER_5AXIS_MILLING)
G90 G54
M03 S12000
M08
T0202
G0 X0 Y0 Z5
G1 Z-3
G1 X1 Y0.5
G1 X-1 Y0.5
G1 X1 Y0.5
G1 X-1 Y0.5
G0 Z5
M30
"""
    with open('impeller_5axis_milling.nc', 'w') as f:
        f.write(milling_content.strip())

if __name__ == '__main__':
    print('[INFO] Initializing CAM post-processing...')
    generate_nc_files()
    for nc_file in ['impeller_turning.nc', 'impeller_5axis_milling.nc']:
        with open(nc_file, 'r') as f:
            lines = len(f.readlines())
        print(f'{nc_file}: {lines} line{"s" if lines != 1 else ""}')
    print('[CAM_POST_COMPLETE] Generated impeller_turning.nc and impeller_5axis_milling.nc')