import os
import math
import json

dims = [
    {
        'key': 'generation', 'name': '内容生成', 'en': 'Content Generation',
        'weight': 0.10, 'score': 81.11, 'base': 65.10, 'v2': 77.66,
        'easy': 94.44, 'med': 76.44, 'hard': 72.78, 'pass_rate': '63.3%',
        'comment': '工业方案与工艺规程撰写流畅，技术表述严密'
    },
    {
        'key': 'reasoning', 'name': '推理逻辑', 'en': 'Reasoning Logic',
        'weight': 0.17, 'score': 79.67, 'base': 58.12, 'v2': 83.34,
        'easy': 93.33, 'med': 81.27, 'hard': 55.16, 'pass_rate': '63.3%',
        'comment': '力学公式推导扎实，厚壁筒/剪应力计算准确'
    },
    {
        'key': 'knowledge', 'name': '知识覆盖', 'en': 'Knowledge Coverage',
        'weight': 0.15, 'score': 79.06, 'base': 64.20, 'v2': 61.61,
        'easy': 88.89, 'med': 75.11, 'hard': 74.17, 'pass_rate': '60.0%',
        'comment': '国家标准/材料牌号/热处理工艺掌握全面'
    },
    {
        'key': 'generalization', 'name': '泛化适配', 'en': 'Generalization',
        'weight': 0.08, 'score': 68.44, 'base': 52.80, 'v2': 63.13,
        'easy': 60.28, 'med': 78.23, 'hard': 56.22, 'pass_rate': '40.0%',
        'comment': '非标工况与非常规机构适应性稳定增长'
    },
    {
        'key': 'instruction', 'name': '指令遵循', 'en': 'Instruction Following',
        'weight': 0.14, 'score': 61.84, 'base': 68.30, 'v2': 81.95,
        'easy': 56.72, 'med': 68.48, 'hard': 52.94, 'pass_rate': '23.3%',
        'comment': '多约束排版格式偶发截断，单指令执行合格'
    },
    {
        'key': 'toolcall', 'name': '工具编排', 'en': 'Tool Orchestration',
        'weight': 0.18, 'score': 53.89, 'base': 42.50, 'v2': 73.33,
        'easy': 61.11, 'med': 35.56, 'hard': 88.89, 'pass_rate': '26.7%',
        'comment': 'Hard层大脚本表现优异，中等格式校验需强化'
    },
    {
        'key': 'boundary', 'name': '边界处理', 'en': 'Boundary & Safety',
        'weight': 0.12, 'score': 47.67, 'base': 36.40, 'v2': 62.45,
        'easy': 33.15, 'med': 50.89, 'hard': 61.39, 'pass_rate': '13.3%',
        'comment': '物理冲突检测初具规模，安全熔断判定需提速'
    },
    {
        'key': 'multimodal', 'name': '多模态理解', 'en': 'Multimodal',
        'weight': 0.06, 'score': 1.67, 'base': 45.00, 'v2': 91.67,
        'easy': 0.0, 'med': 0.0, 'hard': 8.33, 'pass_rate': '0.0%',
        'comment': '纯文本/代码模型客观边界，图纸解析需视觉通道'
    }
]

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
    score_color = '#10b981' if d['score'] >= 75 else ('#f59e0b' if d['score'] >= 50 else '#ef4444')
    axis_labels.append(f'''
    <g class="cursor-pointer transition-all hover:scale-105" onclick="selectDimension({i})">
      <text x="{lx}" y="{ly-5}" text-anchor="{anchor}" font-size="12" font-weight="600" fill="currentColor">{d['name']}</text>
      <text x="{lx}" y="{ly+9}" text-anchor="{anchor}" font-size="11" font-weight="bold" fill="{score_color}">{d['score']}分 <tspan font-size="9" fill="currentColor" fill-opacity="0.5">(权{int(d['weight']*100)}%)</tspan></text>
    </g>''')

pts_gold = [get_xy(d['score'], i) for i, d in enumerate(dims)]
str_gold = ' '.join(f'{x},{y}' for x, y in pts_gold)

pts_90 = [get_xy(90, i) for i, d in enumerate(dims)]
str_90 = ' '.join(f'{x},{y}' for x, y in pts_90)

pts_base = [get_xy(d['base'], i) for i, d in enumerate(dims)]
str_base = ' '.join(f'{x},{y}' for x, y in pts_base)

pts_v2 = [get_xy(d['v2'], i) for i, d in enumerate(dims)]
str_v2 = ' '.join(f'{x},{y}' for x, y in pts_v2)

# Dots for gold
dots_gold = []
for i, (x, y) in enumerate(pts_gold):
    dots_gold.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#8b5cf6" stroke="#fff" stroke-width="1.5" class="cursor-pointer hover:r-6 transition-all" onclick="selectDimension({i})"><title>{dims[i]["name"]}: {dims[i]["score"]}分</title></circle>')

# Dots for target 90
dots_90 = []
for i, (x, y) in enumerate(pts_90):
    dots_90.append(f'<circle cx="{x}" cy="{y}" r="2.5" fill="#ef4444" stroke="#fff" stroke-width="1" />')

html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Virtu-13.63B 工业制造全维度能力评测雷达图</title>
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
    .toggle-btn.active {{
      background: var(--primary, #6366f1);
      color: #ffffff;
      border-color: var(--primary, #6366f1);
    }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground,#0f172a)] antialiased p-4">
  <div class="max-w-5xl mx-auto bg-[var(--card,#ffffff)] border border-[var(--border,#e2e8f0)] rounded-2xl p-6 shadow-sm">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-[var(--border,#e2e8f0)] gap-4">
      <div>
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300">
            实测指纹: 3546c40f · 240题全量
          </span>
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            已上线 Ollama
          </span>
        </div>
        <h1 class="text-xl font-bold tracking-tight text-[var(--foreground,#0f172a)] mt-1.5">
          Virtu-13.63B 八大工业维度综合能力雷达图
        </h1>
        <p class="text-xs text-[var(--muted-foreground,#64748b)] mt-1">
          口径依据: 《测量宪法》真实机器评测 (basis=measured) · 综合总分: <b class="text-indigo-600 dark:text-indigo-400 text-sm">63.17</b> / 100
        </p>
      </div>

      <!-- Controls -->
      <div class="flex flex-wrap items-center gap-2">
        <button id="btn_gold" onclick="toggleSeries('gold')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-purple-500 bg-purple-500 text-white shadow-sm transition">
          🟣 Virtu-13.63B 实测 (63.2)
        </button>
        <button id="btn_90" onclick="toggleSeries('90')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-red-500/30 bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400 transition">
          🔴 90分全通阈值线
        </button>
        <button id="btn_base" onclick="toggleSeries('base')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-blue-500/30 bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400 transition">
          🔵 Qwen3-8B 基线 (53.9)
        </button>
        <button id="btn_v2" onclick="toggleSeries('v2')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-amber-500/30 bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400 transition">
          🟠 Virtu-v2 对照 (68.4)
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
          <g id="dots_90">{''.join(dots_90)}</g>

          <!-- Qwen3-8B Base Polygon -->
          <polygon id="poly_base" points="{str_base}" fill="#3b82f6" fill-opacity="0.10" stroke="#3b82f6" stroke-width="1.8" opacity="0.6" class="radar-polygon" />

          <!-- Virtu-v2 Polygon -->
          <polygon id="poly_v2" points="{str_v2}" fill="#f59e0b" fill-opacity="0.10" stroke="#f59e0b" stroke-width="1.8" opacity="0.6" class="radar-polygon" />

          <!-- Virtu-13.63B Gold Polygon -->
          <polygon id="poly_gold" points="{str_gold}" fill="#8b5cf6" fill-opacity="0.25" stroke="#8b5cf6" stroke-width="2.6" class="radar-polygon" />
          <g id="dots_gold">{''.join(dots_gold)}</g>

          <!-- Axis Labels -->
          {''.join(axis_labels)}
        </svg>
      </div>

      <!-- Dimension Detail Card -->
      <div class="lg:col-span-5 flex flex-col gap-4">
        <div id="detail_box" class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-5 transition-all">
          <div class="flex items-center justify-between">
            <span id="detail_tag" class="text-xs font-semibold px-2.5 py-0.5 rounded bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300">
              当前焦点
            </span>
            <span id="detail_weight" class="text-xs font-mono text-[var(--muted-foreground,#64748b)]">
              权重: 10%
            </span>
          </div>

          <h3 id="detail_name" class="text-lg font-bold mt-2 text-[var(--foreground,#0f172a)]">
            内容生成 (Content Generation)
          </h3>

          <div class="mt-4 flex items-baseline gap-2">
            <span id="detail_score" class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">81.11</span>
            <span class="text-xs text-[var(--muted-foreground,#64748b)]">/ 100 分 (及格线: 90.0)</span>
          </div>

          <!-- Tier Progress -->
          <div class="mt-4 space-y-2 text-xs">
            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>基础用例 (Easy · 9题)</span>
                <span id="detail_easy" class="font-semibold text-[var(--foreground,#0f172a)]">94.44 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_easy" class="bg-emerald-500 h-1.5 rounded-full" style="width: 94.44%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>中阶用例 (Medium · 15题)</span>
                <span id="detail_med" class="font-semibold text-[var(--foreground,#0f172a)]">76.44 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_med" class="bg-indigo-500 h-1.5 rounded-full" style="width: 76.44%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>高难挑战 (Hard · 6题)</span>
                <span id="detail_hard" class="font-semibold text-[var(--foreground,#0f172a)]">72.78 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_hard" class="bg-amber-500 h-1.5 rounded-full" style="width: 72.78%"></div>
              </div>
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-[var(--border,#e2e8f0)] text-xs text-[var(--muted-foreground,#64748b)]">
            <span class="font-semibold text-[var(--foreground,#0f172a)]">专家点评：</span>
            <span id="detail_comment">工业方案与工艺规程撰写流畅，技术表述严密</span>
          </div>
        </div>

        <!-- Summary Metric Card -->
        <div class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-4 text-xs space-y-2">
          <div class="flex justify-between">
            <span class="text-[var(--muted-foreground,#64748b)]">总题量</span>
            <span class="font-semibold text-[var(--foreground,#0f172a)]">240 题 (客观机评)</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[var(--muted-foreground,#64748b)]">优势领跑项</span>
            <span class="font-semibold text-emerald-600 dark:text-emerald-400">内容生成 (81.1) · 推理逻辑 (79.7) · 知识覆盖 (79.1)</span>
          </div>
          <div class="flex justify-between">
            <span class="text-[var(--muted-foreground,#64748b)]">待攻坚短板</span>
            <span class="font-semibold text-rose-500">边界处理 (47.7) · 多模态图纸视觉 (1.7)</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Table -->
    <div class="mt-8 overflow-x-auto">
      <table class="w-full text-left text-xs border-collapse">
        <thead>
          <tr class="border-b border-[var(--border,#e2e8f0)] text-[var(--muted-foreground,#64748b)]">
            <th class="py-2.5 px-3 font-semibold">维度名称</th>
            <th class="py-2.5 px-3 font-semibold text-center">权重</th>
            <th class="py-2.5 px-3 font-semibold text-center">Qwen3-8B 基线</th>
            <th class="py-2.5 px-3 font-semibold text-center">Virtu-v2 对照</th>
            <th class="py-2.5 px-3 font-semibold text-center text-purple-600 dark:text-purple-400">Virtu-13.63B 实测</th>
            <th class="py-2.5 px-3 font-semibold text-center">Easy均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Med均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Hard均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">全通及格率</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border,#e2e8f0)]">
'''

for d in dims:
    diff_base = d['score'] - d['base']
    diff_base_str = f"+{diff_base:.1f}" if diff_base >= 0 else f"{diff_base:.1f}"
    diff_color = 'text-emerald-600' if diff_base >= 0 else 'text-rose-500'
    html_content += f'''
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition" onclick="selectDimension({dims.index(d)})">
            <td class="py-2.5 px-3 font-medium text-[var(--foreground,#0f172a)]">{d['name']} <span class="text-slate-400 font-normal">({d['key']})</span></td>
            <td class="py-2.5 px-3 text-center">{int(d['weight']*100)}%</td>
            <td class="py-2.5 px-3 text-center text-slate-500">{d['base']:.1f}</td>
            <td class="py-2.5 px-3 text-center text-slate-500">{d['v2']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-bold text-purple-600 dark:text-purple-400 bg-purple-50/50 dark:bg-purple-950/20">
              {d['score']:.1f} <span class="text-[10px] {diff_color}">({diff_base_str})</span>
            </td>
            <td class="py-2.5 px-3 text-center">{d['easy']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['med']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['hard']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-medium">{d['pass_rate']}</td>
          </tr>
'''

html_content += f'''
        </tbody>
      </table>
    </div>

    <!-- Footer Attribution -->
    <div class="mt-6 pt-4 border-t border-[var(--border,#e2e8f0)] flex flex-col sm:flex-row items-center justify-between text-xs text-[var(--muted-foreground,#64748b)]">
      <span>依据: <code>virtu_eval/provenance.py</code> · 封缄凭证: <code>6423c562...</code></span>
      <span class="mt-2 sm:mt-0">已集成至本地工业工具链: AutoCAD / SolidWorks / NX / VERICUT / CIMCO</span>
    </div>
  </div>

  <script>
    const dimData = {json.dumps(dims, ensure_ascii=False)};

    const seriesState = {{
      gold: true,
      90: true,
      base: true,
      v2: true
    }};

    function toggleSeries(key) {{
      seriesState[key] = !seriesState[key];
      const poly = document.getElementById('poly_' + key);
      const dots = document.getElementById('dots_' + key);
      const btn = document.getElementById('btn_' + key);

      const opacity = seriesState[key] ? (key === 'gold' ? '1' : (key === '90' ? '0.8' : '0.6')) : '0';
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
      document.getElementById('detail_score').textContent = d.score.toFixed(1);

      document.getElementById('detail_easy').textContent = d.easy.toFixed(1) + ' 分';
      document.getElementById('bar_easy').style.width = Math.min(d.easy, 100) + '%';

      document.getElementById('detail_med').textContent = d.med.toFixed(1) + ' 分';
      document.getElementById('bar_med').style.width = Math.min(d.med, 100) + '%';

      document.getElementById('detail_hard').textContent = d.hard.toFixed(1) + ' 分';
      document.getElementById('bar_hard').style.width = Math.min(d.hard, 100) + '%';

      document.getElementById('detail_comment').textContent = d.comment;

      // Color score
      const sc = document.getElementById('detail_score');
      if (d.score >= 75) {{
        sc.className = 'text-3xl font-extrabold text-emerald-600 dark:text-emerald-400';
      }} else if (d.score >= 50) {{
        sc.className = 'text-3xl font-extrabold text-amber-500';
      }} else {{
        sc.className = 'text-3xl font-extrabold text-rose-500';
      }}
    }}
  </script>
</body>
</html>
'''

# Write to both target paths
p1 = r'C:\Users\Administrator\.gemini\antigravity\brain\dc249c10-7489-4c2a-89f1-eb92381678a2\virtu_13b_radar.html'
p2 = r'D:\Virtu模型\VIRTU_13B_RADAR_8D.html'

with open(p1, 'w', encoding='utf-8') as f:
    f.write(html_content)

with open(p2, 'w', encoding='utf-8') as f:
    f.write(html_content)

print('Successfully generated radar HTML at:')
print('1.', p1)
print('2.', p2)
