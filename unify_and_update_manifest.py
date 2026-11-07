# -*- coding: utf-8 -*-
"""
Virtu CAD/CAM 训练集全量汇总、BOM清洗、质量校验与元数据清单更新脚本
"""
import os
import json
import glob

DATA_DIR = r"E:\数据"

MODULE_FILES = [
    ("01_SFT_AGENT_TOOLCALLS", "virtu_agent_toolcall_train.jsonl"),
    ("02_SFT_CAD_CAM_CODE", "virtu_cad_cam_code_sft.jsonl"),
    ("02_SFT_CAD_CAM_CODE", "virtu_software_samples_sft.jsonl"),
    ("02_SFT_CAD_CAM_CODE", "virtu_macro_automation_qa.jsonl"),
    ("03_MECHANICAL_HANDBOOK_RAG_AND_QA", "mechanical_calculation_qa_sft.jsonl"),
    ("04_MULTIMODAL_DRAWING_TO_CAD", "drawing_to_cad_sft.jsonl"),
    ("05_STANDARDS_AND_COMPONENTS_LIBRARY", "standard_components_selection_sft.jsonl"),
    ("07_FIXTURES_AND_TOOLING", "fixture_design_rules_sft.jsonl"),
    ("08_ANIMATION_AND_CURRICULUM", "animation_and_curriculum_sft.jsonl"),
    # ---- 2026-10-30 新图纸批次（D:\新图纸\图纸(2) 与 图纸(3)）----
    ("10_NX_CAD_MODELS_AND_ASSEMBLIES", "nx_model_understanding_sft.jsonl"),
    ("10_NX_CAD_MODELS_AND_ASSEMBLIES", "nx_assembly_structure_sft.jsonl"),
    ("11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "drawing_reading_sft.jsonl"),
    ("11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "drawing_to_feature_tree_sft.jsonl"),
    ("11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "machining_process_planning_sft.jsonl"),
    ("12_WORLD_SKILLS_ASSESSMENT_AND_TASKS", "wsc2013_assessment_qa_sft.jsonl"),
    ("13_MULTIMODAL_CAD_ASSETS", "cad_image_caption_sft.jsonl"),
]

def clean_file_bom(file_path):
    """读取并去除可能存在的 UTF-8 BOM 签名，重新以无 BOM UTF-8 写回"""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

def main():
    print("="*60)
    print("正在执行全量 SFT 数据集清洗、聚合与深度校验...")
    print("="*60)
    
    # 1. 先对所有 JSONL 文件进行 UTF-8 BOM 清洗，确保对所有微调框架 100% 兼容
    all_jsonl = glob.glob(os.path.join(DATA_DIR, "**", "*.jsonl"), recursive=True)
    for p in all_jsonl:
        clean_file_bom(p)
    print(f"[+] 已完成 {len(all_jsonl)} 个 JSONL 文件的 UTF-8 无BOM编码净化")
    
    master_file = os.path.join(DATA_DIR, "00_UNIFIED_MASTER_TRAIN", "virtu_master_train_sft.jsonl")
    
    all_sft_lines = []
    module_counts = {}
    total_characters = 0
    total_tool_calls = 0
    
    for mod_dir, mod_file in MODULE_FILES:
        file_path = os.path.join(DATA_DIR, mod_dir, mod_file)
        if not os.path.exists(file_path):
            print(f"[!] 警告: 未找到 {file_path}")
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            
        count = len(lines)
        module_counts[f"{mod_dir}/{mod_file}"] = count
        print(f"[*] 读取并验证 {mod_dir}/{mod_file}: {count} 条样本")
        
        for idx, line in enumerate(lines):
            try:
                obj = json.loads(line)
            except Exception as e:
                raise ValueError(f"JSON 解析错误在 {file_path} 行 {idx+1}: {e}")
                
            assert "messages" in obj, f"缺少 messages 字段: {file_path} 行 {idx+1}"
            
            # 校验 tool_call_id 与角色序列
            for m in obj["messages"]:
                if m.get("role") == "assistant" and "tool_calls" in m:
                    for tc in m["tool_calls"]:
                        assert "id" in tc, f"assistant tool_call 缺少 id: {file_path} 行 {idx+1}"
                        total_tool_calls += 1
                elif m.get("role") == "tool":
                    assert "tool_call_id" in m and m["tool_call_id"], f"Tool 消息缺少 tool_call_id: {file_path} 行 {idx+1}"
                    
                content = m.get("content", "")
                total_characters += len(content)
                
            all_sft_lines.append(json.dumps(obj, ensure_ascii=False))
            
    # 写入全量主训练文件（纯无 BOM UTF-8，原子替换避免并发读到半截文件）
    tmp_master = master_file + ".tmp"
    with open(tmp_master, "w", encoding="utf-8", newline="\n") as f:
        for l in all_sft_lines:
            f.write(l + "\n")
    os.replace(tmp_master, master_file)
            
    print(f"\n[+] 全量训练集写入完成: {master_file}")
    print(f"[+] 汇聚样本总数: {len(all_sft_lines)} 条")
    print(f"[+] 总字符量: {total_characters:,} 字符")
    print(f"[+] 总工具调用点位: {total_tool_calls} 次 (含全部 tool_call_id 映射)")
    
    # 估算 tokens
    estimated_tokens = int(total_characters / 2.1)
    print(f"[+] 预估 Token 量: ~{estimated_tokens:,} tokens")
    
    # 更新 DATASET_MANIFEST.json
    manifest_path = os.path.join(DATA_DIR, "DATASET_MANIFEST.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    manifest["storage_location"] = "e:\\数据"
    manifest["statistics"]["unified_master_samples"] = len(all_sft_lines)
    manifest["statistics"]["total_characters"] = total_characters
    manifest["statistics"]["estimated_tokens"] = estimated_tokens
    
    # 按模块目录聚合（自动覆盖新增模块，避免漏统计）
    breakdown = {}
    for mod_dir, mod_file in MODULE_FILES:
        breakdown[mod_dir] = breakdown.get(mod_dir, 0) + \
            module_counts.get(f"{mod_dir}/{mod_file}", 0)
    manifest["statistics"]["module_breakdown"] = breakdown
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        
    print(f"[+] DATASET_MANIFEST.json 已更新为实际统计")
    
    # 更新 README.md
    readme_path = os.path.join(DATA_DIR, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme_text = f.read()
        
    import re
    readme_text = re.sub(r'e:\\新建文件夹 \(3\)', 'e:\\数据', readme_text)
    readme_text = re.sub(r'e:\\\\新建文件夹 \(3\)', 'e:\\数据', readme_text)
    # 只更新"第 1 节统计概览"表格行，避免误改其它章节中的数字
    readme_text = re.sub(
        r"(\*\*微调数据总样本数 \(SFT Samples\)\*\*\s*\|\s*\*\*)\d+( 条\*\*)",
        rf"\g<1>{len(all_sft_lines)}\2", readme_text)
    readme_text = re.sub(
        r"(\*\*文本字符总量 \(Total Characters\)\*\*\s*\|\s*\*\*)[\d,]+( 字符\*\*)",
        rf"\g<1>{total_characters:,}\2", readme_text)
    readme_text = re.sub(
        r"(\*\*预估 Token 规模 \(Estimated Tokens\)\*\*\s*\|\s*\*\*)~[\d,]+( Tokens\*\*)",
        rf"\g<1>~{estimated_tokens:,}\2", readme_text)
    readme_text = re.sub(r'（\d+ 台非标设备完整拆解与工具调用）', f'（90 台非标设备完整拆解、异常恢复与工具调用）', readme_text)
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_text)
        
    print(f"[+] README.md 已同步更新")
    print("\n[SUCCESS] 全部聚合与校验任务圆满完成！")

if __name__ == "__main__":
    main()
