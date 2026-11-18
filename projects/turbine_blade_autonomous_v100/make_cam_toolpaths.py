import os

def generate_nc_files():
    # 第一程: 圣诞树榫齿线切 NC 字符串化
    nc_content = [
        "(O3001) ; CHRISTMAS_TREE_FIRTREE_ROOT_CUTTING_PROGRAM",
        "O3001",
        "G90 G54",
        "; 初始化原点至工件装夹面基准...",
        "; 首层圣诞树榫齿根部切入 (Z+6mm 至 Z-12mm 深度盲槽)",
        "G01 Z-12 F120",
        "X-75 Y-25",
        "G02 I-5 J0 F120",
        "G01 Z-18",
        "X-65 Y-20",
        "G03 I-5 J0 F120",
        "M30"
    ]
    
    with open("turbine_firtree_root.nc", 'w') as f:
        for line in nc_content:
            f.write(line + '\n')
    print(f"[INFO] Wrote turbine_firtree_root.nc lines: {len(nc_content)}")
    
    # 第二程: 五轴异构曲面叶型精铣 NC 字符串化
    nc_content = [
        "(O3002) ; FIVE_AXIS_AIRFOIL_SURFACE_MACHINING_PROGRAM",
        "O3002",
        "G90 G54",
        "; 主轴正转启动与冷却液开启",
        "M03 S15000",
        "M08",
        "; 刀具选择为 T0303 球头铣刀",
        "T0303",
        "; 进入五轴联动空间曲面铣削循环",
        "; X,Y,Z 轴按翼型法向量切向进给; A,C 转台实现刀尖点位姿态回转同步",
        "# START OF ROBUST_SURFACE_MILLING_SUBROUTINE",
        "G17 G51.7 P0 Q0 R0 S0 T0;",
        "G1 X-55 Y-20 Z-5 A-15 C-5 F120;",
        "G1 X-45 Y-15 Z-4.5 A-20 C-7;",
        "G1 X-35 Y-10 Z-4 A-25 C-9;",
        "G1 X-25 Y-5 Z-3.5 A-30 C-11;",
        "G1 X-15 Y-0 Z-3 A-35 C-13;",
        "G1 X-5 Y+5 Z-2.5 A-40 C-15;",
        "G1 X+5 Y+10 Z-2 A-45 C-17;",
        "G1 X+15 Y+15 Z-1.5 A-50 C-19;",
        "G1 X+25 Y+20 Z-1 A-55 C-21;",
        "G1 X+35 Y+25 Z-0.5 A-60 C-23;",
        "G1 X+45 Y+30 Z-0 A-65 C-25;",
        "G1 X+55 Y+35 Z+0.5 A-70 C-27;",
        "G1 X+65 Y+40 Z+1 A-75 C-29;",
        "G1 X+75 Y+45 Z+1.5 A-80 C-31;",
        "G1 X+85 Y+50 Z+2 A-85 C-33;",
        "G1 X+95 Y+55 Z+2.5 A-90 C-35;",
        "M30"
    ]
    
    with open("turbine_5axis_airfoil.nc", 'w') as f:
        for line in nc_content:
            f.write(line + '\n')
    print(f"[INFO] Wrote turbine_5axis_airfoil.nc lines: {len(nc_content)}")
    
    # 终极校准与程序结束
    print("[CAM_POST_COMPLETE] Generated turbine_firtree_root.nc and turbine_5axis_airfoil.nc")

if __name__ == "__main__":
    generate_nc_files()