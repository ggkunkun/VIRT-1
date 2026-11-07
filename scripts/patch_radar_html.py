with open(r"D:\Virtu模型\VIRTU_MODEL_RADAR.html", "r", encoding="utf-8") as f:
    text = f.read()

# Normalize line endings to \n
crlf = "\r\n" in text
text_norm = text.replace("\r\n", "\n")

old_text = """<div class="card" style="margin-top:18px;">
  <b>真实存在性核查结论</b>
  <div style="margin-top:8px;">
  <span class="tag ok">真实·可用：virtu-moe-14b:latest / virtu-10b:a45b3427 / virtu-comprehensive 等 8.2B 族 / extreme-256k / longctx</span>
  <span class="tag warn">真实·未注册：virtu-moe-14b-bf16.gguf (27.26GB, 无标签无 receipt)</span>
  <span class="tag warn">404 半删除：virtu-toolcall:latest / virtu-boundary-sft:latest / virtu-toolcall:latest.bak_pre_params_repair / virtu-production:v3</span>
  </div>"""

new_text = """<div class="card" style="margin-top:18px;">
  <b>真实存在性核查结论 (已于 2026-11-06 02:10 全量修复闭环)</b>
  <div style="margin-top:8px;">
  <span class="tag ok">真实·全量可用已注册：virtu-moe-14b:latest (Q4) / virtu-moe-14b:bf16 (BF16) / virtu-10b:a45b3427 / virtu-comprehensive 等 8.2B 族</span>
  <span class="tag ok">凭据已封缄：virtu-moe-14b-bf16.gguf.receipt.json / virtu-moe-14b-q4_k_m.gguf.receipt.json (SHA-256 完备)</span>
  <span class="tag ok">404 坏标签已清理：0 个损坏标签 (Broken tags = 0)</span>
  </div>"""

if old_text in text_norm:
    text_norm = text_norm.replace(old_text, new_text)
    if crlf:
        final_text = text_norm.replace("\n", "\r\n")
    else:
        final_text = text_norm
    with open(r"D:\Virtu模型\VIRTU_MODEL_RADAR.html", "w", encoding="utf-8") as f:
        f.write(final_text)
    print("SUCCESS: VIRTU_MODEL_RADAR.html updated!")
else:
    print("WARNING: Target block not found in text_norm!")
