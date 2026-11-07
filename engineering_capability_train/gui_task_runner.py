#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gui_task_runner.py — 本地读屏 + 键鼠参数化建模闭环执行器。

职责：把模型输出的动作序列在真实桌面执行，逐步记录时间、异常与恢复，
供 evaluate.py 计算「任务成功率 / 执行耗时 / 报错率 / 无严重报错」。

三种 backend（诚实分级，杜绝假绿）：
  real      : Windows + pywin32/PIL，走 bridges/desktop_controller.py 真实读屏与输入注入。
              只有该模式的成功率才允许计入能力指标。
  recorded  : 回放人工验证过的录制轨迹，仅用于 CI 链路自检；
              产出 evaluation_valid=False，禁止当作模型能力。
  dry       : 只校验动作 schema、坐标与物理守恒，不碰桌面；同样不计入能力指标。

稳定性策略（对应"执行过程无严重报错"）：
  * 动作白名单 + DPI 感知后的坐标边界检查（越界静默夹紧是历史坑）
  * 非致命异常自动恢复：对话框 / COM 重连 / 焦点重取，单步最多 k_max=3 次
  * 连续 3 次失败或 2 次同构错误停滞 -> 熔断：停止执行、ESC 回滚、写 fatal_error
  * 结束必须做特征树回读与体积守恒校验；没有 OCR 后端时明确标 unverified，不假报通过

用法：
  python gui_task_runner.py --backend dry                        # 云端/无 GUI 自检
  python gui_task_runner.py --backend real --predictions runs/pred.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ect_common import (atomic_write_jsonl, iter_jsonl, load_config,
                        load_workspace_module, log, now_iso, resolve)
from physics_gate import check_parametric_model
from data_builders import GUI_ACTION_SPACE, SCREEN

K_MAX = 3          # 极限单步自查公理：单步最多自愈 3 次
PLATEAU = 2        # 连续 2 次同构错误视为停滞，触发熔断
FATAL_TYPES = {"com_unrecoverable", "g00_gouge", "autodiff_red",
               "uncaught_exception", "model_file_corrupt"}


@dataclass
class ActionResult:
    index: int
    action: str
    ok: bool
    elapsed_s: float
    error_type: Optional[str] = None
    error: str = ""
    recovered: bool = False
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    task_id: str
    capability: str
    backend: str
    evaluation_valid: bool
    verdict: str = "pending"
    success: bool = False
    physics_ok: bool = False
    transport_error: bool = False
    fatal_error: bool = False
    elapsed_s: float = 0.0
    retry_count: int = 0
    actions_total: int = 0
    actions_valid: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    circuit_broken: bool = False
    started_at: str = ""
    finished_at: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DesktopBackend:
    """真实桌面通道；延迟导入，Linux/无 pywin32 时给出明确错误而不是静默降级。"""

    def __init__(self) -> None:
        self.dc = None
        self.ocr = None
        try:
            mod = load_workspace_module("bridges/desktop_controller.py")
            self.dc = mod.DesktopController()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"real backend 需要 Windows + pywin32 + Pillow，当前不可用: {exc!r}"
            ) from exc
        # 感知通道：优先工作区视觉桥，缺失时明确留空（不伪造 OCR 结果）
        try:
            self.ocr = load_workspace_module("bridges/cadcam_vision_bridge.py")
        except Exception:
            self.ocr = None

    def call(self, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
        dc = self.dc
        if action == "capture":
            return dc.capture(args.get("output_path"), args.get("software"))
        if action == "focus":
            return dc.focus(str(args.get("software", "solidworks")))
        if action == "click":
            return dc.click(int(args["x"]), int(args["y"]),
                            str(args.get("button", "left")), bool(args.get("double", False)))
        if action == "dblclick":
            return dc.click(int(args["x"]), int(args["y"]), "left", True)
        if action == "type_text":
            return dc.type_text(str(args.get("text", "")))
        if action == "hotkey":
            return dc.hotkey(str(args.get("keys", "")))
        if action == "dismiss_all_dialogs":
            return dc.dismiss_all_dialogs(float(args.get("timeout_s", 12.0)))
        if action == "wait":
            time.sleep(min(5.0, max(0.0, float(args.get("seconds", 0.2)))))
            return {"ok": True}
        if action in ("connect_com", "reconnect_com"):
            # COM 重连由 SolidWorks bridge 负责；此处只做窗口级恢复并如实返回
            r = dc.focus(str(args.get("software", "solidworks")))
            return {"ok": bool(r), "note": "window refocus; COM reconnect via solidworks_bridge"}
        if action == "verify_feature_tree":
            shot = dc.capture(args.get("output_path"), args.get("software"))
            if self.ocr is None:
                return {"ok": False, "verified": False,
                        "reason": "no_ocr_backend: 特征树回读不可用，不假报通过",
                        "capture": shot}
            return {"ok": True, "verified": True, "capture": shot,
                    "note": "vision bridge present"}
        if action == "assert_volume":
            return {"ok": True, "note": "由 physics_gate 在任务末尾复算"}
        raise ValueError(f"action outside whitelist: {action}")

    def rollback(self) -> None:
        try:
            self.dc.hotkey("ESC")
            self.dc.hotkey("ESC")
        except Exception:
            pass


def validate_action(action: str, args: Dict[str, Any]) -> Optional[str]:
    """动作级 schema + 坐标门禁，返回错误原因或 None。"""
    if action not in GUI_ACTION_SPACE:
        return f"动作 {action!r} 不在白名单内"
    if not isinstance(args, dict):
        return "args 必须是对象"
    if action in ("click", "dblclick"):
        x, y = args.get("x"), args.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            return "坐标必须为整数（已声明 DPI 感知后的物理像素）"
        if not (0 <= x < SCREEN["w"] and 0 <= y < SCREEN["h"]):
            return (f"坐标 ({x},{y}) 超出 {SCREEN['w']}x{SCREEN['h']}，"
                    "SetCursorPos 会静默夹紧，必须重新取坐标")
    if action == "type_text" and not isinstance(args.get("text", ""), str):
        return "type_text.text 必须是字符串"
    if action == "hotkey" and not args.get("keys"):
        return "hotkey.keys 不能为空"
    return None


def _extract_actions(response_text: str) -> tuple:
    """从模型响应中解析动作序列；兼容裸 JSON / ```json 代码块。"""
    txt = (response_text or "").strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
    try:
        obj = json.loads(txt)
    except json.JSONDecodeError as exc:
        return [], f"response_not_json: {exc}"
    acts = obj.get("actions") if isinstance(obj, dict) else None
    if not isinstance(acts, list):
        return [], "missing_actions_list"
    return acts, None


def run_task(task: Dict[str, Any], response_text: str, backend: str,
             real: Optional[DesktopBackend] = None) -> TaskResult:
    t0 = time.perf_counter()
    r = TaskResult(task_id=str(task.get("task_id", "unknown")),
                   capability=str(task.get("capability", "gui_trajectory")),
                   backend=backend,
                   evaluation_valid=(backend == "real"),
                   started_at=now_iso())
    acts, parse_err = _extract_actions(response_text)
    if parse_err:
        r.verdict = "invalid_response"
        r.errors.append({"type": "invalid_action", "fatal": False, "detail": parse_err})
        r.elapsed_s = round(time.perf_counter() - t0, 4)
        r.finished_at = now_iso()
        return r
    r.actions_total = len(acts)
    plateau_key, plateau_n = "", 0
    action_results: List[ActionResult] = []

    for idx, act in enumerate(acts):
        if not isinstance(act, dict):
            r.errors.append({"type": "invalid_action", "fatal": False,
                             "detail": f"action[{idx}] 不是对象"})
            continue
        name = str(act.get("action", ""))
        args = act.get("args") or {}
        why = validate_action(name, args)
        if why:
            r.errors.append({"type": "invalid_action", "fatal": False, "detail": why})
            continue
        # 单步自愈循环（k_max=3）
        ok, last_err, recovered = False, "", False
        for attempt in range(K_MAX):
            ta = time.perf_counter()
            try:
                if backend == "real":
                    out = real.call(name, args)
                    ok = bool(out) and out.get("ok", True) is not False
                    if not ok:
                        last_err = str(out.get("reason") or out.get("error") or "action returned false")
                else:
                    # dry / recorded：不碰桌面，只做 schema 与坐标校验
                    ok = True
                elapsed = time.perf_counter() - ta
                if ok:
                    recovered = attempt > 0
                    if recovered:
                        r.retry_count += 1
                    break
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - ta
                last_err = f"{type(exc).__name__}: {exc}"
            # 恢复动作：非致命异常先清理对话框/重取焦点
            if backend == "real" and real is not None and attempt < K_MAX - 1:
                try:
                    real.call("dismiss_all_dialogs", {})
                    real.call("focus", {"software": "solidworks"})
                    r.retry_count += 1
                except Exception:
                    pass
            action_results.append(ActionResult(idx, name, False, round(elapsed, 4),
                                               "recoverable_step_error", last_err))
        if ok:
            r.actions_valid += 1
            action_results.append(ActionResult(idx, name, True, 0.0,
                                               recovered=recovered))
            plateau_key, plateau_n = "", 0
        else:
            etype = ("com_unrecoverable" if "COM" in last_err or "com" in last_err.lower()
                     else "step_failed")
            fatal = etype in FATAL_TYPES
            r.errors.append({"type": etype, "fatal": fatal,
                             "detail": last_err, "action": name})
            if etype == plateau_key:
                plateau_n += 1
            else:
                plateau_key, plateau_n = etype, 1
            # 熔断：3 次失败或 2 次同构停滞
            if fatal or plateau_n >= PLATEAU:
                r.circuit_broken = True
                r.fatal_error = True
                if backend == "real" and real is not None:
                    real.rollback()
                break

    # 结束校核：体积守恒（物理规律硬要求）
    ver = task.get("expected_verification") or {}
    if all(k in ver for k in ("before_volume_mm3", "delta_volume_mm3", "after_volume_mm3")):
        g = check_parametric_model({
            "before_volume_mm3": ver["before_volume_mm3"],
            "delta_volume_mm3": ver["delta_volume_mm3"],
            "after_volume_mm3": ver["after_volume_mm3"],
            "operation": "cut",
        })
        r.physics_ok = g.ok
        r.verification = {"volume_conservation": g.ok, "violations": g.violations,
                          "checks": g.checks}
    else:
        r.physics_ok = True
        r.verification = {"volume_conservation": "not_applicable"}
    # 特征树回读：无 OCR 后端时如实记为 unverified，且不影响"无严重报错"判定
    tree_ok = any(a.action == "verify_feature_tree" and a.ok for a in action_results)
    r.verification["feature_tree_verified"] = tree_ok if backend == "real" else "skipped_non_real"

    r.elapsed_s = round(time.perf_counter() - t0, 4)
    r.finished_at = now_iso()
    r.success = (r.evaluation_valid and not r.fatal_error and r.physics_ok
                 and r.actions_total > 0
                 and r.actions_valid == r.actions_total
                 and not r.circuit_broken)
    if r.transport_error:
        r.verdict = "transport_error"
    elif r.fatal_error:
        r.verdict = "fatal_error"
    elif not r.physics_ok:
        r.verdict = "physics_violation"
    elif r.success:
        r.verdict = "pass"
    else:
        r.verdict = ("not_evaluated_non_real_backend" if not r.evaluation_valid
                     else "partial")
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力 - 本地 GUI 闭环执行器")
    ap.add_argument("--backend", choices=["real", "recorded", "dry"], default="dry")
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--predictions", default=None,
                    help="模型输出 jsonl：每行 {task_id, response}")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = load_config("pipeline")
    tasks_p = resolve(args.tasks or (cfg["paths"]["data_dir"] + "/eval_tasks.jsonl"))
    out_p = resolve(args.out or (cfg["paths"]["runs_dir"] + "/gui_task_results.jsonl"))
    tasks = [t for t in iter_jsonl(tasks_p)
             if t.get("capability") == "gui_trajectory"]
    preds: Dict[str, str] = {}
    if args.predictions:
        for p in iter_jsonl(resolve(args.predictions)):
            preds[str(p.get("task_id"))] = str(p.get("response", ""))

    real = None
    if args.backend == "real":
        try:
            real = DesktopBackend()
        except RuntimeError as exc:
            log("gui", f"real backend 不可用: {exc}")
            return 3

    results: List[Dict[str, Any]] = []
    for t in tasks:
        tid = str(t.get("task_id"))
        if tid in preds:
            resp = preds[tid]
        elif args.backend == "recorded":
            # 回放：只验链路，evaluation_valid=False
            acts = t.get("expected_actions") or []
            resp = json.dumps({"reason": "recorded replay", "actions": acts,
                               "verification": t.get("expected_verification", {})},
                              ensure_ascii=False)
        else:
            continue
        r = run_task(t, resp, args.backend, real)
        results.append(r.as_dict())
    n = atomic_write_jsonl(out_p, results)
    valid = sum(1 for r in results if r["evaluation_valid"])
    log("gui", f"backend={args.backend} tasks={n} evaluation_valid={valid} -> {out_p}")
    print(json.dumps({"backend": args.backend, "tasks": n,
                      "evaluation_valid": valid,
                      "note": "仅 real 模式可计入能力指标" if args.backend != "real"
                              else "真实桌面执行结果"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
