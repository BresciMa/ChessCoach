import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from chesscoach.ui.calibration import MARK_CODE, CalibrationDialog, RubberBand


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_mark_leaves_the_modal_dialog_before_the_drag(qapp):
    dialog = CalibrationDialog()
    QTimer.singleShot(0, dialog._mark)
    assert dialog.exec() == MARK_CODE


def test_drag_on_the_overlay_marks_a_rectangle(qapp):
    screen = qapp.primaryScreen()
    band = RubberBand(screen)
    band._ratio = 1
    band.setGeometry(0, 0, 800, 600)
    chosen = []
    band.selected.connect(chosen.append)
    band.show()
    qapp.processEvents()
    QTest.mousePress(band, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(40, 50))
    QTest.mouseRelease(band, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(360, 390))
    qapp.processEvents()
    assert chosen
    assert chosen[0].width == 320
    assert chosen[0].height == 340
    band.close()


def test_a_tiny_drag_does_not_count(qapp):
    screen = qapp.primaryScreen()
    band = RubberBand(screen)
    band._ratio = 1
    band.setGeometry(0, 0, 400, 400)
    chosen = []
    band.selected.connect(chosen.append)
    band.show()
    qapp.processEvents()
    QTest.mousePress(band, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(10, 10))
    QTest.mouseRelease(band, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(30, 30))
    qapp.processEvents()
    assert chosen == []
    assert band.isVisible()
    band.close()
