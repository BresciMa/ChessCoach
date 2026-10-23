import chess

from chesscoach.chess.game import ChessGame, match_legal_move, shortest_replays
from chesscoach.config import AppConfig
from chesscoach.types import Orientation, Rect, TrackerKind
from chesscoach.vision.tracker import MOVING_INTERVAL_MS, STABLE_HOLD_MS, PositionTracker, WatchState
from tests.images import board_image, frame, solid, tint


class QueueCapture:
    def __init__(self, images):
        self.images = list(images)
        self.calls = 0

    def grab(self, monitor, region):
        image = self.images[min(self.calls, len(self.images) - 1)]
        self.calls += 1
        return frame(image, 0)


def _tracker(game: ChessGame | None = None) -> tuple[PositionTracker, ChessGame]:
    game = game or ChessGame()
    config = AppConfig(roi=Rect(0, 0, 320, 320), orientation=Orientation.WHITE_AT_BOTTOM)
    return PositionTracker(QueueCapture([]), game, config), game


def test_idle_does_not_grab_before_250ms():
    image = board_image(chess.Board())
    capture = QueueCapture([image, image, image])
    game = ChessGame()
    config = AppConfig(roi=Rect(0, 0, 320, 320))
    tracker = PositionTracker(capture, game, config)
    tracker.poll(0)
    tracker.poll(100)
    assert capture.calls == 1
    tracker.poll(250)
    assert capture.calls == 2


def test_motion_waits_until_the_piece_has_settled():
    start = board_image(chess.Board())
    played = chess.Board()
    played.push_san("e4")
    after = board_image(played)
    red = solid((255, 0, 0))
    capture = QueueCapture([start, red, after, after])
    game = ChessGame()
    config = AppConfig(roi=Rect(0, 0, 320, 320))
    tracker = PositionTracker(capture, game, config)
    tracker.poll(0)
    tracker.poll(250)
    assert tracker.watch.state == WatchState.MOVING
    tracker.poll(250 + MOVING_INTERVAL_MS - 1)
    assert capture.calls == 2
    tracker.poll(250 + MOVING_INTERVAL_MS)
    assert tracker.watch.state == WatchState.MOVING
    quiet = 250 + MOVING_INTERVAL_MS * 2
    early = tracker.poll(quiet)
    assert early is not None
    assert early.kind == TrackerKind.NO_CHANGE
    assert tracker.watch.state == WatchState.HOLDING
    assert game.sans == []
    result = tracker.poll(quiet + STABLE_HOLD_MS)
    assert tracker.watch.state == WatchState.IDLE
    assert result is not None
    assert result.kind == TrackerKind.MOVE_CONFIRMED
    assert result.san == "e4"


def test_unstable_board_times_out_without_changing_the_game():
    tracker, game = _tracker()
    tracker.seed(solid((10, 10, 10)))
    assert tracker.ingest(frame(solid((80, 10, 10)), 0)).kind == TrackerKind.NO_CHANGE
    assert tracker.ingest(frame(solid((10, 80, 10)), 500)).kind == TrackerKind.NO_CHANGE
    result = tracker.ingest(frame(solid((10, 10, 80)), 1000))
    assert result.kind == TrackerKind.BOARD_UNSTABLE
    assert tracker.watch.state == WatchState.IDLE
    assert game.board.fen() == chess.STARTING_FEN


def test_highlight_only_does_not_become_a_move():
    game = ChessGame()
    game.apply(game.parse_san("e4"))
    tracker, _ = _tracker(game)
    after = board_image(game.board)
    tracker.seed(after)
    highlighted = tint(after, ["e2", "e4"])
    tracker.ingest(frame(highlighted, 0))
    tracker.ingest(frame(highlighted, 100))
    result = tracker.ingest(frame(highlighted, 500))
    assert result.kind == TrackerKind.NO_CHANGE
    assert game.sans == ["e4"]


def test_simple_move_capture_castle_en_passant_and_promotion():
    tracker, game = _tracker()
    start = board_image(chess.Board())
    tracker.seed(start)
    after = chess.Board()
    after.push_san("e4")
    _play(tracker, board_image(after))
    assert game.sans == ["e4"]

    capture_before = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    capture_game = ChessGame(capture_before)
    capture_tracker, _ = _tracker(capture_game)
    capture_tracker.seed(board_image(capture_before))
    capture_after = capture_before.copy()
    capture_after.push_san("exd5")
    _play(capture_tracker, board_image(capture_after))
    assert capture_game.sans == ["exd5"]

    castle_before = chess.Board("k7/8/8/8/8/8/8/4K2R w K - 0 1")
    castle_game = ChessGame(castle_before)
    castle_tracker, _ = _tracker(castle_game)
    castle_tracker.seed(board_image(castle_before))
    castle_after = castle_before.copy()
    castle_after.push_san("O-O")
    _play(castle_tracker, board_image(castle_after))
    assert castle_game.sans == ["O-O"]

    ep_before = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    ep_game = ChessGame(ep_before)
    ep_tracker, _ = _tracker(ep_game)
    ep_tracker.seed(board_image(ep_before))
    ep_after = ep_before.copy()
    ep_after.push_san("exd6")
    _play(ep_tracker, board_image(ep_after))
    assert ep_game.sans == ["exd6"]

    promo_before = chess.Board("8/4P3/8/8/8/8/4K3/k7 w - - 0 1")
    promo_game = ChessGame(promo_before)
    promo_tracker, _ = _tracker(promo_game)
    promo_tracker.seed(board_image(promo_before))
    visual = promo_before.copy()
    visual.push_san("e8=Q")
    first = promo_tracker.ingest(frame(board_image(visual), 0))
    holding = promo_tracker.ingest(frame(board_image(visual), 100))
    result = promo_tracker.ingest(frame(board_image(visual), 500))
    assert first.kind == TrackerKind.NO_CHANGE
    assert holding.kind == TrackerKind.NO_CHANGE
    assert result.kind == TrackerKind.PROMOTION_NEEDED
    assert promo_game.sans == []
    san = promo_tracker.confirm_promotion("q")
    assert san == "e8=Q"
    assert promo_game.board.piece_at(chess.E8).symbol() == "Q"


def test_illegal_change_and_ambiguous_board():
    tracker, game = _tracker()
    tracker.seed(board_image(chess.Board()))
    changed = board_image(chess.Board())
    # a1 e a3 não formam um lance legal a partir da posição inicial.
    noisy = tint(changed, ["a1", "a3"])
    tracker.ingest(frame(noisy, 0))
    tracker.ingest(frame(noisy, 100))
    result = tracker.ingest(frame(noisy, 500))
    assert result.kind == TrackerKind.NO_CHANGE
    assert game.sans == []

    everything = solid((0, 255, 0))
    tracker.ingest(frame(everything, 600))
    tracker.ingest(frame(everything, 700))
    covered = tracker.ingest(frame(everything, 1100))
    assert covered.kind == TrackerKind.BOARD_LOST
    assert game.sans == []


def test_several_moves_ask_for_a_fresh_read_instead_of_sticking():
    tracker, game = _tracker()
    start = chess.Board()
    start.push_san("e4")
    game.apply(game.parse_san("e4"))
    tracker.seed(board_image(start))
    later = start.copy()
    for san in ("c6", "Nc3", "d5"):
        later.push_san(san)
    picture = board_image(later)
    tracker.ingest(frame(picture, 0))
    tracker.ingest(frame(picture, 100))
    result = tracker.ingest(frame(picture, 500))
    assert result.kind == TrackerKind.BOARD_CHECK
    assert game.sans == ["e4"]


def test_shortest_replay_recovers_the_missed_moves():
    start = chess.Board()
    start.push_san("e4")
    later = start.copy()
    for san in ("c6", "Nc3", "d5"):
        later.push_san(san)
    placement = {chess.square_name(square): piece.symbol() for square, piece in later.piece_map().items()}
    paths = shortest_replays(start, placement)
    assert len(paths) == 1
    replay = start.copy()
    sans = []
    for move in paths[0]:
        sans.append(replay.san(move))
        replay.push(move)
    assert sans == ["c6", "Nc3", "d5"]
    assert replay.fen() == later.fen()


def test_match_helper_prefers_the_larger_explanation():
    board = chess.Board("k7/8/8/8/8/8/8/4K2R w K - 0 1")
    found = match_legal_move(board, {"e1", "f1", "g1", "h1"})
    assert found.kind == TrackerKind.MOVE_CONFIRMED
    assert board.san(found.move) == "O-O"


def test_a_pause_shorter_than_the_hold_does_not_change_the_game():
    tracker, game = _tracker()
    tracker.seed(board_image(chess.Board()))
    after = chess.Board()
    after.push_san("e4")
    image = board_image(after)
    dragged = tint(image, ["d1", "c1", "b1"])
    tracker.ingest(frame(dragged, 0))
    tracker.ingest(frame(dragged, 100))
    moved = tracker.ingest(frame(image, 200))
    assert moved.kind == TrackerKind.NO_CHANGE
    assert game.sans == []
    tracker.ingest(frame(image, 300))
    settled = tracker.ingest(frame(image, 700))
    assert settled.kind == TrackerKind.MOVE_CONFIRMED
    assert game.sans == ["e4"]


def test_a_drag_trail_is_not_a_move():
    tracker, game = _tracker()
    tracker.seed(board_image(chess.Board()))
    after = chess.Board()
    after.push_san("e4")
    dragged = tint(board_image(after), ["d1", "c1", "b1", "f1"])
    tracker.ingest(frame(dragged, 0))
    tracker.ingest(frame(dragged, 100))
    result = tracker.ingest(frame(dragged, 500))
    assert result.kind == TrackerKind.BOARD_CHECK
    assert game.sans == []


def test_two_leftover_squares_still_count_as_the_move():
    tracker, game = _tracker()
    tracker.seed(board_image(chess.Board()))
    after = chess.Board()
    after.push_san("e4")
    _play(tracker, tint(board_image(after), ["a3", "h3"]))
    assert game.sans == ["e4"]


def test_covering_the_board_stops_moves_until_the_same_position_returns():
    tracker, game = _tracker()
    start = board_image(chess.Board())
    tracker.seed(start)
    green = solid((0, 255, 0))
    tracker.ingest(frame(green, 0))
    tracker.ingest(frame(green, 100))
    lost = tracker.ingest(frame(green, 500))
    assert lost.kind == TrackerKind.BOARD_LOST
    assert tracker.ingest(frame(green, 800)).kind == TrackerKind.NO_CHANGE
    tracker.ingest(frame(start, 900))
    tracker.ingest(frame(start, 1000))
    back = tracker.ingest(frame(start, 1400))
    assert back.kind == TrackerKind.NO_CHANGE
    assert back.restored is True
    assert game.sans == []


def test_a_different_picture_while_lost_asks_for_a_fresh_read():
    tracker, game = _tracker()
    tracker.seed(board_image(chess.Board()))
    green = solid((0, 255, 0))
    tracker.ingest(frame(green, 0))
    tracker.ingest(frame(green, 100))
    assert tracker.ingest(frame(green, 500)).kind == TrackerKind.BOARD_LOST
    mid = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        mid.push_san(san)
    picture = board_image(mid)
    tracker.ingest(frame(picture, 600))
    tracker.ingest(frame(picture, 700))
    check = tracker.ingest(frame(picture, 1100))
    assert check.kind == TrackerKind.BOARD_CHECK
    assert game.sans == []


def _play(tracker: PositionTracker, image) -> None:
    tracker.ingest(frame(image, 0))
    tracker.ingest(frame(image, 100))
    tracker.ingest(frame(image, 500))
