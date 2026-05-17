"""Tests for slider_solver.py — write BEFORE implementation."""

import base64
import json
import os
import struct
import zlib

import cv2
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers to generate synthetic test images (no real jigsaw dependency)
# ---------------------------------------------------------------------------

def _make_png_bytes(img: np.ndarray) -> bytes:
    """Encode BGR ndarray to PNG bytes."""
    ok, buf = cv2.imencode(".png", img)
    assert ok, "cv2.imencode failed"
    return buf.tobytes()


def _to_data_url(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode()


def _synth_big_image(width=280, height=160, gap_x=120, gap_y=62, gap_w=40, gap_h=40):
    """Create a synthetic big image; cut a piece from it to simulate a real jigsaw."""
    # Create textured background
    img = np.random.randint(80, 200, (height, width, 3), dtype=np.uint8)
    # Add some structure so template matching works
    for i in range(0, width, 20):
        cv2.line(img, (i, 0), (i, height), (150, 100, 50), 1)
    for j in range(0, height, 20):
        cv2.line(img, (0, j), (width, j), (50, 100, 150), 1)
    return img, gap_x, gap_y, gap_w, gap_h


def _synth_small_image(big_img, gap_x, gap_y, gap_w, gap_h):
    """Cut the piece from big_img and return as BGRA (simulates real jigsaw)."""
    piece_bgr = big_img[gap_y : gap_y + gap_h, gap_x : gap_x + gap_w].copy()
    piece_bgra = cv2.cvtColor(piece_bgr, cv2.COLOR_BGR2BGRA)
    # Set alpha=255 for the interior, 0 for a small border (simulates puzzle shape)
    piece_bgra[:, :, 3] = 255
    piece_bgra[0:3, :, 3] = 0
    piece_bgra[-3:, :, 3] = 0
    piece_bgra[:, 0:3, 3] = 0
    piece_bgra[:, -3:, 3] = 0
    return piece_bgra


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSolveSlider:
    """Test suite for solve_slider function."""

    def test_returns_slider_solution_with_required_fields(self):
        """SliderSolution must have target_x, target_y, piece_initial_x, drag_distance, confidence."""
        from slider_solver import solve_slider

        big_img, gx, gy, gw, gh = _synth_big_image()
        small_img = _synth_small_image(big_img, gx, gy, gw, gh)
        big_url = _to_data_url(_make_png_bytes(big_img))
        small_url = _to_data_url(_make_png_bytes(small_img))

        result = solve_slider(big_url, small_url, y_height=gy, panel_width=280)

        assert hasattr(result, "target_x")
        assert hasattr(result, "target_y")
        assert hasattr(result, "piece_initial_x")
        assert hasattr(result, "drag_distance")
        assert hasattr(result, "confidence")

    def test_target_x_within_image_bounds(self):
        """target_x must be within [0, big_image_width)."""
        from slider_solver import solve_slider

        big_img, gx, gy, gw, gh = _synth_big_image(width=280)
        small_img = _synth_small_image(big_img, gx, gy, gw, gh)
        big_url = _to_data_url(_make_png_bytes(big_img))
        small_url = _to_data_url(_make_png_bytes(small_img))

        result = solve_slider(big_url, small_url, y_height=gy, panel_width=280)

        assert 0 <= result.target_x < 280, f"target_x={result.target_x} out of bounds"

    def test_drag_distance_positive(self):
        """drag_distance must be > 0 when piece_initial_x < target_x."""
        from slider_solver import solve_slider

        big_img, gx, gy, gw, gh = _synth_big_image(gap_x=120)
        small_img = _synth_small_image(big_img, gx, gy, gw, gh)
        big_url = _to_data_url(_make_png_bytes(big_img))
        small_url = _to_data_url(_make_png_bytes(small_img))

        result = solve_slider(big_url, small_url, y_height=gy, panel_width=280)

        assert result.drag_distance > 0, f"drag_distance={result.drag_distance} should be positive"

    def test_target_reports_alpha_offset(self):
        """The solver must detect the transparent border around the crop."""
        from slider_solver import solve_slider

        big_img, gx, gy, gw, gh = _synth_big_image(gap_x=120, gap_y=62)
        small_img = _synth_small_image(big_img, gx, gy, gw, gh)
        big_url = _to_data_url(_make_png_bytes(big_img))
        small_url = _to_data_url(_make_png_bytes(small_img))

        result = solve_slider(big_url, small_url, y_height=gy, panel_width=280)

        assert result.template_offset_x == 3
        assert result.template_offset_y == 3
        assert result.target_x == gx
        assert result.target_y == gy

    def test_confidence_above_threshold(self):
        """confidence must be >= 0.3 for a valid match."""
        from slider_solver import solve_slider

        big_img, gx, gy, gw, gh = _synth_big_image()
        small_img = _synth_small_image(big_img, gx, gy, gw, gh)
        big_url = _to_data_url(_make_png_bytes(big_img))
        small_url = _to_data_url(_make_png_bytes(small_img))

        result = solve_slider(big_url, small_url, y_height=gy, panel_width=280)

        assert result.confidence >= 0.3, f"confidence={result.confidence} too low"

    def test_decodes_data_url_correctly(self):
        """Must handle data:image/png;base64, prefix."""
        from slider_solver import _decode_data_url

        png_bytes = _make_png_bytes(np.zeros((10, 10, 3), dtype=np.uint8))
        url = _to_data_url(png_bytes)
        decoded = _decode_data_url(url)
        assert len(decoded) == len(png_bytes)

    def test_decode_data_url_without_prefix(self):
        """Must also handle raw base64 without data-url prefix."""
        from slider_solver import _decode_data_url

        png_bytes = _make_png_bytes(np.zeros((10, 10, 3), dtype=np.uint8))
        raw_b64 = base64.b64encode(png_bytes).decode()
        decoded = _decode_data_url(raw_b64)
        assert len(decoded) == len(png_bytes)

    def test_extract_template_from_alpha(self):
        """_extract_template must crop to the opaque region of smallImg."""
        from slider_solver import _extract_template

        big_img, gx, gy, gw, gh = _synth_big_image()
        small = _synth_small_image(big_img, gx, gy, gw, gh)
        tmpl = _extract_template(small)
        # Template should be smaller than full image (cropped to alpha content)
        assert tmpl.shape[0] <= gw
        assert tmpl.shape[1] <= gh
        assert tmpl.shape[0] > 0
        assert tmpl.shape[1] > 0

    def test_solve_with_real_jigsaw_data(self):
        """Integration test with the real jigsaw_response.json if available."""
        jigsaw_path = os.path.join(os.path.dirname(__file__), "..", "artifacts", "jigsaw_response.json")
        if not os.path.exists(jigsaw_path):
            pytest.skip("jigsaw_response.json not found")

        from slider_solver import solve_slider

        with open(jigsaw_path) as f:
            data = json.load(f)

        bo = data["bo"]
        result = solve_slider(bo["bigImg"], bo["smallImg"], y_height=bo["yHeight"], panel_width=280)

        assert 0 <= result.target_x < 280
        assert result.drag_distance > 0
        assert result.confidence >= 0.3
