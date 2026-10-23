import ssl

from chesscoach.analysis.facts import CoachFacts, KingFacts
from chesscoach.coach.orchestrator import CoachOrchestrator
from chesscoach.coach.policy import StockHelpPolicy
from chesscoach.llm.gemini import LlmConnectionError, gemini_ssl_context
from chesscoach.messages import MSG_SSL
from chesscoach.types import Level, Reason


def test_ssl_context_uses_an_ssl_context():
    context = gemini_ssl_context()
    assert isinstance(context, ssl.SSLContext)


def test_connection_failure_becomes_a_chat_message(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "teste")

    class Boom:
        def complete(self, messages, model):
            raise LlmConnectionError(MSG_SSL)

    facts = CoachFacts(
        fen="8/8/8/8/8/8/8/8 w - - 0 1",
        side_to_move="white",
        last_move_san="e4",
        in_check=False,
        moved_piece="peão branco",
        moved_piece_rule="O peão anda.",
        evaluation_cp=10,
        previous_evaluation_cp=10,
        best_move_san="Nf3",
        candidate_moves_san=["Nf3"],
        hanging_squares=[],
        threatened_squares=[],
        development_white=1,
        development_black=0,
        own_king=KingFacts(True, True, True, False),
        opponent_king=KingFacts(True, True, True, False),
    )
    turn = CoachOrchestrator(StockHelpPolicy(), Boom(), "gemini-flash-latest").respond(
        facts, Level.LEVEL_1, Reason.HINT_REQUESTED
    )
    assert turn.called_llm is False
    assert "certificado" in turn.text
