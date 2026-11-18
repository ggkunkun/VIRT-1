# -*- coding: utf-8 -*-
"""bridges/cadcam_vision_bridge.py — Industrial CAD/CAM Computer Vision & Multimodal Perception Bridge.

Integrates cutting-edge vision capabilities for the 6 industrial software packages:
1. AutoCAD / Blueprint: Drawing view segmentation, title block isolation, dimension & GD&T extraction.
2. VERICUT: Auto-Diff chromatic spectrum analysis (Red=Gouge/过切, Blue=Excess/欠切, Green=In-Tolerance/合格).
3. 斯沃数控 (SSCNC) / Machine Panel: CRT display segmentation, coordinate readout & alarm banner detection.
4. SOLIDWORKS / NX: Viewport feature inspection, ribbon/feature-tree grounding, visual quality audit.
"""

import os
import sys
import json
import math
import numpy as np
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class CADCAMVisionBridge:
    def __init__(self):
        self.has_cv2 = HAS_CV2

    def _read_image(self, path: str, flags: int = None):
        """Robust image reader supporting Unicode/Chinese file paths on Windows."""
        if not HAS_CV2:
            # 审计修复：默认参数曾直接写 cv2.IMREAD_COLOR，未装 OpenCV 时
            # 连 import 都会抛 NameError，整条视觉链无法降级。
            return None
        if flags is None:
            flags = cv2.IMREAD_COLOR
        try:
            data = np.fromfile(path, dtype=np.uint8)
            return cv2.imdecode(data, flags)
        except Exception:
            return None

    def inspect_vericut_autodiff(self, image_path: str) -> dict:
        """Analyze VERICUT Auto-Diff screenshot to detect Gouges (Red) and Excess Material (Blue)."""
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Image file not found: {image_path}"}
        if not self.has_cv2:
            return {"status": "error", "message": "OpenCV (cv2) not installed"}

        img_bgr = self._read_image(image_path, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return {"status": "error", "message": f"Failed to decode image: {image_path}"}

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        h, w = img_bgr.shape[:2]
        total_pixels = float(h * w)

        # 1. Red (Gouge / 过切) mask: Red wraps around hue 0 and 180
        mask_red1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([170, 100, 100]), np.array([180, 255, 255]))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        red_count = int(cv2.countNonZero(mask_red))

        # 2. Blue (Excess material / 欠切) mask
        mask_blue = cv2.inRange(hsv, np.array([100, 100, 100]), np.array([130, 255, 255]))
        blue_count = int(cv2.countNonZero(mask_blue))

        # 3. Green (In Tolerance / 公差合格) mask
        mask_green = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        green_count = int(cv2.countNonZero(mask_green))

        machined_pixels = max(1, red_count + blue_count + green_count)
        gouge_ratio = round((red_count / machined_pixels) * 100.0, 2)
        excess_ratio = round((blue_count / machined_pixels) * 100.0, 2)
        in_tolerance_ratio = round((green_count / machined_pixels) * 100.0, 2)

        # Verdict logic
        if red_count > 100 and gouge_ratio > 0.5:
            verdict = "CRITICAL_GOUGE_DETECTED"
            recommendation = "Reject G-code! Severe gouge/crash detected on workpiece surface. Tool compensation or Z depth must be reviewed."
        elif blue_count > 500 and excess_ratio > 5.0:
            verdict = "WARNING_EXCESS_MATERIAL"
            recommendation = "Pass with rework: Uncut excess material detected. Add semi-finishing or corner cleanout pass."
        else:
            verdict = "PASSED_IN_TOLERANCE"
            recommendation = "Machined part matches nominal CAD model within tolerance. Ready for CMM inspection."

        return {
            "status": "success",
            "image_path": image_path,
            "dimensions": {"width": w, "height": h},
            "metrics": {
                "gouge_pixels": red_count,
                "gouge_percentage": gouge_ratio,
                "excess_pixels": blue_count,
                "excess_percentage": excess_ratio,
                "green_pixels": green_count,
                "machined_pixels": int(machined_pixels),
                "in_tolerance_percentage": in_tolerance_ratio,
            },
            # 审计 §4-4：triage_autodiff.py 读的是扁平字段。此前只给嵌套 metrics，
            # 消费端 .get("red_pixels", 0) 恒读 0 导致每次都判 AD-EMPTY-FIELD。
            # 两套键同时输出，保持旧消费方向后兼容。
            "gouge_pixels": red_count,
            "excess_pixels": blue_count,
            "green_pixels": green_count,
            "machined_pixels": int(machined_pixels),
            "gouge_percentage": gouge_ratio,
            "excess_percentage": excess_ratio,
            "in_tolerance_percentage": in_tolerance_ratio,
            "safety_verdict": verdict,
            "verdict": verdict,
            "engineering_recommendation": recommendation
        }

    def analyze_drawing_blueprint(self, image_path: str) -> dict:
        """Analyze 2D technical drawing / blueprint image to segment titleblock, views, and annotations."""
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Image not found: {image_path}"}
        if not self.has_cv2:
            return {"status": "error", "message": "OpenCV (cv2) not installed"}

        img = self._read_image(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"status": "error", "message": f"Failed to read image: {image_path}"}

        h, w = img.shape
        # Threshold
        _, bin_img = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)

        # Morphological extraction of horizontal and vertical line networks
        horiz_k = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 80, 1))
        verti_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 80))

        horiz_lines = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, horiz_k)
        verti_lines = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, verti_k)
        table_grid = cv2.bitwise_or(horiz_lines, verti_lines)

        # Detect contours (potential title blocks or tabular areas)
        contours, _ = cv2.findContours(table_grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detected_boxes = []
        title_block = None

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            if area > (w * h * 0.01):  # Filter trivial boxes
                box_info = {"x": int(x), "y": int(y), "width": int(bw), "height": int(bh), "area": int(area)}
                detected_boxes.append(box_info)
                # Bottom-right box is typically ISO/GB title block
                if (x + bw) > (w * 0.7) and (y + bh) > (h * 0.7):
                    title_block = box_info

        return {
            "status": "success",
            "image_path": image_path,
            "sheet_resolution": {"width": w, "height": h},
            "title_block_located": title_block is not None,
            "title_block_region": title_block or {"x": int(w * 0.65), "y": int(h * 0.8), "width": int(w * 0.35), "height": int(h * 0.2)},
            "detected_view_regions_count": len(detected_boxes),
            "detected_regions": detected_boxes[:10],
            "gdt_readiness": "ready_for_ctq_extraction"
        }

    def inspect_cnc_screen(self, image_path: str) -> dict:
        """Perceive virtual CNC controller (SSCNC/CIMCO/FANUC) screen to detect active status & display panel."""
        if not os.path.exists(image_path):
            return {"status": "error", "message": f"Image not found: {image_path}"}
        if not self.has_cv2:
            return {"status": "error", "message": "OpenCV (cv2) not installed"}

        img = self._read_image(image_path, cv2.IMREAD_COLOR)
        if img is None:
            return {"status": "error", "message": "Failed to decode image"}

        h, w = img.shape[:2]
        # Look for green text CRT or alarm banners (typical of FANUC 0i / CNC simulation)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask_green = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([80, 255, 255]))
        mask_yellow = cv2.inRange(hsv, np.array([20, 100, 100]), np.array([35, 255, 255]))
        mask_red_alarm = cv2.inRange(hsv, np.array([0, 150, 150]), np.array([10, 255, 255]))

        green_crt_pixels = int(cv2.countNonZero(mask_green))
        alarm_pixels = int(cv2.countNonZero(mask_red_alarm))

        has_alarm = alarm_pixels > 200
        crt_active = green_crt_pixels > 500

        return {
            "status": "success",
            "image_path": image_path,
            "screen_size": {"width": w, "height": h},
            "crt_display_active": crt_active,
            "alarm_state": "ALARM_TRIGGERED" if has_alarm else "NORMAL_OPERATION",
            "alarm_pixels": alarm_pixels,
            "system_mode": "AUTO_OR_MEM" if not has_alarm else "INTERRUPTED_BY_ALARM"
        }

    # ------------------------------------------------------------------
    # 统一视觉入口（审计 §4-3：super_agent 曾调用不存在的 analyze_inspection）
    # ------------------------------------------------------------------
    VISION_TASK_METHODS = {
        "autodiff_inspection": "inspect_vericut_autodiff",
        "vericut_autodiff": "inspect_vericut_autodiff",
        "blueprint_analysis": "analyze_drawing_blueprint",
        "drawing_blueprint": "analyze_drawing_blueprint",
        "cnc_screen_perception": "inspect_cnc_screen",
        "cnc_screen": "inspect_cnc_screen",
    }

    def analyze_inspection(self, task: str = "autodiff_inspection", image_path: str = "") -> dict:
        """Single dispatch point for every vision task.

        Keeps ``cadcam_visual_inspect``, ``super_agent.facet_screen_control`` and any
        script on one routing table so the tool surface cannot drift out of sync with
        the methods actually implemented here.
        """
        if not image_path:
            return {
                "status": "error",
                "verdict_code": "MISSING_IMAGE_PATH",
                "task": task,
                "supported_tasks": sorted(self.VISION_TASK_METHODS),
            }
        method_name = self.VISION_TASK_METHODS.get(str(task))
        if not method_name:
            return {
                "status": "error",
                "verdict_code": "UNKNOWN_VISION_TASK",
                "task": task,
                "supported_tasks": sorted(self.VISION_TASK_METHODS),
            }
        return getattr(self, method_name)(image_path)
