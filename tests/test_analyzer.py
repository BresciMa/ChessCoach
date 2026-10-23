import chess

from chesscoach.analysis.analyzer import PositionAnalyzer
from chesscoach.chess.game import ChessGame
from chesscoach.engine.uci import EngineResult


def test_hanging_check_development_and_king():
    analyzer = PositionAnalyzer()
    hanging = ChessGame(chess.Board("4k3/8/8/2p5/3P4/8/8/4K3 w - - 0 1"))
    facts = analyzer.analyze(hanging, None, None)
    assert facts.hanging_squares == ["d4"]
    assert "d4" in facts.threatened_squares
    assert facts.evaluation_cp is None
    assert facts.best_move_san is None
    assert facts.in_check is False

    checked = ChessGame(chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"))
    check_facts = analyzer.analyze(checked, None, None)
    assert check_facts.in_check is True
    assert check_facts.own_king.on_start_square is True

    developed = ChessGame()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5"):
        developed.apply(developed.parse_san(san))
    dev_facts = analyzer.analyze(developed, None, None)
    assert dev_facts.development_white == 2
    assert dev_facts.development_black == 1

    castled = ChessGame()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O"):
        castled.apply(castled.parse_san(san))
    king_facts = analyzer.analyze(castled, None, None)
    assert king_facts.opponent_king.castled is True
    assert king_facts.opponent_king.on_start_square is False
    assert king_facts.own_king.on_start_square is True
    assert king_facts.own_king.castled is False

    unknown = ChessGame(chess.Board(), history_known=False)
    unknown_facts = analyzer.analyze(unknown, None, None)
    assert unknown_facts.own_king.castled is None


def test_the_scotch_name_comes_from_the_move_list_not_from_the_model():
    game = ChessGame()
    for san in ("e4", "e5", "Nf3", "Nc6", "d4"):
        game.apply(game.parse_san(san))
    facts = PositionAnalyzer().analyze(game, None, None)
    assert facts.opening_name == "Abertura Escocesa"
    assert "Nc6" in facts.previous_move_plain
    assert "d4" in facts.last_move_plain
    unknown = ChessGame()
    for san in ("e4", "e5", "Ke2"):
        unknown.apply(unknown.parse_san(san))
    quiet = PositionAnalyzer().analyze(unknown, None, None)
    assert quiet.opening_name == "Abertura do Peão do Rei"


def test_engine_moves_become_san_and_missing_engine_keeps_static_fields():
    analyzer = PositionAnalyzer()
    game = ChessGame()
    game.apply(game.parse_san("e4"))
    facts = analyzer.analyze(
        game,
        EngineResult(evaluation_cp=35, uci_moves=["g8h6", "a7a6", "d7d6"]),
        previous_evaluation_cp=10,
    )
    assert facts.best_move_san == "Nh6"
    assert facts.candidate_moves_san[0] == "Nh6"
    assert facts.evaluation_cp == 35
    assert facts.previous_evaluation_cp == 10
    assert facts.moved_piece == "peão branco"
    assert facts.moved_piece_rule.startswith("O peão anda")
    assert facts.best_move_plain == "cavalo preto de g8 para h6 (Nh6)"
    assert facts.last_move_plain == "peão branco de e2 para e4 (e4)"
    assert facts.opening_name == "Abertura do Peão do Rei"

    bare = analyzer.analyze(game, None, 10)
    assert bare.best_move_san is None
    assert bare.evaluation_cp is None
    assert bare.moved_piece == "peão branco"
    assert bare.hanging_squares == facts.hanging_squares
