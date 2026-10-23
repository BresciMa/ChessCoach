import json

from chesscoach.analysis.facts import CoachFacts, KingFacts
from chesscoach.config import AppConfig, load_config, save_config
from chesscoach.types import Level, Rect


def test_coach_facts_can_be_built():
    facts = CoachFacts(
        fen="8/8/8/8/8/8/8/4K2k w - - 0 1",
        side_to_move="white",
        last_move_san=None,
        in_check=False,
        moved_piece=None,
        moved_piece_rule=None,
        evaluation_cp=None,
        previous_evaluation_cp=None,
        best_move_san=None,
        candidate_moves_san=[],
        hanging_squares=[],
        threatened_squares=[],
        development_white=0,
        development_black=0,
        own_king=KingFacts(True, False, False, False),
        opponent_king=KingFacts(True, False, False, None),
    )
    assert facts.side_to_move == "white"
    assert facts.own_king.on_start_square


def test_config_roundtrip_keeps_level_and_acceptance(tmp_path):
    path = tmp_path / "config.json"
    original = AppConfig(
        training_accepted=True,
        level=Level.LEVEL_2,
        roi=Rect(10, 20, 400, 400),
        arrows_enabled=True,
    )
    save_config(original, path)
    loaded = load_config(path)
    assert loaded.training_accepted is True
    assert loaded.level == Level.LEVEL_2
    assert loaded.roi == Rect(10, 20, 400, 400)
    assert loaded.arrows_enabled is True


def test_config_never_stores_the_api_key(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"gemini_api_key": "segredo", "level": "nivel_1", "training_accepted": True}), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.level == Level.LEVEL_1
    save_config(loaded, path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "gemini_api_key" not in saved
    assert "GEMINI_API_KEY" not in saved
    assert loaded.training_accepted is True


def test_default_training_is_not_accepted(tmp_path):
    loaded = load_config(tmp_path / "ausente.json")
    assert loaded.training_accepted is False
