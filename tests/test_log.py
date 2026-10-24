import logging

from chesscoach.log import RepeatGate, configure, consume_debug_flag


def test_debug_flag_is_removed_before_qt_sees_the_arguments():
    debug, argv = consume_debug_flag(["chesscoach", "--debug", "--other"])
    assert debug is True
    assert argv == ["chesscoach", "--other"]
    debug, argv = consume_debug_flag(["chesscoach"])
    assert debug is False
    assert argv == ["chesscoach"]


def test_without_debug_only_errors_are_written(tmp_path):
    path = tmp_path / "chesscoach.log"
    configure(False, path)
    logging.getLogger("chesscoach.vision").info("quadro parado")
    logging.getLogger("chesscoach.engine").error("stockfish sem bestmove")
    _flush()
    text = path.read_text(encoding="utf-8")
    assert "quadro parado" not in text
    assert "stockfish sem bestmove" in text


def test_debug_writes_info_and_the_same_line_waits(tmp_path):
    path = tmp_path / "chesscoach.log"
    configure(True, path)
    logging.getLogger("chesscoach.vision").info("visao releitura")
    _flush()
    assert "visao releitura" in path.read_text(encoding="utf-8")
    gate = RepeatGate(1.0)
    assert gate.allow("releitura casas=4", 0)
    assert gate.allow("releitura casas=4", 0.4) is False
    assert gate.allow("releitura casas=4", 1.1)
    assert gate.allow("perda casas=64", 1.2)


def test_configuring_again_does_not_duplicate_the_error(tmp_path):
    path = tmp_path / "chesscoach.log"
    configure(False, path)
    configure(False, path)
    logging.getLogger("chesscoach.engine").error("uma vez")
    _flush()
    assert path.read_text(encoding="utf-8").count("uma vez") == 1


def _flush() -> None:
    for handler in logging.getLogger("chesscoach").handlers:
        handler.flush()
