"""Captura de uma região. O restante do app não escolhe a API de tela."""

from __future__ import annotations

import numpy as np

from chesscoach.types import Frame, Rect


class MonitorCapture:
    def __init__(self) -> None:
        self._dxcam = None
        self._dxcam_failed = False

    def grab(self, monitor: int, region: Rect) -> Frame:
        image = self._grab_dxcam(monitor, region)
        if image is None:
            image = self._grab_mss(monitor, region)
        return Frame(image=image, time_ms=0)

    def _grab_dxcam(self, monitor: int, region: Rect) -> np.ndarray | None:
        if self._dxcam_failed:
            return None
        try:
            import dxcam
        except ImportError:
            self._dxcam_failed = True
            return None
        try:
            if self._dxcam is None:
                self._dxcam = dxcam.create(output_idx=monitor)
            box = (region.x, region.y, region.x + region.width, region.y + region.height)
            frame = self._dxcam.grab(region=box)
            if frame is None:
                return None
            array = np.asarray(frame)
            return array[:, :, :3].copy()
        except Exception:
            self._dxcam_failed = True
            return None

    def _grab_mss(self, monitor: int, region: Rect) -> np.ndarray:
        import mss

        with mss.mss() as sct:
            screens = sct.monitors[1:] or sct.monitors
            chosen = screens[min(monitor, len(screens) - 1)]
            box = {
                "left": int(chosen["left"] + region.x),
                "top": int(chosen["top"] + region.y),
                "width": int(region.width),
                "height": int(region.height),
            }
            shot = np.asarray(sct.grab(box))
            return shot[:, :, :3][:, :, ::-1].copy()
