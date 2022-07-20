from __future__ import annotations

from typing import Union, Optional
from sprites import *

# Type Alias
BOARD_SPRITES = List[List[List[Union[Piece, Empty]]]]
BOARD = List[List[List[Union[Player, None]]]]
MOVE = Tuple[Optional[COORDINATES], COORDINATES, Optional[COORDINATES]]

POSSIBLE_MOVES = {
    (0, 0, 0): {(0, 0, 1), (0, 1, 0)},
    (0, 0, 1): {(0, 0, 0), (0, 0, 2), (1, 0, 1)},
    (0, 0, 2): {(0, 0, 1), (0, 1, 2)},
    (0, 1, 0): {(1, 1, 0), (0, 0, 0), (0, 2, 0)},
    (0, 1, 2): {(1, 1, 2), (0, 0, 2), (0, 2, 2)},
    (0, 2, 0): {(0, 2, 1), (0, 1, 0)},
    (0, 2, 1): {(0, 2, 0), (0, 2, 2), (1, 2, 1)},
    (0, 2, 2): {(0, 2, 1), (0, 1, 2)},
    (1, 0, 0): {(1, 0, 1), (1, 1, 0)},
    (1, 0, 1): {(1, 0, 0), (1, 0, 2), (0, 0, 1), (2, 0, 1)},
    (1, 0, 2): {(1, 0, 1), (1, 1, 2)},
    (1, 1, 0): {(0, 1, 0), (2, 1, 0), (1, 0, 0), (1, 2, 0)},
    (1, 1, 2): {(2, 1, 2), (0, 1, 2), (1, 0, 2), (1, 2, 2)},
    (1, 2, 0): {(1, 2, 1), (1, 1, 0)},
    (1, 2, 1): {(1, 2, 0), (1, 2, 2), (2, 2, 1), (0, 2, 1)},
    (1, 2, 2): {(1, 2, 1), (1, 1, 2)},
    (2, 0, 0): {(2, 0, 1), (2, 1, 0)},
    (2, 0, 1): {(2, 0, 0), (2, 0, 2), (1, 0, 1)},
    (2, 0, 2): {(2, 0, 1), (2, 1, 2)},
    (2, 1, 0): {(1, 1, 0), (2, 0, 0), (2, 2, 0)},
    (2, 1, 2): {(1, 1, 2), (2, 0, 2), (2, 2, 2)},
    (2, 2, 0): {(2, 2, 1), (2, 1, 0)},
    (2, 2, 1): {(2, 2, 0), (2, 2, 2), (1, 2, 1)},
    (2, 2, 2): {(2, 2, 1), (2, 1, 2)},
}


def convert_board(board: BOARD_SPRITES) -> BOARD:
    def get_field(field: Piece | Empty) -> None | Player:
        if isinstance(field, Empty):
            return None
        else:
            if field.player == Player.BLACK:
                return Player.BLACK
            else:
                return Player.WHITE

    return [[[get_field(board[r][x][y]) for y in range(3)] for x in range(3)] for r in range(3)]


class KI:
    def __init__(self, level: int = 0):
        self.level = level

    def set_level(self, level: int) -> None:
        self.level = level

    def get_move(self, board: BOARD_SPRITES, player: Player, status: GameStatus) -> MOVE:
        board = convert_board(board)
        if self.level <= 0:
            # random move
            return self._get_random_move(board, player, status)

        return (1, 1, 1), (1, 1, 1), None

    def _get_random_move(self, board: BOARD, player: Player, status: GameStatus) -> MOVE:
        pass
