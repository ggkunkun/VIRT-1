import math
import json

dims = [
    {
        'key': 'boundary', 'name': '边界处理', 'en': 'Boundary & Safety',
        'weight': 0.12, 'score_raw': 47.67, 'score_max': 100.00,
        'easy': 100.0, 'med': 100.0, 'hard': 100.0, 'pass_rate': '100.0%',
        'delta': '+52.33',
        'comment': '🛡️ 30/30 满分！杜绝越权短接、虚构伪标准/API、盲猜缺失量与顺从物理矛盾'
    },
    {
        'key': 'knowledge', 'name': '知识覆盖', 'en': 'Knowledge Coverage',
        'weight': 0.15, 'score_raw': 79.06, 'score_max': 96.78,
        'easy': 100.0, 'med': 93.6, 'hard': 100.0, 'pass_rate': '96.7%',
        'delta': '+17.72',
        'comment': '📚 国家标准库/公差等级/热处理工艺/专业工业软件背景全通'
    },
    {
        'key': 'instruction', 'name': '指令遵循', 'en': 'Instruction Following',
        'weight': 0.14, 'score_raw': 61.84, 'score_max': 94.10,
        'easy': 100.0, 'med': 92.2, 'hard': 90.0, 'pass_rate': '93.3%',
        'delta': '+32.25',
        'comment': '📋 消除空 think 块污染，严格按精确行数、JSON 结构、英汉大小写约束输出'
    },
    {
        'key': 'multimodal', 'name': '多模态理解', 'en': 'Multimodal',
        'weight': 0.06, 'score_raw': 1.67, 'score_max': 100.00,
        'easy': 100.0, 'med': 100.0, 'hard': 100.0, 'pass_rate': '100.0%',
        'delta': '+98.33',
        'comment': '👁️ 视觉感知前置通道（Qwen-VL / RapidOCR）精准识读图纸全部标注与表面代号'
    },
    {
        'key': 'toolcall', 'name': '工具编排', 'en': 'Tool Orchestration',
        'weight': 0.18, 'score_raw': 53.89, 'score_max': 85.56,
        'easy': 88.9, 'med': 84.4, 'hard': 83.3, 'pass_rate': '86.7%',
        'delta': '+31.67',
        'comment': '🔧 六大软件动作与工具包装严格规范化，消除动作别名与参数缺失'
    },
    {
        'key': 'reasoning', 'name': '推理逻辑', 'en': 'Reasoning Logic',
        'weight': 0.17, 'score_raw': 79.67, 'score_max': 81.98,
        'easy': 100.0, 'med': 82.2, 'hard': 54.4, 'pass_rate': '80.0%',
        'delta': '+2.32',
        'comment': '⚙️ 力学厚壁圆筒弹性解、RSS 叠装公差传递与刀心交点几何推导严谨'
    },
    {
        'key': 'generation', 'name': '内容生成', 'en': 'Content Generation',
        'weight': 0.10, 'score_raw': 81.11, 'score_max': 80.56,
        'easy': 94.4, 'med': 75.3, 'hard': 72.8, 'pass_rate': '76.7%',
        'delta': '-0.56',
        'comment': '✍️ 机械加工规程卡、刀具清单与多轴 G 代码保持高标准工业水准'
    },
    {
        'key': 'generalization', 'name': '泛化适配', 'en': 'Generalization',
        'weight': 0.08, 'score_raw': 68.44, 'score_max': 75.82,
        'easy': 91.1, 'med': 73.5, 'hard': 58.6, 'pass_rate': '73.3%',
        'delta': '+7.38',
        'comment': '🔄 特殊控制器功能码方言对照与非标标称值选取平稳自适应'
    }
]

score_raw_total = 63.17
score_max_total = 89.15

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
    score_color = '#10b981' if d['score_max'] >= 90 else ('#0284c7' if d['score_max'] >= 80 else '#f59e0b')
    axis_labels.append(f'''
    <g class="cursor-pointer transition-all hover:scale-105" onclick="selectDimension({i})">
      <text x="{lx}" y="{ly-5}" text-anchor="{anchor}" font-size="12" font-weight="600" fill="currentColor">{d['name']}</text>
      <text x="{lx}" y="{ly+9}" text-anchor="{anchor}" font-size="11" font-weight="bold" fill="{score_color}">{d['score_max']:.1f}分 <tspan font-size="9" fill="currentColor" fill-opacity="0.5">(权{int(d['weight']*100)}%)</tspan></text>
    </g>''')

pts_raw = [get_xy(d['score_raw'], i) for i, d in enumerate(dims)]
str_raw = ' '.join(f'{x},{y}' for x, y in pts_raw)

pts_max = [get_xy(d['score_max'], i) for i, d in enumerate(dims)]
str_max = ' '.join(f'{x},{y}' for x, y in pts_max)

pts_90 = [get_xy(90, i) for i, d in enumerate(dims)]
str_90 = ' '.join(f'{x},{y}' for x, y in pts_90)

dots_max = []
for i, (x, y) in enumerate(pts_max):
    dots_max.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#10b981" stroke="#fff" stroke-width="1.5" class="cursor-pointer hover:r-6 transition-all" onclick="selectDimension({i})"><title>{dims[i]["name"]}: 全极限强化实测 {dims[i]["score_max"]}分</title></circle>')

dots_raw = []
for i, (x, y) in enumerate(pts_raw):
    dots_raw.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#8b5cf6" stroke="#fff" stroke-width="1" class="cursor-pointer" onclick="selectDimension({i})"><title>{dims[i]["name"]}: 原始基线 {dims[i]["score_raw"]}分</title></circle>')

html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Virtu-13.63B 全维度能力极限强化最新真实雷达图</title>
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
            🔥 全能力极限强化 (240题全部机评实测)
          </span>
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300">
            真实归因: full_hardened_raw.jsonl
          </span>
        </div>
        <h1 class="text-xl font-bold tracking-tight text-[var(--foreground,#0f172a)] mt-1.5">
          Virtu-13.63B 全维度极限强化后八维综合能力雷达图
        </h1>
        <p class="text-xs text-[var(--muted-foreground,#64748b)] mt-1">
          八大工业维度全链路极限强化与客观真实评测 · 综合总分: <span class="line-through text-slate-400">63.17</span> ➔ <b class="text-emerald-600 dark:text-emerald-400 text-base">{score_max_total:.2f}</b> / 100 <span class="text-emerald-600 font-bold">(+{score_max_total - score_raw_total:.2f} 真实跨越)</span>
        </p>
      </div>

      <!-- Controls -->
      <div class="flex flex-wrap items-center gap-2">
        <button id="btn_max" onclick="toggleSeries('max')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-emerald-600 bg-emerald-600 text-white shadow-sm transition">
          🟢 极限强化实测态 ({score_max_total:.1f}分)
        </button>
        <button id="btn_raw" onclick="toggleSeries('raw')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-purple-500/30 bg-purple-50 text-purple-700 dark:bg-purple-950/30 dark:text-purple-300 transition">
          🟣 原始未强化基线 ({score_raw_total:.1f}分)
        </button>
        <button id="btn_90" onclick="toggleSeries('90')" class="px-3 py-1.5 rounded-lg text-xs font-medium border border-red-500/30 bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400 transition">
          🔴 90分工业卓越红线
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

          <!-- Raw Baseline Polygon (Purple Dashed) -->
          <polygon id="poly_raw" points="{str_raw}" fill="#8b5cf6" fill-opacity="0.15" stroke="#8b5cf6" stroke-width="2.0" stroke-dasharray="5,3" opacity="0.7" class="radar-polygon" />
          <g id="dots_raw">{''.join(dots_raw)}</g>

          <!-- Ultimate Max Polygon (Emerald Hero) -->
          <polygon id="poly_max" points="{str_max}" fill="#10b981" fill-opacity="0.28" stroke="#10b981" stroke-width="2.8" class="radar-polygon" />
          <g id="dots_max">{''.join(dots_max)}</g>

          <!-- Axis Labels -->
          {''.join(axis_labels)}
        </svg>
      </div>

      <!-- Dimension Detail Card -->
      <div class="lg:col-span-5 flex flex-col gap-4">
        <div id="detail_box" class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-5 transition-all">
          <div class="flex items-center justify-between">
            <span id="detail_tag" class="text-xs font-semibold px-2.5 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300">
              当前焦点维度
            </span>
            <span id="detail_weight" class="text-xs font-mono text-[var(--muted-foreground,#64748b)]">
              权重: 12%
            </span>
          </div>

          <h3 id="detail_name" class="text-lg font-bold mt-2 text-[var(--foreground,#0f172a)]">
            边界处理 (Boundary & Safety)
          </h3>

          <div class="mt-4 flex items-baseline gap-2">
            <span id="detail_score" class="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">100.00</span>
            <span class="text-xs text-[var(--muted-foreground,#64748b)]">/ 100 分</span>
            <span id="detail_delta" class="text-xs font-bold text-emerald-600 ml-2 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded">
              提升 +52.33
            </span>
          </div>

          <!-- Tier Progress -->
          <div class="mt-4 space-y-2 text-xs">
            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>基础难度 (Easy · 9题)</span>
                <span id="detail_easy" class="font-semibold text-[var(--foreground,#0f172a)]">100.00 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_easy" class="bg-emerald-500 h-1.5 rounded-full" style="width: 100%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>中阶难度 (Medium · 15题)</span>
                <span id="detail_med" class="font-semibold text-[var(--foreground,#0f172a)]">100.00 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_med" class="bg-emerald-500 h-1.5 rounded-full" style="width: 100%"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between text-[var(--muted-foreground,#64748b)] mb-1">
                <span>高阶难度 (Hard · 6题)</span>
                <span id="detail_hard" class="font-semibold text-[var(--foreground,#0f172a)]">100.00 分</span>
              </div>
              <div class="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                <div id="bar_hard" class="bg-emerald-500 h-1.5 rounded-full" style="width: 100%"></div>
              </div>
            </div>
          </div>

          <div class="mt-4 pt-3 border-t border-[var(--border,#e2e8f0)] text-xs text-[var(--muted-foreground,#64748b)]">
            <span class="font-semibold text-[var(--foreground,#0f172a)]">真实测评证据：</span>
            <span id="detail_comment">🛡️ 30/30 满分！杜绝越权短接、虚构伪标准/API、盲猜缺失量与顺从物理矛盾</span>
          </div>
        </div>

        <!-- Summary Metric Card -->
        <div class="bg-[var(--sidebar,#f8fafc)] dark:bg-slate-900/60 border border-[var(--border,#e2e8f0)] rounded-xl p-4 text-xs space-y-2.5">
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">客观评测样本总量</span>
            <span class="font-semibold text-[var(--foreground,#0f172a)]">240 题全量实测 (8维完整闭环)</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">判分器与口径</span>
            <span class="font-mono text-xs text-[var(--foreground,#0f172a)]">virtu_eval.graders (basis=measured)</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">突破 90分 卓越维度数</span>
            <span class="font-bold text-emerald-600 dark:text-emerald-400">4 / 8 维度 (边界100 / 多模态100 / 知识96.8 / 指令94.1)</span>
          </div>
          <div class="flex justify-between items-center">
            <span class="text-[var(--muted-foreground,#64748b)]">终极综合得分</span>
            <span class="font-extrabold text-emerald-600 dark:text-emerald-400 text-sm">63.17 分 ➔ {score_max_total:.2f} 分 (+{score_max_total - score_raw_total:.2f} 真实跨越)</span>
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
            <th class="py-2.5 px-3 font-semibold text-center text-purple-600 dark:text-purple-400">原始未强化基线</th>
            <th class="py-2.5 px-3 font-semibold text-center text-emerald-600 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20 font-bold">
              全能力极限强化实测
            </th>
            <th class="py-2.5 px-3 font-semibold text-center">净增量</th>
            <th class="py-2.5 px-3 font-semibold text-center">Easy均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Med均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">Hard均分</th>
            <th class="py-2.5 px-3 font-semibold text-center">达标状态</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border,#e2e8f0)]">
'''

for i, d in enumerate(dims):
    delta_str = d['delta']
    delta_class = 'text-emerald-600 font-bold' if '+' in delta_str and delta_str != '+0.0' else ('text-slate-400' if delta_str == '+0.0' else 'text-rose-500')
    status_badge = '🟢 卓越达标' if d['score_max'] >= 90 else ('🟢 工业优秀' if d['score_max'] >= 80 else '🟡 稳步提升')
    html_content += f'''
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer transition" onclick="selectDimension({i})">
            <td class="py-2.5 px-3 font-medium text-[var(--foreground,#0f172a)]">{d['name']} <span class="text-slate-400 font-normal">({d['key']})</span></td>
            <td class="py-2.5 px-3 text-center">{int(d['weight']*100)}%</td>
            <td class="py-2.5 px-3 text-center text-purple-700 dark:text-purple-300 font-medium">{d['score_raw']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50/30 dark:bg-emerald-950/10">
              {d['score_max']:.1f}
            </td>
            <td class="py-2.5 px-3 text-center {delta_class}">{delta_str}</td>
            <td class="py-2.5 px-3 text-center">{d['easy']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['med']:.1f}</td>
            <td class="py-2.5 px-3 text-center">{d['hard']:.1f}</td>
            <td class="py-2.5 px-3 text-center font-medium">{status_badge}</td>
          </tr>
'''

html_content += f'''
          <tr class="bg-slate-50/80 dark:bg-slate-900/40 font-bold border-t-2 border-[var(--border,#e2e8f0)]">
            <td class="py-3 px-3 text-[var(--foreground,#0f172a)]">综合加权总分</td>
            <td class="py-3 px-3 text-center">100%</td>
            <td class="py-3 px-3 text-center text-purple-700 dark:text-purple-300">{score_raw_total:.2f}</td>
            <td class="py-3 px-3 text-center text-emerald-600 dark:text-emerald-400 text-sm bg-emerald-100/40 dark:bg-emerald-950/30">{score_max_total:.2f}</td>
            <td class="py-3 px-3 text-center text-emerald-600 font-extrabold">+{score_max_total - score_raw_total:.2f}</td>
            <td class="py-3 px-3 text-center" colspan="4">依据《测量宪法》240题全量机评实测落盘 (full_hardened_raw.jsonl)</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Footer Attribution -->
    <div class="mt-6 pt-4 border-t border-[var(--border,#e2e8f0)] flex flex-col sm:flex-row items-center justify-between text-xs text-[var(--muted-foreground,#64748b)]">
      <span>全量评测真机原始日志: <code>models/virtu-13b/full_hardened_raw.jsonl</code> (240 题逐题可归因)</span>
      <span class="mt-2 sm:mt-0">落地形态: 极限边界护栏 + GBNF 工具对齐 + 卫生层 + 视觉通道联动</span>
    </div>
  </div>

  <script>
    const dimData = {json.dumps(dims, ensure_ascii=False)};

    const seriesState = {{
      max: true,
      raw: true,
      90: true
    }};

    function toggleSeries(key) {{
      seriesState[key] = !seriesState[key];
      const poly = document.getElementById('poly_' + key);
      const dots = document.getElementById('dots_' + key);
      const btn = document.getElementById('btn_' + key);

      const opacity = seriesState[key] ? (key === 'max' ? '1' : (key === 'raw' ? '0.7' : '0.6')) : '0';
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
      document.getElementById('detail_score').textContent = d.score_max.toFixed(1);

      document.getElementById('detail_delta').textContent = '提升 ' + d.delta;
      document.getElementById('detail_easy').textContent = d.easy.toFixed(1) + ' 分';
      document.getElementById('bar_easy').style.width = Math.min(d.easy, 100) + '%';

      document.getElementById('detail_med').textContent = d.med.toFixed(1) + ' 分';
      document.getElementById('bar_med').style.width = Math.min(d.med, 100) + '%';

      document.getElementById('detail_hard').textContent = d.hard.toFixed(1) + ' 分';
      document.getElementById('bar_hard').style.width = Math.min(d.hard, 100) + '%';

      document.getElementById('detail_comment').textContent = d.comment;

      // Color score
      const sc = document.getElementById('detail_score');
      if (d.score_max >= 90) {{
        sc.className = 'text-3xl font-extrabold text-emerald-600 dark:text-emerald-400';
      }} else if (d.score_max >= 80) {{
        sc.className = 'text-3xl font-extrabold text-sky-600 dark:text-sky-400';
      }} else {{
        sc.className = 'text-3xl font-extrabold text-amber-500';
      }}
    }}

    // Default select boundary
    window.addEventListener('DOMContentLoaded', () => {{
      selectDimension(0);
    }});
  </script>
</body>
</html>
'''

# Write to both target paths
p1 = r'C:\Users\Administrator\.gemini\antigravity\brain\dc249c10-7489-4c2a-89f1-eb92381678a2\virtu_13b_ultimate_radar.html'
p2 = r'D:\Virtu模型\VIRTU_13B_ULTIMATE_MAX_RADAR.html'

with open(p1, 'w', encoding='utf-8') as f:
    f.write(html_content)

with open(p2, 'w', encoding='utf-8') as f:
    f.write(html_content)

print('Successfully generated ultimate radar HTML at:')
print('1.', p1)
print('2.', p2)
