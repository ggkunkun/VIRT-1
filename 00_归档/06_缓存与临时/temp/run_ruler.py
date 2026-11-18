import sys, json, importlib.util
sys.path.insert(0, r"D:\Virtu模型\scripts")
spec = importlib.util.spec_from_file_location("proctor", r"D:\Virtu模型\scripts\closed_impeller_proctor.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
p = {"D2_mm":220.0,"N_rpm":40300.5,"Z_blades":12,"beta2b_deg":25.0,"b2_mm":19.8,"D1t_mm":174.32,"D1h_mm":93.14,
     "axial_length_mm":82.5,"shroud_thickness_mm":2.0,"blade_thickness_mm":1.8,"hub_disk_thickness_mm":2.0,
     "bore_diameter_mm":22.0,"fillet_root_mm":1.2,"eta_total":0.85,"claimed_pressure_ratio":4.01,
     "claimed_tip_speed_m_s":464.23,"claimed_FOS":1.84}
vals, viol, adv = m.ruler(p)
print(json.dumps({"values":vals,"violations":viol,"advisory":adv}, ensure_ascii=False, indent=1))
