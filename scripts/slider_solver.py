"""
slider_solver.py — Pure OpenCV slider gap solver.

Decodes bigImg/smallImg data URLs from ZTE SCM jigsaw API,
finds the gap x-coordinate via template matching, and returns
a SliderSolution with all fields needed for drag automation.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Union

import cv2
import numpy as np


# ── Data class ─────────────────────────────────────────────────────────────

@dataclass
class SliderSolution:
    target_x: int          # gap left edge x in big-image coords
    target_y: int          # gap top edge y in big-image coords
    piece_initial_x: int   # will be filled from DOM later; default 0
    drag_distance: float   # target_x - piece_initial_x
    confidence: float      # template match score [0, 1]


# ── Public API ─────────────────────────────────────────────────────────────

def solve_slider(
    big_img_data_url: str,
    small_img_data_url: str,
    y_height: int,
    panel_width: int = 280,
) -> SliderSolution:
    """Find the gap position and compute drag parameters.

    Parameters
    ----------
    big_img_data_url : str   data:image/png;base64,... of the background
    small_img_data_url : str data:image/png;base64,... of the puzzle piece
    y_height : int           approximate y of the gap from the API
    panel_width : int        width of the slider panel (default 280)

    Returns
    -------
    SliderSolution with all fields populated.
    piece_initial_x is set to 0 here — the caller must override it
    with the real DOM value before dragging.
    """
    big_bytes = _decode_data_url(big_img_data_url)
    small_bytes = _decode_data_url(small_img_data_url)

    big_img = cv2.imdecode(np.frombuffer(big_bytes, np.uint8), cv2.IMREAD_COLOR)
    small_img = cv2.imdecode(np.frombuffer(small_bytes, np.uint8), cv2.IMREAD_UNCHANGED)

    if big_img is None:
        raise ValueError("Failed to decode bigImg")
    if small_img is None:
        raise ValueError("Failed to decode smallImg")

    template = _extract_template(small_img)
    target_x, target_y, confidence = _match_template(big_img, template, y_height, panel_width)

    drag_distance = float(target_x)  # piece_initial_x defaults to 0

    return SliderSolution(
        target_x=target_x,
        target_y=target_y,
        piece_initial_x=0,
        drag_distance=drag_distance,
        confidence=confidence,
    )


# ── Internal helpers ───────────────────────────────────────────────────────

def _decode_data_url(data_url: str) -> bytes:
    """Decode a data:image/...;base64,... URL (or raw base64 string)."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


def _extract_template(small_img: np.ndarray) -> np.ndarray:
    """Crop the puzzle piece to its opaque bounding box, return BGR."""
    if small_img.ndim == 3 and small_img.shape[2] == 4:
        alpha = small_img[:, :, 3]
        coords = cv2.findNonZero(alpha)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            cropped = small_img[y : y + h, x : x + w]
            # Convert BGRA -> BGR for template matching
            return cv2.cvtColor(cropped, cv2.COLOR_BGRA2BGR)
    # Fallback: already BGR or no alpha
    if small_img.ndim == 3 and small_img.shape[2] == 4:
        return cv2.cvtColor(small_img, cv2.COLOR_BGRA2BGR)
    return small_img


def _match_template(
    big_img: np.ndarray,
    template: np.ndarray,
    y_height: int,
    panel_width: int,
) -> tuple[int, int, float]:
    """Template match restricted to a band around y_height.

    Returns (target_x, target_y, confidence).
    """
    h, w = big_img.shape[:2]
    th, tw = template.shape[:2]

    # Search band: ±30 px around y_height, clamped to image
    y_lo = max(0, y_height - 30)
    y_hi = min(h, y_height + th + 30)

    # Clamp x search to [0, panel_width - template_width]
    x_hi = min(w - tw, panel_width - tw)
    if x_hi <= 0:
        x_hi = w - tw

    # Extract ROI
    roi = big_img[y_lo:y_hi, 0 : x_hi + tw]
    if roi.shape[0] < th or roi.shape[1] < tw:
        # ROI too small; fall back to full image
        roi = big_img
        y_lo = 0

    result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    target_x = max_loc[0]
    target_y = y_lo + max_loc[1]
    confidence = float(max_val)

    return target_x, target_y, confidence


def draw_overlay(
    big_img_bytes: bytes,
    template_bytes: bytes,
    solution: SliderSolution,
    output_path: str,
) -> None:
    """Draw match result overlay and save to output_path."""
    img = cv2.imdecode(np.frombuffer(big_img_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return
    tmpl = cv2.imdecode(np.frombuffer(template_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
    if tmpl is None:
        return
    tmpl_bgr = _extract_template(tmpl)
    th, tw = tmpl_bgr.shape[:2]

    # Draw target rectangle
    cv2.rectangle(
        img,
        (solution.target_x, solution.target_y),
        (solution.target_x + tw, solution.target_y + th),
        (0, 0, 255),
        2,
    )
    # Draw drag arrow
    cv2.arrowedLine(
        img,
        (solution.piece_initial_x, solution.target_y + th // 2),
        (solution.target_x, solution.target_y + th // 2),
        (0, 255, 0),
        2,
        tipLength=0.1,
    )
    # Label
    cv2.putText(
        img,
        f"x={solution.target_x} drag={solution.drag_distance:.0f} conf={solution.confidence:.2f}",
        (5, 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
    )
    cv2.imwrite(output_path, img)
