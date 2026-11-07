import os
import math
import json

dims = [
    {
        'key': 'generation', 'name': '内容生成', 'en': 'Content Generation',
        'weight': 0.10, 'score_raw': 81.11, 'score_vision': 81.11, 'v2': 77.66,
        'easy': 94.44, 'med': 76.44, 'hard': 72.78, 'pass_rate': '63.3%',
        'delta': '+0.0',
        'comment': '纯文本强项，工艺规程与设计方案表达完整规范'
    },
    {
        'key': 'reasoning', 'name': '推理逻辑', 'en': 'Reasoning Logic',
        'weight': 0.17, 'score_raw': 79.67, 'score_vision': 79.67, 'v2': 83.34,
        'easy': 93.33, 'med': 81.27, 'hard': 55.16, 'pass_rate': '63.3%',
        'delta': '+0.0',
        'comment': '力学公式与厚壁筒Lamé弹性解推导扎实'
    },
    {
        'key': 'knowledge', 'name': '知识覆盖', 'en': 'Knowledge Coverage',
        'weight': 0.15, 'score_raw': 79.06, 'score_vision': 79.06, 'v2': 61.61,
        'easy': 88.89, 'med': 75.11, 'hard': 74.17, 'pass_rate': '60.0%',
        'delta': '+0.0',
        'comment': '材料与国家标准参数库掌握扎实'
    },
    {
        'key': 'generalization', 'name': '泛化适配', 'en': 'Generalization',
        'weight': 0.08, 'score_raw': 68.44, 'score_vision': 68.44, 'v2': 63.13,
        'easy': 60.28, 'med': 78.23, 'hard': 56.22, 'pass_rate': '40.0%',
        'delta': '+0.0',
        'comment': '非标工况通用设计自适应良好'
    },
    {
        'key': 'instruction', 'name': '指令遵循', 'en': 'Instruction Following',
        'weight': 0.14, 'score_raw': 61.84, 'score_vision': 61.84, 'v2': 81.95,
        'easy': 56.72, 'med': 68.48, 'hard': 52.94, 'pass_rate': '23.3%',
        'delta': '+0.0',
        'comment': '严格遵循单步指令，复杂排版格式待强化'
    },
    {
        'key': 'toolcall', 'name': '工具编排', 'en': 'Tool Orchestration',
        'weight': 0.18, 'score_raw': 53.89, 'score_vision': 72.50, 'v2': 73.33,
        'easy': 75.00, 'med': 68.00, 'hard': 88.89, 'pass_rate': '56.7%',
        'delta': '+18.6',
        'comment': '视觉提供图纸图元坐标与投影上下文，消除参数缺失，大幅提高 CAD 调用成功率'
    },
    {
        'key': 'boundary', 'name': '边界处理', 'en': 'Boundary & Safety',
        'weight': 0.12, 'score_raw': 47.67, 'score_vision': 47.67, 'v2': 62.45,
        'easy': 33.15, 'med': 50.89, 'hard': 61.39, 'pass_rate': '13.3%',
        'delta': '+0.0',
        'comment': '具备物理极限负荷拒绝能力，防过载机制初显'
    },
    {
        'key': 'multimodal', 'name': '多模态理解', 'en': 'Multimodal',
        'weight': 0.06, 'score_raw': 1.67, 'score_vision': 91.67, 'v2': 91.67,
        'easy': 95.00, 'med': 92.00, 'hard': 88.00, 'pass_rate': '91.7%',
        'delta': '+90.0',
        'comment': '✨ 视觉前端 (Qwen-VL / OCR) 补全图纸识别短板，尺寸标注、代号与表面粗糙度 91.7% 全通！'
    }
]

# Calculate weighted overall
raw_overall = sum(d['score_raw'] * d['weight'] for d in dims)
vision_direct_overall = sum((91.67 if d['key'] == 'multimodal' else d['score_raw']) * d['weight'] for d in dims)
vision_full_overall = sum(d['score_vision'] * d['weight'] for d in dims)

cx, cy = 350, 260
R = 170

def get_xy(val, idx):
    angle = -math.pi/2 + idx * (2 * math.pi / 8)
    r = (max(val, 0) / 100.0) * R
    x = cx + r * math.cos(angle)
    y = cy + r * math.sin(angle)
    return round(x, 1), round(y, 1)

def get_label_pos(idx, offset=35):
    angle = -math.pi/2 + idx * (2 * math.pi / 8)
    r = R + offset
    x = cx + r * math.cos(angle)
    y = cy + r * math.sin(angle)
    cos_val = math.cos(angle)
    if abs(cos_val) < 0.2:
        anchor = 'middle'
    elif cos_val > 0:
        anchor = 'start'
    else:
        anchor = 'end'
    return round(x, 1), round(y, 1), anchor

grid_polygons = []
grid_labels = []
for level in [20, 40, 60, 80, 100]:
    pts = [get_xy(level, i) for i in range(8)]
    pts_str = ' '.join(f'{x},{y}' for x, y in pts)
    grid_polygons.append(f'<polygon points="{pts_str}" fill="none" stroke="currentColor" stroke-opacity="0.15" stroke-width="1" />')
    grid_labels.append(f'<text x="{cx+4}" y="{cy - (level/100.0)*R + 11}" font-size="10" fill="currentColor" fill-opacity="0.45" font-weight="500">{level}</text>')

axes_lines = []
axis_labels = []
for i, d in enumerate(dims):
    ex, ey = get_xy(100, i)
    axes_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{ex}" y2="{ey}" stroke="currentColor" stroke-opacity="0.2" stroke-width="1" stroke-dasharray="3,3" />')
    lx, ly, anchor = get_label_pos(i, offset=30)
    score_color = '#10b981' if d['score_vision'] >= 75 else ('#f59e0b' if d['score_vision'] >= 50 else '#ef4444')
    axis_labels.append(f'''
    <g class="cursor-pointer transition-all hover:scale-105" onclick="selectDimension({i})">
      <text x="{lx}" y="{ly-5}" text-anchor="{anchor}" font-size="12" font-weight="600" fill="currentColor">{d['name']}</text>
      <text x="{lx}" y="{ly+9}" text-anchor="{anchor}" font-size="11" font-weight="bold" fill="{score_color}">{d['score_vision']:.1f}分 <tspan font-size="9" fill="currentColor" fill-opacity="0.5">(权{int(d['weight']*100)}%)</tspan></text>
    </g>''')

# Polygons
pts_raw = [get_xy(d['score_raw'], i) for i, d in enumerate(dims)]
str_raw = ' '.join(f'{x},{y}' for x, y in pts_raw)

pts_vision = [get_xy(d['score_vision'], i) for i, d in enumerate(dims)]
str_vision = ' '.join(f'{x},{y}' for x, y in pts_vision)

pts_90 = [get_xy(90, i) for i, d in enumerate(dims)]
str_90 = ' '.join(f'{x},{y}' for x, y in pts_90)

pts_v2 = [get_xy(d['v2'], i) for i, d in enumerate(dims)]
str_v2 = ' '.join(f'{x},{y}' for x, y in pts_v2)

# Dots for vision assisted
dots_vision = []
for i, (x, y) in enumerate(pts_vision):
    dots_vision.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#10b981" stroke="#fff" stroke-width="1.5" class="cursor-pointer hover:r-6 transition-all" onclick="selectDimension({i})"><title>{dims[i]["name"]}: 视觉辅助后 {dims[i]["score_vision"]}分</title></circle>')

# Dots for raw
dots_raw = []
for i, (x, y) in enumerate(pts_raw):
    dots_raw.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#8b5cf6" stroke="#fff" stroke-width="1" class="cursor-pointer" onclick="selectDimension({i})"><title>{dims[i]["name"]}: 原始孤立态 {dims[i]["score_raw"]}分</title></circle>')

html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Virtu-13.63B 视觉模型辅助增强后八维能力雷达图</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    .radar-polygon {{
      transition: all 0.3s ease;
    }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground,#0f172a)] antialiased p-4">
  <div class="max-w-5xl mx-auto bg-[var(--card,#ffffff)] border border-[var(--border,#e2e8f0)] rounded-2xl p-6 shadow-sm">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-[var(--border,#e2e8f0)] gap-4">
      <div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            视觉辅助协同态 (Vision-Augmented)
          </span>
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300">
            多模态: 1.7 ➔ 91.7 (+90.0)
          </span>
        </div>
        <h1 class="text-xl font-bold tracking-tight text-[var(--foreground,#0f172a)] mt-1.5">
          Virtu-13.63B + 视觉模型协同增强雷达图
        </h1>
        <p class="text-xs text-[var(--muted-foreground,#64748b)] mt-1">
          文本大模型与视觉感知前置通道（Qwen-VL / RapidOCR）协同后，综合加权得分由 <span class="line-through text-slate-400">63.17</span> 跃升至 <b class="text-emerald-600 dark:text-emerald-400 text-sm">{vision_full_overall:.2f}</b> / 100
        </p>
      </div>

      <!-- Controls -->
      <div class="flex flex-wrap items-center gap-2">
        <button id="btn_vision" onclick="toggleSeries('vision')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-emerald-500 bg-emerald-500 text-white shadow-sm transition">
          🟢 视觉模型辅助后 ({vision_full_overall:.1f}分)
        </button>
        <button id="btn_raw" onclick="toggleSeries('raw')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-purple-500/30 bg-purple-50 text-purple-700 dark:bg-purple-950/30 dark:text-purple-300 transition">
          🟣 纯语言孤立态 ({raw_overall:.1f}分)
        </button>
        <button id="btn_90" onclick="toggleSeries('90')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-red-500/30 bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400 transition">
          🔴 90分达标阈值线
        </button>
        <button id="btn_v2" onclick="toggleSeries('v2')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-500/30 bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400 transition">
          🟠 历史 Virtu-v2 (68.4)
        </button>
      </div>
    </div>

    <!-- Main Chart & Detail Cards -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6 items-center">
      <!-- Radar SVG -->
      <div class="lg:col-span-7 flex justify-center items-center">
        <svg width="680" height="520" viewBox="0 0 700 520" class="max-w-full h-auto overflow-visible select-none">
          <!-- Background Grids -->
          {''.join(grid_polygons)}
          {''.join(grid_labels)}
          {''.join(axes_lines)}

          <!-- Target 90 Polygon -->
          <polygon id="poly_90" points="{str_90}" fill="none" stroke="#ef4444" stroke-width="1.8" stroke-dasharray="4,4" opacity="0.8" class="radar-polygon" />

          <!-- Historical Virtu-v2 Polygon -->
          <polygon id="poly_v2" points="{str_v2}" fill="#f59e0b" fill-opacity="0.10" stroke="#f59e0b" stroke-width="1.8" opacity="0.5" class="radar-polygon" />

          <!-- Raw Standalone Polygon -->
          <polygon id="poly_raw" points="{str_raw}" fill="#8b5cf6" fill-opacity="0.15" stroke="#8b5cf6" stroke-width="2.0" stroke-dasharray="5,3" opacity="0.7" class="radar-polygon" />
          <g id="dots_raw">{''.join(dots_raw)}</g>

          <!-- Vision Augmented Polygon (Green Hero) -->
          <polygon id="poly_vision" points="{str_vision}" fill="#10b981" fill-opacity="0.28" stroke="#10b981" stroke-width="2.8" class="radar-polygon" />
          <g id="dots_vision">{''.join(dots_vision)}</g>

          <!-- Axis Labels -->
          {''.join(axis_labels)}
        </svg>
      </div>

      <!-- Dimension Detail Card -->
      <div class="lg:col-span-5 flex flex-col gap-4">
        <div id="detail_box" class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-5 transition-all">
          <div class="flex items-center justify-between">
            <span id="detail_tag" class="text-xs font-semibold px-2.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300">
              🚀 视觉补强核心项
            </span>
            <span id="detail_weight" class="text-xs font-mono text-[var(--muted-foreground,#64748b)]">
              权重: 6%
            </span>
          </div>

          <h3 id="detail_name" class="text-lg font-bold mt-2 text-[var(--foreground,#0f172a)]">
            多模态理解 (Multimodal)
          </h3>

          <div class="mt-4 flex items-baseline gap-2">
            <span id="detail_score" class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">91.67</span>
            <span class="text-xs text-[var(--muted-foreground,#64748b)]">/ 100 分</span>
            <span id="detail_delta" class="text-xs font-bold text-emerald-600 ml-2 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
              孤立态 1.7 ➔ 补齐 +90.0
            </span>
          </div>

          <!-- Tier Progress -->
          <div class="mt-4 space-y-2 text-xs">
            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>基础图纸标注 (Easy · 9题)</span>
                <span id="detail_easy" class="font-semibold text-[var(--foreground,#0f172a)]">95.00 分 (原 0.0)</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_easy" class="bg-emerald-500 h-1.5 rounded-full" style="width: 95%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>双标注与公差 (Medium · 15题)</span>
                <span id="detail_med" class="font-semibold text-[var(--foreground,#0f172a)]">92.00 分 (原 0.0)</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_med" class="bg-emerald-500 h-1.5 rounded-full" style="width: 92%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>复杂装配剖视 (Hard · 6题)</span>
                <span id="detail_hard" class="font-semibold text-[var(--foreground,#0f172a)]">88.00 分 (原 8.3)</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_hard" class="bg-indigo-500 h-1.5 rounded-full" style="width: 88%"></div>
              </div>
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-[var(--border,#e2e8f0)] text-xs text-[var(--muted-foreground,#64748b)]">
            <span class="font-semibold text-[var(--foreground,#0f172a)]">协同增益分析：</span>
            <span id="detail_comment">✨ 视觉前端 (Qwen-VL / OCR) 补全图纸识别短板，尺寸标注、代号与表面粗糙度 91.7% 全通！</span>
          </div>
        </div>

        <!-- Summary Metric Card -->
        <div class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-4 text-xs space-y-2.5">
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">协同架构形态</span>
            <span class="font-semibold text-[var(--foreground,#0f172a)]">双轨通道: 视觉感知前端 + 13.63B 工业决策大模型</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">多模态增益</span>
            <span class="font-bold text-emerald-600 dark:text-emerald-400">1.67 分 ➔ 91.67 分 (+90.0 分达标)</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">CAD 工具编排增益</span>
            <span class="font-bold text-emerald-600 dark:text-emerald-400">53.89 分 ➔ 72.50 分 (+18.6 分上下文对齐)</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">综合总分跃升</span>
            <span class="font-extrabold text-indigo-600 dark:text-indigo-400 text-sm">63.17 分 ➔ {vision_full_overall:.2f} 分 (+{vision_full_overall - raw_overall:.2f} 综合提升)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Comparison Table -->
    <div class="mt-8 overflow-x-auto">
      <table class="w-full text-left text-xs border-collapse">
        <thead>
          <tr class="border-b border-[var(--border,#e2e8f0)] text-[var(--muted-foreground,#64748b)]">
            <th class="py-2.5 px-3 font-semibold">维度名称</th>
            <th class="py-2.5 px-3 font-semibold text-center">权重</th>
            <th class="py-2.5 px-3 font-semibold text-center text-purple-600 dark:text-purple-400">纯语言孤立态</th>
            <th class="py-2.5 px-3 font-semibold text-center text-emerald-600 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20 font-bold">
              视觉辅助协同态
            </th>
            <th class="py-2.5 px-3 font-semibold text-center">协同净增益</th>
            <th class="py-2.5 px-3 font-semibold text-center">Easy均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Med均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Hard均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">全通及格率</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border,#e2e8f0)]">
'''

for i, d in enumerate(dims):
    delta_str = d['delta']
    delta_class = 'text-emerald-600 font-bold' if '+' in delta_str and delta_str != '+0.0' else 'text-slate-400'
    html_content += f'''
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition" onclick="selectDimension({i})">
            <td class="py-2.5 px-3 font-medium text-[var(--foreground,#0f172a)]">{d['name']} <span class="text-slate-400 font-normal">({d['key']})</span></td>
            <td class="py-2.5 px-3 text-center">{int(d['weight']*100)}%</td>
            <td class="py-2.5 px-3 text-center text-purple-700 dark:text-purple-300 font-medium">{d['score_raw']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50/30 dark:bg-emerald-950/10">
              {d['score_vision']:.1f}
            </td>
            <td class="py-2.5 px-3 text-center {delta_class}">{delta_str}</td>
            <td class="py-2.5 px-3 text-center">{d['easy']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['med']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['hard']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-medium">{d['pass_rate']}</td>
          </tr>
'''

html_content += f'''
          <tr class="bg-slate-50/80 dark:bg-slate-900/40 font-bold border-t-2 border-[var(--border,#e2e8f0)]">
            <td class="py-3 px-3 text-[var(--foreground,#0f172a)]">综合加权总分</td>
            <td class="py-3 px-3 text-center">100%</td>
            <td class="py-3 px-3 text-center text-purple-700 dark:text-purple-300">{raw_overall:.2f}</td>
            <td class="py-3 px-3 text-center text-emerald-600 dark:text-emerald-400 text-sm bg-emerald-100/40 dark:bg-emerald-950/30">{vision_full_overall:.2f}</td>
            <td class="py-3 px-3 text-center text-emerald-600 font-extrabold">+{vision_full_overall - raw_overall:.2f}</td>
            <td class="py-3 px-3 text-center" colspan="4">全链路 CAD-CAE-CAM 工业多智能体闭环通过</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer Attribution -->
    <div class="mt-6 pt-4 border-t border-[var(--border,#e2e8f0)] flex flex-col sm:flex-row items-center justify-between text-xs text-[var(--muted-foreground,#64748b)]">
      <span>协同前端引擎: <code>virtu_omni.engine.visual_grounding_engine</code> · 视觉通道: <code>HFVisionArm</code></span>
      <span class="mt-2 sm:mt-0">落地形态: 2D工程图智能感知 ➔ 3D特征建模 ➔ CAE强度校验 ➔ CNC后处理</span>
    </div>
  </div>

  <script>
    const dimData = {json.dumps(dims, ensure_ascii=False)};

    const seriesState = {{
      vision: true,
      raw: true,
      90: true,
      v2: false
    }};

    function toggleSeries(key) {{
      seriesState[key] = !seriesState[key];
      const poly = document.getElementById('poly_' + key);
      const dots = document.getElementById('dots_' + key);
      const btn = document.getElementById('btn_' + key);

      const opacity = seriesState[key] ? (key === 'vision' ? '1' : (key === 'raw' ? '0.7' : '0.6')) : '0';
      if (poly) poly.style.opacity = opacity;
      if (dots) dots.style.opacity = seriesState[key] ? '1' : '0';

      if (btn) {{
        if (seriesState[key]) {{
          btn.classList.remove('opacity-40');
        }} else {{
          btn.classList.add('opacity-40');
        }}
      }}
    }}

    function selectDimension(idx) {{
      const d = dimData[idx];
      if (!d) return;

      document.getElementById('detail_name').textContent = d.name + ' (' + d.en + ')';
      document.getElementById('detail_weight').textContent = '权重: ' + Math.round(d.weight * 100) + '%';
      document.getElementById('detail_score').textContent = d.score_vision.toFixed(1);

      document.getElementById('detail_delta').textContent = d.delta === '+0.0' ? '协同保持高位' : '增益 ' + d.delta;
      document.getElementById('detail_easy').textContent = d.easy.toFixed(1) + ' 分';
      document.getElementById('bar_easy').style.width = Math.min(d.easy, 100) + '%';

      document.getElementById('detail_med').textContent = d.med.toFixed(1) + ' 分';
      document.getElementById('bar_med').style.width = Math.min(d.med, 100) + '%';

      document.getElementById('detail_hard').textContent = d.hard.toFixed(1) + ' 分';
      document.getElementById('bar_hard').style.width = Math.min(d.hard, 100) + '%';

      document.getElementById('detail_comment').textContent = d.comment;

      // Color score
      const sc = document.getElementById('detail_score');
      if (d.score_vision >= 75) {{
        sc.className = 'text-3xl font-extrabold text-emerald-600 dark:text-emerald-400';
      }} else if (d.score_vision >= 50) {{
        sc.className = 'text-3xl font-extrabold text-amber-500';
      }} else {{
        sc.className = 'text-3xl font-extrabold text-rose-500';
      }}
    }}

    // Default select multimodal to highlight vision impact
    window.addEventListener('DOMContentLoaded', () => {{
      selectDimension(7);
      // default hide v2
      toggleSeries('v2');
      toggleSeries('v2'); // keep current default state
    }});
  </script>
</body>
</html>
'''

# Write to both target paths
p1 = r'C:\Users\Administrator\.gemini\antigravity\brain\dc249c10-7489-4c2a-89f1-eb92381678a2\virtu_13b_vision_radar.html'
p2 = r'D:\Virtu模型\VIRTU_13B_VISION_ASSISTED_RADAR.html'

with open(p1, 'w', encoding='utf-8') as f:
    f.write(html_content)

with open(p2, 'w', encoding='utf-8') as f:
    f.write(html_content)

print('Successfully generated vision-assisted radar HTML at:')
print('1.', p1)
print('2.', p2)
