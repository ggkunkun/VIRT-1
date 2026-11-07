"""Virtu 13.63B 深度规划智能体（Plan -> Act -> Verify），对着 Windows-MCP 落地。

设计目标：让模型"先想清楚再动"，而不是靠反复试错穷举。

三个阶段：
  P 规划  —— 不绑工具（绑了就会抢答），给真实 inputSchema，产出结构化 JSON 计划；
             计划必须过硬闸门：工具名合法、参数键受 schema 约束、required 齐全、enum 合法、
             写操作前必须有观察步。不过闸 -> 带违规清单返修 1 次，仍不过则降级并记录 plan_valid=false。
  A 执行  —— 按步执行，每步只允许计划里的工具；模型必须先用一行"检查"引用上一步观察里的原文片段
             （引用对不上 = 幻觉证据，单独计数）；动作签名去重，重复动作直接拦截不执行。
  V 验收  —— 逐条 success_criteria 判定，判定必须引用观察原文，引用不到就记 unknown（不算通过）。

反穷举闸门（这是与单轮直调桥的本质区别）：
  1. action_sig 去重：同参同工具第二次出现直接不执行；
  2. 每步尝试上限 2 次，失败只能触发 1 次重规划，全局重规划上限 2 次；
  3. 连续 3 步失败立即熔断，输出 RCFA 而不是继续试；
  4. 未在计划中出现的写操作（launch/stop/kill 等）一律拒绝执行。

用法：
    python bridges/deep_agent.py --task "..." --out runs/deep_agent_xxx
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from windows_mcp_bridge import (WindowsMCPClient, mcp_to_ollama_tools,  # noqa: E402
                               DEFAULT_MODEL, DEFAULT_TOOLS, OLLAMA, _http)
try:
    from magic_hand_adapter import (MagicHandAdapter, WRITE_ACTIONS as MAGIC_WRITE,
                                   SCRIPTS, slim_schemas)
except Exception:                                  # pragma: no cover
    MagicHandAdapter, MAGIC_WRITE, SCRIPTS = None, set(), None

ROOT = Path(__file__).resolve().parent.parent
MAX_STEPS = 6
MAX_ATTEMPTS_PER_STEP = 2
MAX_REPLANS = 2
WRITE_MODES = {"launch", "launch_executable", "start", "stop", "kill", "resize", "switch", "close"}
READ_ONLY_HINT = ("controlstatus", "list", "get", "status", "query", "screen")


# --------------------------------------------------------------------------- model io
def chat(model: str, messages: list, tools: list | None = None, *,
         think: bool = False, num_predict: int = 256, num_ctx: int = 4096,
         temperature: float = 0.1, timeout: int = 600,
         format_schema: dict | None = None) -> tuple[dict, float]:
    payload = {"model": model, "stream": False, "think": think, "keep_alive": "10m",
               "options": {"num_ctx": num_ctx, "temperature": temperature,
                           "num_predict": num_predict, "num_gpu": 99},
               "messages": messages}
    if tools:
        payload["tools"] = tools
    if format_schema:                     # Ollama 结构化输出：语法层强制合法 JSON
        payload["format"] = format_schema
    req = urllib.request.Request(OLLAMA + "/api/chat",
                                 data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with _http.open(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:           # 404=模型不存在 500=加载失败，都带回原文
        body = e.read().decode("utf-8", errors="replace")[:400]
        return {"error": f"HTTP {e.code}: {body}"}, round(time.time() - t0, 2)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:300]}"}, round(time.time() - t0, 2)
    # 工具腿若有 tool_calls，正文一律丢弃（下游只认结构化调用，不认套话）
    try:
        from windows_mcp_bridge import drop_tool_leg_prose
        resp = drop_tool_leg_prose(resp)
    except Exception:
        pass
    return resp, round(time.time() - t0, 2)


def parse_json_loose(text: str) -> tuple[dict | None, str]:
    """模型有时吐 python dict 字面量（单引号）而非 JSON；按 JSON -> literal_eval -> 截取 依次尝试。"""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t), "json"
    except Exception:
        pass
    try:
        v = ast.literal_eval(t)
        if isinstance(v, dict):
            return v, "literal_eval"
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        for fn, tag in ((json.loads, "json_extracted"), (ast.literal_eval, "literal_extracted")):
            try:
                v = fn(m.group())
                if isinstance(v, dict):
                    return v, tag
            except Exception:
                continue
    return None, "failed"


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def is_write_action(tool: str, args: dict, schemas: list[dict]) -> bool:
    """写操作判定：MCP 走 mode（含 schema default），skill 走 action。"""
    if tool == "MagicHand":
        return str((args or {}).get("action") or "") in MAGIC_WRITE
    return effective_mode(tool, args or {}, schemas) in WRITE_MODES


def effective_mode(tool: str, args: dict, schemas: list[dict]) -> str:
    """工具调用的真实 mode：显式 mode 优先，否则取 schema default。

    v6 实测：模型给的 App 计划只有 name 没有 mode，但 schema default=launch，
    写操作识别漏判，导致"启动后复查"被重复动作闸门误拦。
    """
    m = str((args or {}).get("mode") or "")
    if m:
        return m
    sch = next((t.get("inputSchema") or {} for t in schemas if t["name"] == tool), {})
    return str(((sch.get("properties") or {}).get("mode") or {}).get("default") or "")


def sig_of(tool: str, args: dict) -> str:
    return tool + ":" + sha256(json.dumps(args, sort_keys=True, ensure_ascii=False))[:16]


# --------------------------------------------------------------------------- plan gate
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string", "description": "先用不超过80字说明拆解理由与条件分支"},
        "goal": {"type": "string"},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"}, "intent": {"type": "string"},
                "tool": {"type": "string"}, "args": {"type": "object"},
                "expect": {"type": "string"}, "on_fail": {"type": "string"}},
            "required": ["id", "intent", "tool", "args", "expect"]}}},
    "required": ["analysis", "goal", "success_criteria", "steps"]}


def tool_brief(schemas: list[dict]) -> str:
    """把真实 inputSchema 压成规划器能读的紧凑说明。"""
    lines = []
    for t in schemas:
        sch = t.get("inputSchema") or {}
        props = sch.get("properties") or {}
        req = sch.get("required") or []
        parts = []
        for k, v in props.items():
            tname = v.get("type") or "string"
            enum = v.get("enum")
            seg = f"{k}:{tname}"
            if enum:
                seg += "=" + "|".join(str(x) for x in enum[:24])
            if k in req:
                seg += "*"
            parts.append(seg)
        lines.append(f"- {t['name']}({', '.join(parts)})：{(t.get('description') or '')[:600]}")
    return "\n".join(lines)


def validate_plan(plan: dict, schemas: list[dict]) -> list[str]:
    v: list[str] = []
    if not isinstance(plan, dict):
        return ["计划不是 JSON 对象"]
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return ["steps 缺失或为空"]
    if len(steps) > MAX_STEPS:
        v.append(f"steps 数量 {len(steps)} 超过上限 {MAX_STEPS}")
    byname = {t["name"]: (t.get("inputSchema") or {}) for t in schemas}
    seen_write = False
    for i, st in enumerate(steps, 1):
        if not isinstance(st, dict):
            v.append(f"step{i} 不是对象")
            continue
        tool = st.get("tool")
        if tool not in byname:
            v.append(f"step{i}.tool={tool!r} 不在工具清单 {sorted(byname)}")
            continue
        if not str(st.get("expect") or "").strip():
            v.append(f"step{i} 缺少 expect（无法验收）")
        args = st.get("args") or {}
        if not isinstance(args, dict):
            v.append(f"step{i}.args 必须是对象")
            args = {}
        sch = byname[tool]
        props = sch.get("properties") or {}
        required = sch.get("required") or []
        for k in args:
            if props and k not in props:
                v.append(f"step{i}.args.{k} 不是 {tool} 的合法参数（合法：{sorted(props)}）")
        for k in required:
            if k not in args:
                v.append(f"step{i} 缺少 {tool} 必填参数 {k}")
        for k, val in args.items():
            enum = (props.get(k) or {}).get("enum")
            if enum and val not in enum and str(val) not in [str(x) for x in enum]:
                v.append(f"step{i}.args.{k}={val!r} 不在枚举 {enum} 内")
        mode = str(args.get("mode") or "")
        is_write = tool == "Process" and mode in WRITE_MODES
        is_write = is_write or (tool == "App" and mode in WRITE_MODES)
        if tool == "MagicHand" and str(args.get("action") or "") in MAGIC_WRITE:
            is_write = True
        if is_write:
            if not seen_write and i == 1:
                v.append(f"step{i} 第一步就是写操作（{tool}.{mode or args.get('action')}），必须先观察现状")
            seen_write = True
    bad_words = ("...", "…", "例如", "原文", "工具名", "参数", "xxx", "TODO")
    for field in ("goal",):
        val = str(plan.get(field) or "")
        if any(w in val for w in bad_words):
            v.append(f"{field}={val!r} 含模板占位符，必须写实际内容")
    crits = plan.get("success_criteria")
    if not crits:
        v.append("缺少 success_criteria（无法做最终验收）")
    elif not isinstance(crits, list):
        v.append("success_criteria 必须是数组")
    else:
        for j, c in enumerate(crits, 1):
            c = str(c)
            if len(c) < 8 or any(w in c for w in bad_words):
                v.append(f"success_criteria[{j}]={c!r} 不是可判定的具体标准")
        if len(crits) > 4:
            v.append("success_criteria 超过 4 条")
    return v


def coerce_arg(prop: dict, value):
    """按真实 JSON Schema(含 anyOf) 校验/归一化一个参数值。

    返回 (value, ok, note)：ok=False 表示无法安全转换，应由调用方丢弃该可选参数。
    """
    allowed = []
    for sub in (prop.get("anyOf") or [prop]):
        t = sub.get("type")
        if isinstance(t, list):
            allowed.extend(t)
        elif t:
            allowed.append(t)
        if t == "array" and sub.get("items"):
            allowed.append("array:" + str(sub["items"].get("type")))
    if not allowed:
        return value, True, ""
    vt = {"str": "string", "int": "integer", "float": "number",
          "bool": "boolean", "list": "array", "dict": "object"}.get(type(value).__name__, "?")
    if isinstance(value, bool):
        vt = "boolean"
    if vt in allowed:
        return value, True, ""
    # 字符串 -> 数字 / 布尔（模型常把 "true"/"640" 写成字符串）
    if isinstance(value, str):
        if "boolean" in allowed and value.lower() in ("true", "false"):
            return value.lower() == "true", True, f"字符串 {value!r} 归一化为布尔"
        if "integer" in allowed and re.fullmatch(r"-?\d+", value.strip()):
            return int(value.strip()), True, f"字符串 {value!r} 归一化为整数"
    # 无法安全转换：数组型参数收到一个描述性字符串（如 window_loc="centered"）
    if any(a.startswith("array") for a in allowed):
        return value, False, f"应为数组，实为 {type(value).__name__} {value!r}"
    if "null" in allowed:
        return None, True, "归一化为 null"
    return value, False, f"类型 {vt} 不在允许集合 {allowed}"


def sanitize_plan(plan: dict, schemas: list[dict]) -> tuple[dict, list[str]]:
    """确定性纠错：可选参数拼错/枚举越界时直接丢弃该参数，而不是废掉整个计划。

    只做"删掉多余/非法的可选项"这类无损修复；工具名、必填项、结构性问题仍交给 validate_plan 判红。
    """
    fixes: list[str] = []
    byname = {t["name"]: (t.get("inputSchema") or {}) for t in schemas}
    for i, st in enumerate(plan.get("steps") or [], 1):
        if not isinstance(st, dict) or st.get("tool") not in byname:
            continue
        sch = byname[st["tool"]]
        props = sch.get("properties") or {}
        required = set(sch.get("required") or [])
        args = st.get("args")
        if not isinstance(args, dict):
            st["args"] = {}
            fixes.append(f"step{i}.args 非对象，已置空")
            continue
        onfail = str(st.get("on_fail") or "")
        import re as _re
        m = _re.search(r"step[_ ]?(\d+)[_ ]*contains[_ ]*(\w+)", onfail, _re.I)
        if m and isinstance(st.get("skip_if"), dict) is False:
            st["skip_if"] = {"step": int(m.group(1)), "contains": m.group(2).strip()}
            fixes.append(f"step{i}: on_fail 字符串归一化为 skip_if={st['skip_if']}")
        for k in list(args):
            if props and k not in props and k not in required:
                del args[k]
                fixes.append(f"step{i}: 删除非法参数 {k}")
                continue
            prop = props.get(k) or {}
            if prop:
                val, ok, note = coerce_arg(prop, args[k])
                if not ok:
                    if k in required:
                        args[k] = prop.get("default") or (prop.get("enum") or [""])[0]
                        fixes.append(f"step{i}: 必填参数 {k} 类型非法，回退默认值；{note}")
                    else:
                        del args[k]
                        fixes.append(f"step{i}: 删除类型非法的可选参数 {k}；{note}")
                    continue
                if val != args[k]:
                    fixes.append(f"step{i}: {k} {note}")
                    args[k] = val
            enum = prop.get("enum")
            if enum and args[k] not in enum and str(args[k]) not in [str(x) for x in enum]:
                if k in required:
                    args[k] = enum[0]
                    fixes.append(f"step{i}: 必填枚举 {k} 归一化为 {enum[0]}")
                else:
                    bad = args.pop(k)
                    fixes.append(f"step{i}: 删除枚举越界的可选参数 {k}={bad!r}")
        for k in required:
            if k not in args:
                enum = (props.get(k) or {}).get("enum")
                args[k] = enum[0] if enum else ""
                fixes.append(f"step{i}: 补齐缺失必填参数 {k}={args[k]!r}")
    return plan, fixes


def plan_stage(client, schemas: list[dict], task: str, env_facts: str,
               model: str) -> dict:
    brief = tool_brief(schemas)
    brief = "\n".join(line[:260] for line in brief.splitlines())
    sys_p = """你是 Windows 自动化规划器，只做规划，不执行。
把任务拆成最少的可验证步骤，每步必须由一次工具调用完成，并写清成功时可观察到的具体现象。
硬规则：
1. 只能用给定工具与给定参数名，参数名必须逐字来自括号里的清单，禁止自造（例如没有 executable_path 这个参数）。
2. 任何写操作（App.launch / Process.stop 等）之前必须有一、步先查询现状的观察步。
3. 条件分支不许写在一句话里；需要跳过某步时，用 skip_if:{"step":<观察步id>,"contains":"<该出现/不该出现的字>"} 表达。
4. 步数 1-6，能合并就合并。
5. 在 analysis 字段写拆解理由，goal / success_criteria 必须写实际内容，禁止占位符。
6. 条件跳过写进 on_fail，格式为 skip_if_step_1_contains_ugraf（表示第1步观察含 ugraf 则跳过本步）。"""
    msg = [{"role": "system", "content": sys_p},
           {"role": "user", "content": f"可用工具（参数清单来自真实 schema，* 为必填）：\n{brief}\n\n环境事实：\n{env_facts}\n\n任务：{task}"}]
    # 语法约束解码：结构化 JSON 由 Ollama grammar 保证，不再依赖模型自由生成括号嵌套
    resp, el = chat(model, msg, think=False, num_predict=800, num_ctx=3072,
                    temperature=0.2, format_schema=PLAN_SCHEMA)
    content = (resp.get("message") or {}).get("content") or ""
    thinking = (resp.get("message") or {}).get("thinking") or ""
    # 底层错误（超时 / HTTP）不能被伪装成"模型 JSON 写错了"，否则 RCFA 会指错方向
    if resp.get("error"):
        return {"stage": "plan", "used": "call_error",
                "elapsed_s": el, "parse_mode": "failed", "plan": None,
                "call_error": resp["error"],
                "violations": [f"模型调用失败: {resp['error']}"],
                "valid": False, "deterministic_fixes": [],
                "thinking_chars": len(thinking), "raw_content": content[:4000],
                "analysis": None, "decoding": "ollama_format_json_schema"}
    plan, how = parse_json_loose(content)
    viol = validate_plan(plan, schemas) if plan else ["JSON 语法错误，无法解析；请输出完整且合法的 JSON（检查引号、冒号、逗号）"]
    fixes = []
    if plan:
        plan, fixes = sanitize_plan(plan, schemas)
        viol = validate_plan(plan, schemas)
    out = {"stage": "plan", "elapsed_s": el, "parse_mode": how, "plan": plan,
           "deterministic_fixes": fixes,
           "call_error": resp.get("error"),
           "violations": viol, "valid": not viol,
           "thinking_chars": len(thinking), "raw_content": content[:4000],
           "native_thinking": thinking[:3000],
           "analysis": (plan or {}).get("analysis"),
           "decoding": "ollama_format_json_schema"}
    # 返修 1 次：把违规清单原样回喂，要求只改违规点
    if viol and not resp.get("error"):
        fix_msg = msg + [
            {"role": "assistant", "content": content[:3000]},
            {"role": "user", "content": "你的计划未通过校验，逐条修正后只输出修正版 JSON：\n- "
                                        + "\n- ".join(viol)}]
        resp2, el2 = chat(model, fix_msg, think=False, num_predict=800, num_ctx=3072,
                          temperature=0.1, format_schema=PLAN_SCHEMA)
        c2 = (resp2.get("message") or {}).get("content") or ""
        plan2, how2 = parse_json_loose(c2)
        fixes2 = []
        if plan2:
            plan2, fixes2 = sanitize_plan(plan2, schemas)
        viol2 = validate_plan(plan2, schemas) if plan2 else ["返修后仍无法解析"]
        out["repair"] = {"elapsed_s": el2, "parse_mode": how2, "plan": plan2,
                         "deterministic_fixes": fixes2,
                         "violations": viol2, "valid": not viol2, "raw_content": c2[:4000]}
        if not viol2:
            out["plan"], out["violations"], out["valid"] = plan2, [], True
            out["used"] = "repair"
        else:
            out["used"] = "original_broken"
    else:
        out["used"] = "original"
    return out


# --------------------------------------------------------------------------- act stage
def act_stage(client, schemas: list[dict], tools_ollama: list[dict], plan: dict,
              step: dict, history: list[dict], task: str, model: str) -> dict:
    def fmt_obs(h):
        return f"[step{h['step']}] {h['tool']}{json.dumps(h['args'], ensure_ascii=False)} -> {h['observation'][:700]}"

    obs_txt = "\n".join(fmt_obs(h) for h in history) or "（还没有任何观察）"
    sch = next((t.get("inputSchema") or {} for t in schemas if t["name"] == step["tool"]), {})
    sys_p = f"""你在执行一个已经定好的计划的第 {step['id']} 步。
当前步意图：{step['intent']}
本步应使用工具：{step['tool']}，参数必须符合：{json.dumps(sch, ensure_ascii=False)[:800]}
本步成功标志：{step['expect']}

输出要求（严格两段）：
第一行必须是核对结论，格式：检查：<met|not_met|first>｜证据：<从上面的观察里原样摘录的片段>
  · met=上一步达到预期；not_met=没达到；first=仅第 1 步可用（后续步骤禁用）。
  · 证据必须逐字来自观察文本，禁止改写、禁止编造；first 时证据写 无。
第二段如需补充可直接发起工具调用；不发起也没关系，执行器会严格按计划调用工具。不要再写解释文字。"""
    msg = [{"role": "system", "content": sys_p},
           {"role": "user", "content": f"总任务：{task}\n\n已有观察：\n{obs_txt}\n\n现在执行第 {step['id']} 步。"}]
    resp, el = chat(model, msg, tools_ollama, think=False, num_predict=180, temperature=0.1)
    msgobj = resp.get("message") or {}
    content = msgobj.get("content") or ""
    calls = msgobj.get("tool_calls") or []
    check = None
    m = re.search(r"检查[:：]\s*(met|not_met|first)\s*[｜|]\s*证据[:：]\s*(.*)", content)
    if m:
        check = {"verdict": m.group(1), "cited": m.group(2).strip()[:200]}
    return {"stage": "act", "elapsed_s": el, "content": content[:1500],
            "check": check, "tool_calls": calls, "error": resp.get("error")}


def judge_evidence(check: dict | None, last_obs: str, allow_first: bool = True) -> dict:
    """机械核对：模型引用的证据片段必须真的出现在上一步观察里。"""
    if check and check["verdict"] == "first" and not allow_first:
        return {"applicable": True, "cited_ok": False,
                "reason": "first_used_after_step1（用 first 逃避证据核对）"}
    if not check or check["verdict"] == "first" or not last_obs:
        return {"applicable": False, "cited_ok": None}
    cited = check["cited"]
    if cited in ("无", "none", "N/A", ""):
        return {"applicable": True, "cited_ok": False, "reason": "empty_citation"}
    norm = lambda s: re.sub(r"\s+", "", s).lower()
    ok = norm(cited[:80]) in norm(last_obs)
    return {"applicable": True, "cited_ok": ok,
            "reason": "substring_hit" if ok else "citation_not_in_observation"}


def mechanical_check(step: dict, history: list[dict]) -> dict:
    """确定性执行期核对：从 expect 抽关键词，在上一步观察里找逐字命中。

    取代让 13.63B 临场引用观察原文（v5 实测 4/5 步引用了不存在的片段）。
    """
    if not history:
        return {"verdict": "first", "cited": "无"}
    last = history[-1]["observation"]
    expect = str(step.get("expect") or "")
    toks = re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]{2,}", expect)
    hit = [t for t in toks if t.lower() in last.lower()]
    return {"verdict": "met" if hit else "not_met",
            "cited": hit[0] if hit else last[:60].strip(),
            "expect_keywords": toks[:8]}


def verify_stage(model: str, task: str, criteria: list, history: list[dict]) -> dict:
    # 长工具输出（如 HWND 树）里的关键行常在尾部，只给头部会让验收看不到证据。
    # 按 criteria 关键词做确定性命中摘要，把关键行送到模型面前。
    kws = set()
    for c in criteria:
        for w in re.findall(r"[A-Za-z0-9_.]{4,}|[\u4e00-\u9fff]{3,}", str(c)):
            kws.add(w.lower())
    kws = list(kws)[:20]
    hit_lines = []
    for h in history:
        for line in h["observation"].splitlines():
            if line.strip() and any(k in line.lower() for k in kws) and len(hit_lines) < 14:
                hit_lines.append(f"[{h['step']}] {line.strip()[:160]}")
    obs = "\n".join(f"[{h['step']}] {h['observation'][:300]}" for h in history)
    if hit_lines:
        obs += "\n\n关键命中行（优先作为 evidence 逐字引用）：\n" + "\n".join(hit_lines)
    sys_p = """你是验收员。逐条判断 success_criteria 是否被证据支持。
只输出 JSON：{"items":[{"criterion":"原文","met":"yes|no|unknown","evidence":"逐字摘录的观察片段"}]}
规则：
1. evidence 必须是下面观察文本里逐字出现的片段，且**不超过 40 个字**，禁止复制整段输出、禁止转义引号。
2. 找不到证据就 met=unknown，绝不允许凭推测判 yes。
3. 只输出 JSON 对象，不要 markdown 代码块，不要解释。"""
    msg = [{"role": "system", "content": sys_p},
           {"role": "user", "content": f"任务：{task}\n\n验收标准：\n" + "\n".join(f"- {c}" for c in criteria) + f"\n\n观察记录：\n{obs or '（无）'}"}]
    resp, el = chat(model, msg, think=False, num_predict=500, temperature=0.0)
    content = (resp.get("message") or {}).get("content") or ""
    data, how = parse_json_loose(content)
    items = [(data or {}).get("items") or []][0]
    items = list(items)[:len(criteria)]        # 丢弃模型多吐的模板项
    while len(items) < len(criteria):          # 缺项按 unknown 补齐，不空转
        items.append({"criterion": criteria[len(items)], "met": "unknown", "evidence": ""})
    norm = lambda s: re.sub(r"\s+", "", s).lower()
    for i, it in enumerate(items):
        it["criterion"] = criteria[i]          # 权威来自计划，覆盖模型照抄的模板文字
    for it in items:
        ev = str(it.get("evidence") or "")
        hit = bool(ev) and norm(ev[:80]) in norm(obs)
        generic = bool(re.fullmatch(r"processes\s*\(\d+\s*shown\)\s*:?", ev.strip(), re.I)) \
            or len(ev.strip()) < 12
        it["evidence_hit"] = hit
        it["generic_evidence"] = generic
        if it.get("met") == "yes" and (not hit or generic):
            it["met"] = "unsupported"      # 无原文 / 只引用表头 -> 不算通过
    return {"stage": "verify", "elapsed_s": el, "parse_mode": how,
            "items": items, "raw_content": content[:1500]}


# --------------------------------------------------------------------------- orchestrator
def run(task: str, model: str = DEFAULT_MODEL, tools_whitelist: str = DEFAULT_TOOLS,
        env_facts: str = "", out_dir: Path | None = None,
        use_act_model: bool = False, plan_cache: str | None = None,
        skill_only: bool = False, actions: str | None = None) -> dict:
    if skill_only and MagicHandAdapter is None:
        raise RuntimeError("magic_hand_adapter 不可用，无法启用 --skill-only")
    client = None if skill_only else WindowsMCPClient(tools_whitelist)
    adapter = MagicHandAdapter(out_dir) if skill_only else None
    trace = {"task": task, "model": model, "basis": "measured", "env_facts": env_facts,
             "tool_source": "magic-hand-windows skill" if skill_only else "windows-mcp",
             "execution_mode": "plan_driven_deterministic" if not use_act_model else "model_per_step",
             "guards": [], "steps": [], "history": []}
    t_start = time.time()
    consecutive_fail = 0
    replans = 0
    sig_seen: dict[str, int] = {}
    write_counter = 0
    try:
        if skill_only:
            schemas = (slim_schemas([a.strip() for a in actions.split(",") if a.strip()])
                       if actions else adapter.schemas())
            tools_ollama = mcp_to_ollama_tools(schemas)
            trace.update({
                "run_id": sha256(f"{task}|{model}|{json.dumps(schemas, sort_keys=True)}|{time.time()}")[:16],
                "skill": "magic-hand-windows", "skill_scripts_dir": str(SCRIPTS),
                "mcp_server": None, "server_argv": None,
                "mcp_tools": [t["name"] for t in schemas],
                "ollama_tools_count": len(tools_ollama),
                "protocol": "skill-cli"})
            print(f"[deep] 工具源 = magic-hand-windows skill，工具 {[t['name'] for t in schemas]}",
                  flush=True)
        else:
            init = client.start()
            schemas = client.list_tools()
            tools_ollama = mcp_to_ollama_tools(schemas)
            trace.update({
                "run_id": sha256(f"{task}|{model}|{json.dumps(schemas, sort_keys=True)}|{time.time()}")[:16],
                "mcp_server": client.server_info, "server_argv": client.argv,
                "mcp_tools": [t["name"] for t in schemas],
                "ollama_tools_count": len(tools_ollama),
                "protocol": (init.get("result") or {}).get("protocolVersion")})
        if not schemas:
            raise RuntimeError("tools/list 为空，闸门判红")

        if plan_cache and Path(plan_cache).is_file():
            cached = json.loads(Path(plan_cache).read_text(encoding="utf-8"))
            cached_plan = cached.get("plan") if isinstance(cached, dict) and "plan" in cached else cached
            cp, fixes = sanitize_plan(cached_plan, schemas)
            cv = validate_plan(cp, schemas)
            print(f"[deep] P 复用缓存计划 {Path(plan_cache).name} valid={not cv} "
                  f"steps={len(cp.get('steps') or [])} fixes={len(fixes)}", flush=True)
            p = {"stage": "plan", "used": "cache", "plan": cp, "violations": cv,
                 "valid": not cv, "deterministic_fixes": fixes,
                 "analysis": cp.get("analysis"), "decoding": "cached_from_previous_model_run",
                 "elapsed_s": 0.0,
                 "plan_sha256": sha256(json.dumps(cp, sort_keys=True, ensure_ascii=False))}
        else:
            print("[deep] P 规划中 ...", flush=True)
            p = plan_stage(client, schemas, task, env_facts, model)
        trace["plan_stage"] = p
        plan = p["plan"] or {}
        steps = plan.get("steps") or []
        trace["plan_valid"] = p["valid"]
        trace["plan_steps"] = len(steps)
        print(f"[deep] P 完成 valid={p['valid']} used={p['used']} "
              f"steps={len(steps)} violations={p['violations'][:3]} "
              f"elapsed={p['elapsed_s']}s", flush=True)

        for step in steps:
            if consecutive_fail >= 3:
                trace["aborted"] = "circuit_breaker_3_consecutive_failures"
                break
            # 机械条件跳过：skip_if 命中则不执行（不是靠模型记忆）
            skip_if = step.get("skip_if")
            if isinstance(skip_if, dict):
                sid, key = skip_if.get("step"), str(skip_if.get("contains") or "")
                prev = next((h for h in trace["history"] if h["step"] == sid), None)
                if prev and key and key.lower() in prev["observation"].lower():
                    trace["steps"].append({"step": step["id"], "skipped": True,
                                           "why": f"skip_if 命中 step{sid} 含 {key!r}"})
                    continue
            # 计划即契约：执行完全按已通过校验的计划走，不再依赖模型临场是否吐出 tool_call。
            # 模型在这一步的职责只剩"读懂上一步观察"，避免 13.63B 偶发不发调用就整步作废。
            if use_act_model:
                a = act_stage(client, schemas, tools_ollama, plan, step,
                              trace["history"], task, model)
            else:
                chk = mechanical_check(step, trace["history"])
                a = {"stage": "act", "elapsed_s": 0.0,
                     "content": f"检查:{chk['verdict']}｜证据：{chk['cited']}",
                     "check": chk, "tool_calls": [], "error": None,
                     "mode": "deterministic"}
            name = step["tool"]
            args = dict(step.get("args") or {})
            last_obs = trace["history"][-1]["observation"] if trace["history"] else ""
            rec = {"step": step["id"], "attempt": 1, "intent": step["intent"],
                   "planned_tool": name, "planned_args": args, "act": a,
                   "judge": judge_evidence(a["check"], last_obs,
                                           allow_first=(len(trace["history"]) == 0))}
            proposed = a["tool_calls"][0] if a["tool_calls"] else None
            if proposed:
                fn = proposed.get("function") or {}
                pargs = fn.get("arguments") or {}
                if isinstance(pargs, str):
                    try:
                        pargs = json.loads(pargs)
                    except Exception:
                        pargs = {"_raw": pargs}
                rec["proposed_call"] = {"tool": fn.get("name"), "args": pargs}
                if fn.get("name") != name or any(pargs.get(k) != v for k, v in args.items()):
                    rec["contract_deviation_corrected"] = True
                    trace["guards"].append({"guard": "contract_override", "step": step["id"],
                                            "proposed": rec["proposed_call"],
                                            "enforced": {"tool": name, "args": args}})
            sig = sig_of(name, args)
            is_write = is_write_action(name, args, schemas)
            planned_write = any(is_write_action(st.get("tool", ""), st.get("args") or {}, schemas)
                                for st in steps if st.get("tool") == name)
            # 闸门 1：计划外的写操作，拒绝
            if is_write and not planned_write:
                rec.update({"outcome": "blocked_write_not_in_plan", "tool": name, "args": args})
                trace["guards"].append({"guard": "unplanned_write", "step": step["id"],
                                        "tool": name, "args": args})
                trace["steps"].append(rec)
                consecutive_fail += 1
                continue
            # 闸门 2：重复动作拦截。例外：两次相同观察之间发生过写操作 => 属于合法的"动作前后对照"
            if sig in sig_seen and write_counter <= sig_seen[sig]:
                rec.update({"outcome": "blocked_duplicate_action", "tool": name, "args": args})
                trace["guards"].append({"guard": "duplicate_action", "step": step["id"],
                                        "sig": sig, "tool": name, "args": args})
                trace["steps"].append(rec)
                consecutive_fail += 1
                continue
            sig_seen[sig] = write_counter
            t0 = time.time()
            out = adapter.call(name, args) if skill_only else client.call_tool(name, args)
            if is_write:
                write_counter += 1
            rec.update({"outcome": "executed", "tool": name, "args": args,
                        "exec_s": round(time.time() - t0, 2), "is_error": out["is_error"],
                        "impl": out.get("impl"), "skill_argv": out.get("argv"),
                        "observation": out["text"][:2500]})
            trace["history"].append({"step": step["id"], "tool": name, "args": args,
                                     "observation": out["text"][:2500]})
            trace["steps"].append(rec)
            print(f"[deep] A step{step['id']}: {name}{json.dumps(args, ensure_ascii=False)[:90]}"
                  f" -> {out['text'][:110]!r}", flush=True)
            consecutive_fail = 0
        # ---- verify
        print("[deep] V 验收中 ...", flush=True)
        criteria = plan.get("success_criteria") or []
        trace["verify"] = verify_stage(model, task, criteria, trace["history"]) if criteria else {"items": []}
        print(f"[deep] V 完成 items={len(trace['verify'].get('items') or [])}", flush=True)
        items = trace["verify"].get("items") or []
        trace["criteria_met"] = sum(1 for i in items if i.get("met") == "yes")
        trace["criteria_total"] = len(items)
        trace["criteria_unsupported"] = sum(1 for i in items if i.get("met") in ("unsupported", "unknown"))
        trace["success"] = bool(items) and trace["criteria_met"] == len(items) and trace.get("plan_valid")
        # ---- 反穷举指标
        executed = [s for s in trace["steps"] if s.get("outcome") == "executed"]
        trace["metrics"] = {
            "wall_s": round(time.time() - t_start, 1),
            "planned_steps": len(steps),
            "executed_calls": len(executed),
            "unique_actions": len({sig_of(s["tool"], s["args"]) for s in executed}),
            "blocked_duplicates": sum(1 for g in trace["guards"] if g["guard"] == "duplicate_action"),
            "blocked_unplanned_writes": sum(1 for g in trace["guards"] if g["guard"] == "unplanned_write"),
            "tool_deviations": sum(1 for s in executed if s.get("tool") != s.get("planned_tool")),
            "hallucinated_evidence": sum(1 for s in trace["steps"]
                                         if s.get("judge", {}).get("cited_ok") is False),
            "check_lines_present": sum(1 for s in trace["steps"] if s.get("act", {}).get("check")),
            "check_evidence_applied": sum(1 for s in trace["steps"] if s.get("judge", {}).get("applicable")),
            "check_invalid": sum(1 for s in trace["steps"]
                                 if s.get("judge", {}).get("cited_ok") is False),
        }
        trace["brute_force_index"] = round(
            trace["metrics"]["executed_calls"] / max(1, trace["metrics"]["unique_actions"]), 3)
        return trace
    finally:
        if adapter is not None:
            trace["clipboard_restored"] = adapter.restore()
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "skill_calls.json").write_text(
                    json.dumps(adapter.calls, ensure_ascii=False, indent=2), encoding="utf-8")
        if client is not None:
            client.close()
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "deep_agent_trace.json").write_text(
                json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--tools", default=DEFAULT_TOOLS)
    ap.add_argument("--env-facts", default="")
    ap.add_argument("--out", default=str(ROOT / "runs" / "deep_agent_last"))
    ap.add_argument("--act-model", action="store_true",
                    help="让模型逐步写核对结论（默认关闭：执行完全由计划驱动）")
    ap.add_argument("--plan-cache", default=None,
                    help="复用前一轮模型真实产出的计划 JSON，跳过规划阶段")
    ap.add_argument("--skill-only", action="store_true",
                    help="工具源只来自 magic-hand-windows skill（不启动 windows-mcp）")
    ap.add_argument("--actions", default=None,
                    help="逗号分隔的 action 白名单：按任务裁剪工具面，避免 13.63B 在大 schema 下超时")
    a = ap.parse_args()
    tr = run(a.task, a.model, a.tools, a.env_facts, Path(a.out), a.act_model,
             a.plan_cache, a.skill_only, a.actions)
    print(json.dumps({"run_id": tr.get("run_id"), "plan_valid": tr.get("plan_valid"),
                      "plan": tr.get("plan_stage", {}).get("plan"),
                      "steps": [{"step": s.get("step"), "outcome": s.get("outcome"),
                                 "tool": s.get("tool"), "args": s.get("args"),
                                 "judge": s.get("judge"),
                                 "obs": (s.get("observation") or "")[:200]} for s in tr["steps"]],
                      "metrics": tr.get("metrics"), "verify": tr.get("verify", {}).get("items"),
                      "success": tr.get("success")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
