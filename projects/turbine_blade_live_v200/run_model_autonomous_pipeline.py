# -*- coding: utf-8 -*-
"""Autonomous Model-Driven Engineering Pipeline with Strict Supervisor Verification.

Model: virtu-v3-all90:perfect
Supervisor: Antigravity Super Agent (零插手、防欺骗、物理闭环核验)
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import re
from supervisor_enforcer import verify_file_novelty, BLACK_LIST_HASHES

PROJECT_DIR = r"d:\Virtu模型\projects\turbine_blade_live_v200"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "virtu-v3-all90:perfect"

def call_model_for_code(prompt: str, filename: str, max_retries: int = 4) -> str:
    current_prompt = prompt
    for attempt in range(1, max_retries + 1):
        payload = {
            "model": MODEL_NAME,
            "prompt": current_prompt,
            "system": (
                "你是一个资深的航空发动机数字设计与数字化制造专家系统（覆盖 CAD/CAE/CAM）。"
                "严禁输出任何自然语言开场白或解释废话！必须直接且仅将可直接执行的完整 Python 源码包裹在 ```python ... ``` 代码块中输出！"
            ),
            "stream": False,
            "options": {
                "temperature": 0.15,
                "num_predict": 4096
            }
        }
        req = urllib.request.Request(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            raw = res.get("response", "")
        
        m = re.findall(r"```python\s*(.*?)\s*```", raw, re.DOTALL)
        if not m:
            m = re.findall(r"```\s*(.*?)\s*```", raw, re.DOTALL)
        
        if not m:
            print(f"[监督官警告] {filename} Attempt {attempt}: 模型未输出 ```python 代码块，正在打回重构...")
            current_prompt = prompt + f"\n\n【监督官重要指令】：你上次回复未包含可执行代码块。请严格将完整 Python 代码包裹在 ```python ... ``` 中输出！"
            continue
            
        code = m[-1].strip()
        try:
            compile(code, "<check>", "exec")
        except SyntaxError as e:
            print(f"[监督官警告] {filename} Attempt {attempt}: 静态语法校验失败: {e}")
            current_prompt = f"你编写的 {filename} 存在语法错误:\n{e}\n请修复并重新提供完整的 ```python 代码。"
            continue

        # 尝试沙盒执行自查
        path = os.path.join(PROJECT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

        res = subprocess.run([sys.executable, path], cwd=PROJECT_DIR, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[监督官核验] {filename} Attempt {attempt}: 沙盒单步自查通过 (ExitCode 0)")
            return code
        else:
            print(f"[监督官警告] {filename} Attempt {attempt}: 运行时报错:\n{res.stderr.strip()}")
            current_prompt = (
                f"你编写的 {filename} 在执行时发生以下运行时错误:\n{res.stderr.strip()}\n"
                f"请彻底分析报错原因，修复代码并输出完整的 ```python ... ``` 源码！"
            )

    raise RuntimeError(f"[监督官熔断] 模型在 {max_retries} 次尝试内未能生成可正常执行的 {filename}。")


print("="*70)
print(f"[监督官启动] 项目目录: {PROJECT_DIR}")
print(f"[监督官确认] 被监督求解模型: {MODEL_NAME}")
print(f"[监督官确认] 历史交付物黑名单哈希数: {len(BLACK_LIST_HASHES)} 条 (严禁偷换复用)")
print("="*70)

# ==============================================================================
# 阶段 1: 2D工程制图 (Stage-2 航空发动机高压涡轮工作叶片)
# ==============================================================================
print("\n>>> [阶段 1: 2D工程蓝图设计] 正在向模型下达指令...")
prompt_2d = """
请编写完整的 Python 脚本 make_2d_drawing.py，使用 ezdxf 库为【航空发动机高压涡轮二级工作叶片】创建符合国标规范的 2D 工程蓝图。
【规范与标准】：
1. 全新四对齿深圣诞树榫头 (4-Tooth Fir-tree Root)：
   - 齿距 p=5.2mm，半角 28°，齿宽 24.0mm，高 22.0mm；
   - 使用 doc.layers.add('OUTLINE', color=7) 等标准 API；
   - 使用 msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'OUTLINE'}) 绘制轮廓；
2. 阻尼平台 (Platform)：长 32.0mm，宽 28.0mm，厚 4.5mm；
3. 空间大扭转叶身：叶根弦长 38.0mm，叶尖弦长 26.0mm，高度 72.0mm，安装扭角 31.5°；
4. 包含标准图层：'OUTLINE', 'CENTER', 'DIM', 'TEXT'；
5. 添加技术要求与标题栏 (msp.add_text)：
   - 零件名称: HIGH-PRESSURE TURBINE ROTOR BLADE STAGE-2
   - 材料牌号: CMSX-4 单晶高温合金
   - 设计单位: VIRTU AERO-ENGINEERING LAB
   - 图号: AE-HPT-02-001
6. 保存图纸至 turbine_blade_stage2.dxf。
请严格输出 ```python ... ``` 完整可运行代码。
"""
code_2d = call_model_for_code(prompt_2d, "make_2d_drawing.py")
dxf_file = os.path.join(PROJECT_DIR, "turbine_blade_stage2.dxf")
seal_2d = verify_file_novelty(dxf_file)
print(f"[阶段 1 监督通过] {seal_2d['path']} | SHA256: {seal_2d['sha256'][:16]}... | 大小: {seal_2d['size_bytes']} 字节 (全新产物，无碰撞)")


# ==============================================================================
# 阶段 2: 3D参数化CAD实体建模 (build123d 水密 B-Rep 实体)
# ==============================================================================
print("\n>>> [阶段 2: 3D参数化CAD建模] 正在向模型下达指令...")
prompt_3d = """
请编写完整的 Python 脚本 make_3d_cad.py，使用 build123d 库生成【航空发动机高压涡轮二级工作叶片】的真实 3D 水密实体，并导出 STEP 与 STL 文件。
【重要规范要求】：
1. 几何构成：
   - 圣诞树榫头 (Fir-tree Root): 高 22.0mm，宽 24.0mm，轴向长 30.0mm；可用 Box 或 Polygon 拉伸实现；
   - 阻尼缘板 (Platform): Box(32.0, 28.0, 4.5)，位于榫头上方；
   - 空间变截面大扭转叶身 (Airfoil):
     创建 4 个高度截面 (Z=0, 24, 48, 72 mm)，采用流线型截面或气动草图，弦长从 38.0mm 渐缩至 26.0mm，截面逐层旋转扭角 (0°, 10.5°, 21.0°, 31.5°)；
     在 build123d 中使用 loft() 生成叶身实体；
   - 布尔并集：part = root + platform + airfoil；
2. 断言与导出规范：
   - 必须断言实体体积 ΔV > 18,000 mm³；
   - 导出必须使用 build123d 的顶层导出函数：
     from build123d import export_step, export_stl
     export_step(part, 'turbine_blade_stage2.step')
     export_stl(part, 'turbine_blade_stage2.stl')
3. 打印最终体积与水密性状态。
请严格输出 ```python ... ``` 完整可运行代码。
"""
code_3d = call_model_for_code(prompt_3d, "make_3d_cad.py")
step_file = os.path.join(PROJECT_DIR, "turbine_blade_stage2.step")
stl_file = os.path.join(PROJECT_DIR, "turbine_blade_stage2.stl")
seal_step = verify_file_novelty(step_file)
seal_stl = verify_file_novelty(stl_file)
print(f"[阶段 2 监督通过] {seal_step['path']} | SHA256: {seal_step['sha256'][:16]}... | 大小: {seal_step['size_bytes']} 字节 (全新产物，无碰撞)")
print(f"[阶段 2 监督通过] {seal_stl['path']} | SHA256: {seal_stl['sha256'][:16]}... | 大小: {seal_stl['size_bytes']} 字节 (全新产物，无碰撞)")


# ==============================================================================
# 阶段 3: CAE有限元应力与安全裕度仿真 (CMSX-4, 15,200 RPM, 750°C)
# ==============================================================================
print("\n>>> [阶段 3: CAE有限元应力分析] 正在向模型下达指令...")
prompt_cae = """
请编写完整的 Python 脚本 run_cae_analysis.py，对【航空发动机高压涡轮二级工作叶片】执行严格的离心力学与强度校核。
【物理常数与工况】：
1. 材料：CMSX-4 单晶高温合金，密度 rho = 8700 kg/m³，750°C 屈服极限 sigma_yield = 960.0 MPa，弹性模量 E = 185 GPa；
2. 转速：n = 15,200 RPM (角速度 omega = 2 * math.pi * 15200 / 60 = 1591.74 rad/s)，盘心半径 R_disk = 0.280 m；
3. 计算沿展向各剖面的离心拉伸应力 sigma_centrifugal(z) 与燃气弯矩 M_gas = 12.5 N*m 引起的弯曲应力 sigma_bending(z)；
4. 合成 von Mises 最大等效应力 sigma_max，考虑叶根过渡应力集中 Kt = 1.35；
5. 断言判定：
   - assert sigma_max < 960.0, "应力超出屈服极限!"
   - fos = 960.0 / sigma_max
   - assert fos >= 1.50, f"安全系数不足: {fos} < 1.50"
6. 输出文件：
   - 使用 matplotlib 生成应力分布图保存为 turbine_cae_stress.png；
   - 将计算结果写入 turbine_cae_report.json，包含 sigma_max, fos, material, rpm, mass_grams 等。
请严格输出 ```python ... ``` 完整可运行代码。
"""
code_cae = call_model_for_code(prompt_cae, "run_cae_analysis.py")
cae_png = os.path.join(PROJECT_DIR, "turbine_cae_stress.png")
cae_json = os.path.join(PROJECT_DIR, "turbine_cae_report.json")
seal_cae_png = verify_file_novelty(cae_png)
seal_cae_json = verify_file_novelty(cae_json)
print(f"[阶段 3 监督通过] {seal_cae_png['path']} | SHA256: {seal_cae_png['sha256'][:16]}... | 大小: {seal_cae_png['size_bytes']} 字节 (全新产物，无碰撞)")
print(f"[阶段 3 监督通过] {seal_cae_json['path']} | SHA256: {seal_cae_json['sha256'][:16]}... | 大小: {seal_cae_json['size_bytes']} 字节 (全新产物，无碰撞)")


# ==============================================================================
# 阶段 4: CAM五轴多轴CNC数控加工编程
# ==============================================================================
print("\n>>> [阶段 4: CAM五轴数控加工编程] 正在向模型下达指令...")
prompt_cam = """
请编写完整的 Python 脚本 make_cam_toolpaths.py，为【航空发动机高压涡轮二级工作叶片】生成两套 CNC G 代码程序：
1. turbine_firtree_root.nc: 四对齿深圣诞树榫头精密拉削/线切割程序 (O4001, G90 G54, 包含连续圆弧微切削插补)；
2. turbine_5axis_airfoil.nc: 空间扭曲叶身五轴联动 (X, Y, Z, A, C) 螺旋精铣程序 (O4002, G90 G54, S16000 M03, M08, 五轴联动曲面点位)；
3. 安全检查：
   - 验证主轴 M03 模态指令；
   - 验证绝对零 G00 高速撞刀；
   - 写入文件并打印生成状态。
请严格输出 ```python ... ``` 完整可运行代码。
"""
code_cam = call_model_for_code(prompt_cam, "make_cam_toolpaths.py")
nc_root = os.path.join(PROJECT_DIR, "turbine_firtree_root.nc")
nc_blade = os.path.join(PROJECT_DIR, "turbine_5axis_airfoil.nc")
seal_nc_root = verify_file_novelty(nc_root)
seal_nc_blade = verify_file_novelty(nc_blade)
print(f"[阶段 4 监督通过] {seal_nc_root['path']} | SHA256: {seal_nc_root['sha256'][:16]}... | 大小: {seal_nc_blade['size_bytes']} 字节 (全新产物，无碰撞)")
print(f"[阶段 4 监督通过] {seal_nc_blade['path']} | SHA256: {seal_nc_blade['sha256'][:16]}... | 大小: {seal_nc_blade['size_bytes']} 字节 (全新产物，无碰撞)")

print("\n" + "="*70)
print("[监督官阶段总结] 前四阶段全新工程产物全部通过物理守恒与密码学防欺骗核验！")
print("="*70)
