import pytest

from chesscoach.analysis.facts import CoachFacts, KingFacts
from chesscoach.coach.policy import StockHelpPolicy, is_hint_request
from chesscoach.types import Level, Reason


def _facts(**overrides) -> CoachFacts:
    base = dict(
        fen="8/8/8/8/8/8/8/8 w - - 0 1",
        side_to_move="black",
        last_move_san="e4",
        in_check=False,
        moved_piece="peão branco",
        moved_piece_rule="O peão anda uma casa para frente.",
        evaluation_cp=30,
        previous_evaluation_cp=10,
        best_move_san="Nh6",
        candidate_moves_san=["Nh6", "a6"],
        hanging_squares=[],
        threatened_squares=[],
        development_white=1,
        development_black=0,
        own_king=KingFacts(False, False, False, True),
        opponent_king=KingFacts(False, False, False, True),
    )
    base.update(overrides)
    return CoachFacts(**base)


def test_level_two_hides_the_move_until_a_hint():
    policy = StockHelpPolicy()
    facts = _facts(hanging_squares=["d4"], threatened_squares=["d4"], own_king=KingFacts(True, True, True, False))
    quiet = policy.apply(facts, Level.LEVEL_2, Reason.MOVE_CONFIRMED)
    assert quiet.facts_for_model.best_move_san is None
    assert quiet.facts_for_model.candidate_moves_san == []
    assert quiet.facts_for_model.evaluation_cp is None
    assert quiet.arrow is None
    assert quiet.speak is True
    hinted = policy.apply(facts, Level.LEVEL_2, Reason.HINT_REQUESTED)
    assert hinted.facts_for_model.best_move_san == "Nh6"
    assert hinted.arrow == "Nh6"


def test_level_two_hides_the_plain_move_until_a_hint():
    policy = StockHelpPolicy()
    facts = _facts(best_move_plain="cavalo preto de g8 para h6 (Nh6)")
    quiet = policy.apply(facts, Level.LEVEL_2, Reason.MOVE_CONFIRMED)
    assert quiet.facts_for_model.best_move_plain is None
    hinted = policy.apply(facts, Level.LEVEL_2, Reason.HINT_REQUESTED)
    assert hinted.facts_for_model.best_move_plain == "cavalo preto de g8 para h6 (Nh6)"


def test_lower_levels_ask_for_the_move_in_one_line():
    from chesscoach.coach.orchestrator import build_messages

    decision = StockHelpPolicy().apply(
        _facts(best_move_plain="cavalo branco de g1 para e2 (Ne2)"),
        Level.LEVEL_1,
        Reason.MOVE_CONFIRMED,
    )
    messages = build_messages(decision, Level.LEVEL_1, Reason.MOVE_CONFIRMED, None)
    assert "uma única linha" in messages[0].content
    assert "casa de saída" in messages[0].content
    assert "Ne2" in messages[1].content
    master = build_messages(decision, Level.MASTER, Reason.MOVE_CONFIRMED, None)
    assert "Sem best_move_plain" in master[0].content
    assert "previous_move_plain" in master[0].content
    assert "opening_name" in master[0].content


def test_level_two_stays_quiet_without_an_alert():
    policy = StockHelpPolicy()
    decision = policy.apply(_facts(), Level.LEVEL_2, Reason.MOVE_CONFIRMED)
    assert decision.speak is False
    assert decision.arrow is None


def test_master_comment_has_no_next_move():
    policy = StockHelpPolicy()
    decision = policy.apply(_facts(), Level.MASTER, Reason.MOVE_CONFIRMED)
    assert decision.speak is True
    assert decision.facts_for_model.best_move_san is None
    assert decision.arrow is None
    assert decision.facts_for_model.last_move_san == "e4"
    named = policy.apply(
        _facts(opening_name="Abertura Escocesa", previous_move_plain="peão branco de e2 para e4 (e4)"),
        Level.MASTER,
        Reason.MOVE_CONFIRMED,
    )
    assert named.facts_for_model.opening_name == "Abertura Escocesa"
    assert named.facts_for_model.previous_move_plain.startswith("peão branco")
    assert named.facts_for_model.best_move_san is None
    hinted = policy.apply(_facts(), Level.MASTER, Reason.HINT_REQUESTED)
    assert hinted.facts_for_model.best_move_san == "Nh6"
    assert hinted.facts_for_model.candidate_moves_san == []


def test_level_one_arrow_and_beginner_keeps_a_single_move():
    policy = StockHelpPolicy()
    level_one = policy.apply(_facts(), Level.LEVEL_1, Reason.MOVE_CONFIRMED)
    assert level_one.arrow == "Nh6"
    assert level_one.facts_for_model.candidate_moves_san == ["Nh6", "a6"]
    beginner = policy.apply(_facts(), Level.BEGINNER, Reason.MOVE_CONFIRMED)
    assert beginner.facts_for_model.best_move_san == "Nh6"
    assert beginner.facts_for_model.candidate_moves_san == []
    assert beginner.arrow is None
    assert beginner.facts_for_model.moved_piece_rule


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("qual lance eu faço?", True),
        ("me dá uma dica", True),
        ("Dica", True),
        ("por que o rei está no centro?", False),
    ],
)
def test_hint_phrases(text, expected):
    assert is_hint_request(text) is expected
