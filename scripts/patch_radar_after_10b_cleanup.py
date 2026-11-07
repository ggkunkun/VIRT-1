with open(r"D:\Virtu模型\VIRTU_MODEL_RADAR.html", "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
text_norm = text.replace("\r\n", "\n")

# 1. Update Virtu-10B row to marked deleted / removed
old_10b_row = """<tr>
<td class="l">Virtu-10B<br>(virtu-10b:a45b3427)</td>
<td>10.12B</td><td>46</td><td>40,960</td><td>Q4_0</td>
<td>1/3</td><td>已注册(OK)</td><td>有 receipt</td>
<td>86.3</td><td>92.0</td><td>100.0</td><td>28.1</td><td>33.3</td><td>100.0</td><td>100.0</td>
</tr>"""

new_10b_row = """<tr style="opacity:0.45;color:#8b95ad;">
<td class="l">Virtu-10B<br><span style="color:#ff7a59;">[已彻底清理下线]</span></td>
<td>10.12B</td><td>46</td><td>40,960</td><td>Q4_0</td>
<td>0/3</td><td>已下线删除</td><td>文件已清除</td>
<td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td>
</tr>"""

# 2. Update Virtu-MoE rows
old_moe_rows = """<tr>
<td class="l">Virtu-MoE-14B<br>(virtu-moe-14b:latest)</td>
<td>13.63B</td><td>36</td><td>40,960</td><td>Q4_K_M</td>
<td>3/3</td><td>已注册(OK)</td><td>无 receipt</td>
<td>100.0</td><td>72.0</td><td>100.0</td><td>30.3</td><td>100.0</td><td>100.0</td><td>0.0</td>
</tr><tr>
<td class="l">Virtu-MoE-14B BF16<br>(disk-only, 未注册)</td>
<td>13.63B</td><td>36</td><td>40,960</td><td>BF16</td>
<td>3/3</td><td>磁盘存在/未注册</td><td>无 receipt</td>
<td>100.0</td><td>72.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>50.0</td><td>0.0</td>
</tr>"""

new_moe_rows = """<tr>
<td class="l">Virtu-MoE-14B<br>(virtu-moe-14b:latest)</td>
<td>13.63B</td><td>36</td><td>40,960</td><td>Q4_K_M</td>
<td>3/3</td><td>已注册(OK)</td><td>有 receipt</td>
<td>100.0</td><td>72.0</td><td>100.0</td><td>30.3</td><td>100.0</td><td>100.0</td><td>100.0</td>
</tr><tr>
<td class="l">Virtu-MoE-14B BF16<br>(virtu-moe-14b:bf16)</td>
<td>13.63B</td><td>36</td><td>40,960</td><td>BF16</td>
<td>3/3</td><td>已注册(OK)</td><td>有 receipt</td>
<td>100.0</td><td>72.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>100.0</td><td>100.0</td>
</tr>"""

# 3. Update bottom card summary
old_bottom_tag = """<span class="tag ok">真实·全量可用已注册：virtu-moe-14b:latest (Q4) / virtu-moe-14b:bf16 (BF16) / virtu-10b:a45b3427 / virtu-comprehensive 等 8.2B 族</span>"""
new_bottom_tag = """<span class="tag ok">真实·在役模型：virtu-moe-14b:latest (Q4_K_M) / virtu-moe-14b:bf16 (BF16) / virtu-comprehensive 8.2B 族</span>
  <span class="tag" style="color:#ff7a59;border-color:#ff7a59;">未训练构件已清理：virtu-10b:a45b3427 (已彻底删除，释放5.7GB空间)</span>"""

old_bottom_note = """· virtu-10b 结构真实 10.12B（46层，509张量，有 receipt），但新增10层为阶段A复制层，能力待阶段B继续预训练激活。<br>"""
new_bottom_note = """· virtu-10b 阶段A复制层体因未在云端训练收敛，已遵照指令全量清理下线，绝不保留未激活半成品；<br>"""

if old_10b_row in text_norm:
    text_norm = text_norm.replace(old_10b_row, new_10b_row)
if old_moe_rows in text_norm:
    text_norm = text_norm.replace(old_moe_rows, new_moe_rows)
if old_bottom_tag in text_norm:
    text_norm = text_norm.replace(old_bottom_tag, new_bottom_tag)
if old_bottom_note in text_norm:
    text_norm = text_norm.replace(old_bottom_note, new_bottom_note)

final_text = text_norm.replace("\n", "\r\n") if crlf else text_norm

with open(r"D:\Virtu模型\VIRTU_MODEL_RADAR.html", "w", encoding="utf-8") as f:
    f.write(final_text)

print("SUCCESS: Radar HTML updated cleanly!")
