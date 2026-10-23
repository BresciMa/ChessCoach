"""Calibração manual do retângulo das 64 casas."""

from __future__ import annotations

from chesscoach.messages import MSG_NEED_ROI
from chesscoach.types import Orientation, Rect, Theme


class CalibrationError(ValueError):
    pass


class RoiCalibrator:
    def __init__(self) -> None:
        self.monitor = 0
        self.rect: Rect | None = None
        self.orientation = Orientation.WHITE_AT_BOTTOM
        self.theme = Theme.LICHESS_2D

    def set(self, monitor: int, rect: Rect | None, orientation: Orientation, theme: Theme) -> None:
        if rect is None or rect.width < 64 or rect.height < 64:
            raise CalibrationError(MSG_NEED_ROI)
        self.monitor = monitor
        self.rect = rect
        self.orientation = orientation
        self.theme = theme
