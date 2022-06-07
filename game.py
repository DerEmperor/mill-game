from __future__ import annotations

import pygame as pg
import pygame_widgets as pgw
from pygame_widgets.button import Button
from pygame_widgets.dropdown import Dropdown
from pygame.locals import *
from typing import List, Tuple, Any
from enum import Enum, auto

if not pg.font:
    print("Warning, fonts disabled")
if not pg.mixer:
    print("Warning, sound disabled")

# Type alias
COORDINATES = Tuple[int, int, int]
SCREEN_COORDINATES = Tuple[int, int]

# Constants
_SIZE = (1000, 850)
_PIECE_SIZE = (60, 60)  # (68, 68)
_FIELD_SIZE = (25, 25)
_MOUSE_SIZE = (20, 20)

_FONT_SIZE = 32

# pixel positions
_POSITIONS_BANK_WHITE = [(50, y) for y in range(95, 896, 89)]
_POSITIONS_BANK_BLACK = [(951, y) for y in range(94, 895, 89)]
_POSITIONS_BOARD = [
    [
        [(150, 100), (500, 100), (850, 100)],
        [(150, 450), (500, 450), (850, 450)],
        [(150, 800), (500, 800), (850, 800)],
    ],
    [
        [(265, 215), (500, 215), (734, 215)],
        [(265, 450), (500, 450), (734, 450)],
        [(265, 684), (500, 684), (734, 684)],
    ],
    [
        [(382, 332), (500, 332), (617, 332)],
        [(382, 450), (500, 450), (617, 450)],
        [(382, 567), (500, 567), (617, 567)],
    ],
]
# x and z are wrong => transpose inner 2d lists
_POSITIONS_BOARD = [[list(x) for x in zip(*matrix)] for matrix in _POSITIONS_BOARD]


class CodeUnreachable(Exception):
    pass


class FatalError(Exception):
    pass


class AccessIllegalField(Exception):
    pass


class IllegalMove(Exception):
    pass


class Player(Enum):
    BLACK = 'black'
    WHITE = 'white'

    def get_next(self):
        if self == Player.BLACK:
            return Player.WHITE
        else:
            return Player.BLACK

    def get_repr_1_char(self):
        if self == Player.BLACK:
            return 'b'
        else:
            return 'w'


class Action(Enum):
    PLACE = 'Place a piece from your bank to the board.'
    MOVE = 'Move one of your pieces on the board.'
    FLY = 'Fly one of your pieces on the board.'
    REMOVE = 'Remove one of your opponents piece from the board.'
    WAIT = 'Wait for AI to make a move'
    OVER = 'Game is over.'


class GameStatus(Enum):
    PLACING = auto()
    PLACING_REMOVING = auto()
    MOVING = auto()
    MOVING_REMOVING = auto()
    WAIT = auto()
    OVER = auto()
    QUIT = auto()


class Direction(Enum):
    UP = 'u'
    DOWN = 'd'
    LEFT = 'l'
    RIGHT = 'r'


class PieceStatus(Enum):
    OUT = 'out'
    BOARD = 'board'
    REMOVED = 'removed'


class Mouse(pg.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pg.image.load('pictures/mouse.png').convert_alpha()
        self.image = pg.transform.smoothscale(self.image, _MOUSE_SIZE)
        self.rect = self.image.get_rect()
        self.radius = _MOUSE_SIZE[0] / 2

    def update(self):
        """move the fist based on the mouse position"""
        pos = pg.mouse.get_pos()
        self.rect.topleft = pos


class Empty(pg.sprite.Sprite):
    def __init__(self, coords: COORDINATES):
        super().__init__()
        self.image = pg.Surface(_FIELD_SIZE)
        self.on_board = True
        self.position: COORDINATES | int = coords
        self.rect = self.image.get_rect()
        self.rect.center = _get_board_position(coords)
        self.radius = _FIELD_SIZE[0] / 2
        self.player: Player | None = None

    def set_position(self, coords: COORDINATES) -> None:
        self.position = coords
        self.rect.center = _get_board_position(coords)


class Piece(pg.sprite.Sprite):
    def __init__(self, position: COORDINATES | int, player: Player):
        super().__init__()
        self.player = player
        self.movable = False
        if player == Player.WHITE:
            self.image = pg.image.load('pictures/piece_white.png').convert_alpha()
        else:
            self.image = pg.image.load('pictures/piece_black.png').convert_alpha()
        self.image = pg.transform.smoothscale(self.image, _PIECE_SIZE)
        self.status = PieceStatus.OUT
        self.position: COORDINATES | int = position
        self.rect = self.image.get_rect()
        self.radius = _PIECE_SIZE[0] / 2

    def set_position(self, coords: COORDINATES) -> None:
        self.position = coords
        if self.status == PieceStatus.BOARD:
            self.rect.center = _get_board_position(coords)
        else:
            raise IllegalMove("You can't move a piece that's not on the board")


class Game:
    """
    board is 3d list:
    r(ing): outer, middle, inner ring
    ---> x
    |
    |
    v
    y

    ┌────────┬────────┐
    │  ┌─────┼─────┐  │
    │  │  ┌──┴──┐  │  │
    ├──┼──┤     ├──┼──┤
    │  │  └──┬──┘  │  │
    │  └─────┼─────┘  │
    └────────┴────────┘
    """

    def __init__(self):
        # init_pygame
        pg.init()
        self.screen = pg.display.set_mode(_SIZE, flags=pg.SCALED, vsync=1)
        pg.display.set_caption('Mill game')
        pg.display.set_icon(pg.image.load('pictures/icon.png'))
        pg.mouse.set_visible(False)
        self.background = pg.image.load('pictures/background.png').convert()
        self.background = pg.transform.smoothscale(self.background, _SIZE)
        self.mouse = Mouse()
        self.mouse_sprites = pg.sprite.Group(self.mouse)

        self.refresh_button, self.ai_level_white_dropdown, self.ai_level_black_dropdown = self._create_widgets()
        self.winning_sound = _load_sound('sounds/tada.wav')
        self.no_sound = _load_sound('sounds/chord.wav')

        # images
        # indicate whose turn it is
        self.black_piece_img_turn = pg.image.load('pictures/piece_black.png').convert_alpha()
        self.black_piece_img_turn = pg.transform.smoothscale(self.black_piece_img_turn, (44, 44))

        self.white_piece_img_turn = pg.image.load('pictures/piece_white.png').convert_alpha()
        self.white_piece_img_turn = pg.transform.smoothscale(self.white_piece_img_turn, (44, 44))

        # indicates last turn via piece
        self.black_piece_img_last = pg.image.load('pictures/piece_black.png').convert_alpha()
        self.black_piece_img_last = pg.transform.smoothscale(self.black_piece_img_last, _PIECE_SIZE)
        self.black_piece_img_last.fill((255, 255, 255, 128), None, pg.BLEND_RGBA_MULT)

        self.white_piece_img_last = pg.image.load('pictures/piece_white.png').convert_alpha()
        self.white_piece_img_last = pg.transform.smoothscale(self.white_piece_img_last, _PIECE_SIZE)
        self.white_piece_img_last.fill((255, 255, 255, 128), None, pg.BLEND_RGBA_MULT)

        # highlights last turn
        self.yellow_circle = pg.Surface(_PIECE_SIZE, pg.SRCALPHA)
        pg.draw.circle(self.yellow_circle, (255, 255, 0, 128 // 3), (_PIECE_SIZE[0] / 2, _PIECE_SIZE[1] / 2),
                       _PIECE_SIZE[0] / 2)

        self.red_circle = pg.Surface(_PIECE_SIZE, pg.SRCALPHA)
        pg.draw.circle(self.red_circle, (255, 0, 0, 128 // 3), (_PIECE_SIZE[0] / 2, _PIECE_SIZE[1] / 2),
                       _PIECE_SIZE[0] / 2)

        # init pieces
        self.moving_piece: Piece | None = None
        self.board: List[List[List[Piece | Empty]]] = [[[(None if x == y == 1 else Empty((ring, x, y)))
                                                         for y in range(3)] for x in range(3)] for ring in range(3)]
        self.piece_bank_white: List[Piece | Empty] = [Piece(i, Player.WHITE) for i in range(9)]
        self.piece_bank_black: List[Piece | Empty] = [Piece(i, Player.BLACK) for i in range(9)]
        for (piece, position) in zip(self.piece_bank_white, _POSITIONS_BANK_WHITE):
            piece.rect.center = position
        for (piece, position) in zip(self.piece_bank_black, _POSITIONS_BANK_BLACK):
            piece.rect.center = position
        self.pieces = pg.sprite.Group((*self.piece_bank_white, *self.piece_bank_black))
        self.empty_fields = pg.sprite.Group([e for e in _flatten(self.board) if e])

        # init game properties
        self.fly_white = False
        self.fly_black = False
        self.status = GameStatus.PLACING
        self.player = Player.WHITE
        self.pieces_left_white = 9
        self.pieces_left_black = 9
        self.action = Action.PLACE
        self.winner: Player | None = None
        self.ai_level_white = -1
        self.ai_level_black = -1
        self.last_move: Tuple[SCREEN_COORDINATES, SCREEN_COORDINATES] | None = None
        self.last_remove: SCREEN_COORDINATES | None = None

    def _create_widgets(self) -> Tuple[Button, Dropdown, Dropdown]:
        # buttons
        restart_button = Button(
            # Mandatory Parameters
            self.screen,  # Surface to place button on
            805,  # X-coordinate of top left corner
            5,  # Y-coordinate of top left corner
            90,  # Width
            40,  # Height

            # Optional Parameters
            text='restart',  # Text to display
            fontSize=_FONT_SIZE,  # Size of font
            textColour=(0, 255, 0),
            margin=20,  # Minimum distance between text/image and edge of button
            inactiveColour=(200, 50, 0),  # Colour of button when not being interacted with
            hoverColour=(150, 25, 0),  # Colour of button when being hovered over
            pressedColour=(100, 0, 0),  # Colour of button when being clicked
            radius=10,  # Radius of border corners (leave empty for not curved)
            onRelease=self.restart,  # Function to call when button released
        )

        ai_level_white = Dropdown(
            self.screen,
            5,
            5,
            90,
            40,
            name='player',
            choices=['player', 'random', *[f'level {i}' for i in range(1, 10)]],
            borderRadius=10,
            inactiveColour=(0, 0, 255),  # Colour of button when not being interacted with
            hoverColour=(0, 0, 139),  # Colour of button when being hovered over
            pressedColour=(0, 0, 128),  # Colour of button when being clicked
            values=list(range(-1, 10)),
            textColour=(0, 255, 0),
            fontSize=_FONT_SIZE,
            direction='down',
            onRelease=self._set_ai_level,
            onReleaseParams=(Player.WHITE,),

        )

        ai_level_black = Dropdown(
            self.screen,
            905,
            5,
            90,
            40,
            name='player',
            choices=['player', 'random', *[f'level {i}' for i in range(1, 10)]],
            borderRadius=10,
            inactiveColour=(0, 0, 255),  # Colour of button when not being interacted with
            hoverColour=(0, 0, 139),  # Colour of button when being hovered over
            pressedColour=(0, 0, 128),  # Colour of button when being clicked
            values=list(range(-1, 10)),
            textColour=(0, 255, 0),
            fontSize=_FONT_SIZE,
            direction='down',
            onRelease=self._set_ai_level,
            onReleaseParams=(Player.BLACK,),

        )
        return restart_button, ai_level_white, ai_level_black

    def restart(self) -> None:
        # init pieces
        self.moving_piece: Piece | None = None
        self.board: List[List[List[Piece | Empty]]] = [[[(None if x == y == 1 else Empty((ring, x, y)))
                                                         for y in range(3)] for x in range(3)] for ring in range(3)]
        self.piece_bank_white: List[Piece | Empty] = [Piece(i, Player.WHITE) for i in range(9)]
        self.piece_bank_black: List[Piece | Empty] = [Piece(i, Player.BLACK) for i in range(9)]
        for (piece, position) in zip(self.piece_bank_white, _POSITIONS_BANK_WHITE):
            piece.rect.center = position
        for (piece, position) in zip(self.piece_bank_black, _POSITIONS_BANK_BLACK):
            piece.rect.center = position
        self.pieces = pg.sprite.Group((*self.piece_bank_white, *self.piece_bank_black))
        self.empty_fields = pg.sprite.Group([e for e in _flatten(self.board) if e])

        # init game properties
        self.fly_white = False
        self.fly_black = False
        self.status = GameStatus.PLACING
        self.player = Player.WHITE
        self.pieces_left_white = 9
        self.pieces_left_black = 9
        self.action = Action.PLACE
        self.winner = None
        self.last_move = None
        self.last_remove = None

    def run_game(self) -> None:
        # game loop:
        while self.status != GameStatus.QUIT:
            # --- Main event loop
            events = pg.event.get()
            for event in events:
                # User did something
                if event.type == pg.QUIT:
                    # user clicked close, flag that we are done, so we exit this loop
                    self.status = GameStatus.QUIT

                # update mouse
                self.mouse.update()

                if self.status == GameStatus.PLACING:
                    self._handle_placing(event)
                elif self.status == GameStatus.MOVING:
                    self._handle_moving(event)
                elif self.status in (GameStatus.PLACING_REMOVING, GameStatus.MOVING_REMOVING):
                    self._handle_removing(event)
                elif self.status == GameStatus.WAIT:
                    pass
                elif self.status == GameStatus.OVER:
                    pass
                elif self.status == GameStatus.QUIT:
                    pass
                else:
                    raise CodeUnreachable

            self._draw_game(events)

            # update screen
            pg.display.flip()

        # Close the window and quit.
        pg.quit()

    def _handle_placing(self, event: pg.Event) -> None:
        if event.type == MOUSEBUTTONDOWN:
            self.moving_piece = _get_collides(self.mouse, self.pieces)
            if self.moving_piece:
                if self.moving_piece.status != PieceStatus.OUT or self.moving_piece.player != self.player:
                    self.no_sound.play()
                    self.moving_piece = None

        elif event.type == MOUSEBUTTONUP:
            if self.moving_piece:
                field = _get_collides(self.moving_piece, self.empty_fields)
                if field:
                    if not field.on_board:
                        self.no_sound.play()
                        # snap back
                        self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                    else:
                        self.place_piece(field.position, self.player, self.moving_piece.position)
                        self.last_remove = None
                        bank = _POSITIONS_BANK_BLACK if self.player == Player.BLACK else _POSITIONS_BANK_WHITE
                        self.last_move = (bank[field.position], _get_board_position(self.moving_piece.position))
                        if self.player == Player.WHITE:
                            self.pieces_left_white -= 1
                        else:
                            self.pieces_left_black -= 1

                        if self.forms_mill(self.moving_piece.position):
                            self.status = GameStatus.PLACING_REMOVING
                            self.action = Action.REMOVE
                        else:
                            # swap player
                            self.player = self.player.get_next()

                        if self.pieces_left_white == self.pieces_left_black == 0:
                            # placing finished
                            if self.status == GameStatus.PLACING_REMOVING:
                                self.status = GameStatus.MOVING_REMOVING
                            else:
                                self.status = GameStatus.MOVING
                                self.action = Action.MOVE
                            # count pieces
                            for r in range(3):
                                for x in range(3):
                                    for y in range(3):
                                        if x == y == 1:
                                            continue
                                        if isinstance(self.board[r][x][y], Piece):
                                            if self.board[r][x][y].player == Player.WHITE:
                                                self.pieces_left_white += 1
                                            else:
                                                self.pieces_left_black += 1

                else:
                    # snap back
                    self.no_sound.play()
                    pos = _POSITIONS_BANK_WHITE if self.player == Player.WHITE else _POSITIONS_BANK_BLACK
                    self.moving_piece.rect.center = pos[self.moving_piece.position]
                self.moving_piece = None

        elif event.type == MOUSEMOTION and self.moving_piece:
            self.moving_piece.rect.move_ip(event.rel)

    def _handle_moving(self, event: pg.Event) -> None:
        if event.type == MOUSEBUTTONDOWN:
            self.moving_piece = _get_collides(self.mouse, self.pieces)
            if self.moving_piece:
                if self.moving_piece.status != PieceStatus.BOARD or self.moving_piece.player != self.player:
                    self.no_sound.play()
                    self.moving_piece = None

        elif event.type == MOUSEBUTTONUP:
            if self.moving_piece:
                field = _get_collides(self.moving_piece, self.empty_fields)
                if field:
                    if not field.on_board:
                        self.no_sound.play()
                        # snap back
                        self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                    else:
                        try:
                            if self.player == Player.WHITE and self.fly_white:
                                self.fly_piece(self.moving_piece.position, field.position, self.player)
                            elif self.player == Player.BLACK and self.fly_black:
                                self.fly_piece(self.moving_piece.position, field.position, self.player)
                            else:
                                self.move_piece_coords(self.moving_piece.position, field.position, self.player)
                        except IllegalMove:
                            self.no_sound.play()
                            # snap back
                            self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                        else:
                            self.last_remove = None
                            self.last_move = (
                                _get_board_position(field.position),
                                _get_board_position(self.moving_piece.position),
                            )
                            if self.forms_mill(self.moving_piece.position):
                                self.status = GameStatus.MOVING_REMOVING
                                self.action = Action.REMOVE
                            else:
                                # swap player
                                self.player = self.player.get_next()
                                # check if player can move
                                if not self.can_move(self.player):
                                    # player can't move -> player lost
                                    self.winning_sound.play()
                                    self.status = GameStatus.OVER
                                    self.action = Action.OVER
                                    self.winner = self.player.get_next()
                else:
                    self.no_sound.play()
                    # snap back
                    self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                self.moving_piece = None

        elif event.type == MOUSEMOTION and self.moving_piece:
            self.moving_piece.rect.move_ip(event.rel)

    def _handle_removing(self, event: pg.Event) -> None:
        if event.type == MOUSEBUTTONDOWN:
            self.moving_piece = _get_collides(self.mouse, self.pieces)
            if self.moving_piece:
                if self.moving_piece.status != PieceStatus.BOARD or self.moving_piece.player == self.player or \
                        self.forms_mill(self.moving_piece.position):
                    self.no_sound.play()
                    self.moving_piece = None

        elif event.type == MOUSEBUTTONUP:
            if self.moving_piece:
                field = _get_collides(self.moving_piece, self.empty_fields)
                if field:
                    if field.on_board or field.player != self.player:
                        self.no_sound.play()
                        # snap back
                        self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                    else:
                        self.remove_piece(self.moving_piece.position, self.player.get_next(), field.position)
                        self.last_remove = _get_board_position(field.position)
                        if self.status == GameStatus.MOVING_REMOVING:
                            if self.player == Player.WHITE:
                                self.pieces_left_black -= 1
                            else:
                                self.pieces_left_white -= 1

                        if self.status == GameStatus.PLACING_REMOVING:
                            self.status = GameStatus.PLACING
                            self.action = Action.PLACE

                        elif self.status == GameStatus.MOVING_REMOVING:
                            # flying?
                            if self.pieces_left_white == 3:
                                self.fly_white = True
                            if self.pieces_left_black == 3:
                                self.fly_black = True
                            # game end?
                            if self.pieces_left_white == 2 or self.pieces_left_black == 2 or \
                                    not self.can_move(self.player.get_next()):
                                # game finished
                                self.winning_sound.play()
                                self.status = GameStatus.OVER
                                self.action = Action.OVER
                                self.winner = self.player
                            else:
                                # move again
                                self.status = GameStatus.MOVING
                                if self.player == Player.WHITE and self.fly_white:
                                    self.action = Action.FLY
                                elif self.player == Player.BLACK and self.fly_black:
                                    self.action = Action.FLY
                                else:
                                    self.action = Action.MOVE
                        else:
                            raise CodeUnreachable

                        # swap player
                        self.player = self.player.get_next()
                else:
                    # snap back
                    self.no_sound.play()
                    self.moving_piece.rect.center = _get_board_position(self.moving_piece.position)
                self.moving_piece = None

        elif event.type == MOUSEMOTION and self.moving_piece:
            self.moving_piece.rect.move_ip(event.rel)

    def _draw_game(self, events: List[pg.Event]) -> None:
        # board
        self.screen.blit(self.background, (0, 0))

        # pieces
        self.pieces.draw(self.screen)

        # last move
        if self.last_move:
            removing = self.status in (GameStatus.PLACING_REMOVING, GameStatus.MOVING_REMOVING)
            if (self.player == Player.BLACK) ^ removing:
                image = self.white_piece_img_last
            else:
                image = self.black_piece_img_last
            for pos in self.last_move:
                self.screen.blit(self.yellow_circle, (pos[0] - _PIECE_SIZE[0] // 2, pos[1] - _PIECE_SIZE[1] // 2))
            pos = self.last_move[0]
            self.screen.blit(image, (pos[0] - _PIECE_SIZE[0] // 2, pos[1] - _PIECE_SIZE[1] // 2))

        if self.last_remove:
            if self.player == Player.WHITE:
                image = self.white_piece_img_last
            else:
                image = self.black_piece_img_last
            pos = self.last_remove
            self.screen.blit(self.red_circle, (pos[0] - _PIECE_SIZE[0] // 2, pos[1] - _PIECE_SIZE[1] // 2))
            self.screen.blit(image, (pos[0] - _PIECE_SIZE[0] // 2, pos[1] - _PIECE_SIZE[1] // 2))

        # Action
        if pg.font:
            font = pg.font.Font(None, _FONT_SIZE)
            text = font.render(self.action.value, True, (0, 255, 0))
            text_pos = text.get_rect(centerx=517, centery=25)
            self.screen.blit(text, text_pos)

        # Players turn
        if pg.font:
            font = pg.font.Font(None, _FONT_SIZE)
            text = font.render("Player:", True, (0, 255, 0))
            text_pos = text.get_rect(x=105, centery=25)
            self.screen.blit(text, text_pos)
            if self.player == Player.WHITE:
                self.screen.blit(self.white_piece_img_turn, (183, 3))
            else:
                self.screen.blit(self.black_piece_img_turn, (183, 3))

        # buttons
        pgw.update(events)

        # winning
        if self.status == GameStatus.OVER and pg.font:
            font = pg.font.Font(None, 200)
            text = font.render(f'{self.winner.value} wins', True, (0, 255, 255))
            text_pos = text.get_rect(centerx=_SIZE[0] / 2, centery=_SIZE[1] / 2 + 25)
            self.screen.blit(text, text_pos)

        # mouse
        self.mouse_sprites.draw(self.screen)

    def _set_ai_level(self, player: Player) -> None:
        if player == Player.WHITE:
            self.ai_level_white = self.ai_level_white_dropdown.getSelected()
        if player == Player.BLACK:
            self.ai_level_black = self.ai_level_black_dropdown.getSelected()

    def get_field(self, coords: COORDINATES) -> Piece | Empty:
        r, x, y = coords
        return self.board[r][x][y]

    def set_field(self, coords: COORDINATES, value: Piece | Empty):
        r, x, y = coords
        self.board[r][x][y] = value

    def place_piece(self, dest: COORDINATES, player: Player, index: int = None) -> None:
        check_access(dest)

        if isinstance(self.get_field(dest), Piece):
            raise IllegalMove('Field is occupied.')

        empty_field: Empty = self.get_field(dest)

        bank = self.piece_bank_white if player == Player.WHITE else self.piece_bank_black
        if index:
            if not isinstance(bank[index], Piece):
                raise IllegalMove("There is no piece!")
            if player and bank[index].player != player:
                raise IllegalMove("That's not your piece")
        else:
            index = 0
            for i in range(9):
                if isinstance(bank[i], Piece) and (player is None or bank[i].player == player):
                    index = i
                    break

        piece = bank[index]
        bank[index] = empty_field
        empty_field.on_board = False
        empty_field.position = index
        pos = _POSITIONS_BANK_WHITE if player == Player.WHITE else _POSITIONS_BANK_BLACK
        empty_field.rect.center = pos[index]
        empty_field.player = player

        if not piece:
            raise IllegalMove("You have already placed all your pieces.")
        piece.status = PieceStatus.BOARD
        piece.set_position(dest)
        self.set_field(dest, piece)

    def fly_piece(self, src: COORDINATES, dest: COORDINATES, player: Player = None) -> None:
        if player == Player.WHITE and not self.fly_white:
            raise IllegalMove('You are not yet allowed to fly.')
        if player == Player.BLACK and not self.fly_black:
            raise IllegalMove('You are not yet allowed to fly.')

        self._move_piece(src, dest, player)

    def _swap(self, src: COORDINATES, dest: COORDINATES) -> None:
        sx, sy, sz = src
        dx, dy, dz = dest
        if self.board[sx][sy][sz]:
            self.board[sx][sy][sz].set_position(dest)
        if self.board[dx][dy][dz]:
            self.board[dx][dy][dz].set_position(src)
        self.board[sx][sy][sz], self.board[dx][dy][dz] = self.board[dx][dy][dz], self.board[sx][sy][sz]

    def _move_piece(self, src: COORDINATES, dest: COORDINATES, player: Player = None) -> None:
        if src[1] == src[2] == 1 or dest[1] == dest[2] == 1:
            raise AccessIllegalField("You can't access the \"middle\" field")
        piece = self.get_field(src)
        if player and piece.player != player:
            raise IllegalMove('Not your piece.')

        if isinstance(self.get_field(dest), Piece):
            raise IllegalMove('Field is occupied.')
        self._swap(src, dest)

    def move_piece_coords(self, src: COORDINATES, dest: COORDINATES, player: Player = None) -> None:
        reachable_fields = []
        for direction in Direction:
            if self.is_move_legal(src, direction):
                reachable_fields.append(self._get_dest_coord(src, direction))

        if dest not in reachable_fields:
            raise IllegalMove("You can't move there.")

        self._move_piece(src, dest, player)

    def remove_piece(self, coords: COORDINATES, player: Player = None, index: int = None) -> None:
        check_access(coords)

        piece = self.get_field(coords)
        if not piece:
            raise IllegalMove('Field is empty.')
        if player and piece.player != player:
            raise IllegalMove("Don't remove your piece.")
        if self.forms_mill(coords):
            raise IllegalMove("You can't remove a piece that forms a mill.")

        piece.status = PieceStatus.REMOVED

        # put in opponents bank
        bank = self.piece_bank_white if player == Player.BLACK else self.piece_bank_black
        bank_pos = _POSITIONS_BANK_WHITE if player == Player.BLACK else _POSITIONS_BANK_BLACK
        if index:
            if isinstance(bank[index], Piece):
                raise IllegalMove("Field is occupied")
        else:
            for i in range(9):
                if isinstance(bank[i], Empty):
                    index = i
                    break
        empty_field = bank[index]
        bank[index] = piece
        piece.rect.center = bank_pos[index]

        if not empty_field:
            raise FatalError('bank field is not defined correctly')

        self.set_field(coords, empty_field)
        empty_field.on_board = True
        empty_field.set_position(coords)
        empty_field.rect.center = _get_board_position(coords)
        empty_field.player = None

    def forms_mill(self, coords: COORDINATES) -> bool:
        check_access(coords)
        r, x, y = coords
        # vertical on ring
        if x in (0, 2):
            if self.board[r][x][0].player == self.board[r][x][1].player == self.board[r][x][2].player:
                return True

        # horizontal on ring
        if y in (0, 2):
            if self.board[r][0][y].player == self.board[r][1][y].player == self.board[r][2][y].player:
                return True

        # vertical between rings
        if x == 1:
            if self.board[0][x][y].player == self.board[1][x][y].player == self.board[2][x][y].player:
                return True

        # horizontal between rings
        if y == 1:
            if self.board[0][x][y].player == self.board[1][x][y].player == self.board[2][x][y].player:
                return True

        return False

    @staticmethod
    def _get_dest_coord(coords: COORDINATES, direction: Direction) -> COORDINATES | None:
        r, x, y = coords
        check_access(coords)

        # up
        if direction == Direction.UP:
            # move on same ring
            if y in (1, 2) and x in (0, 2):
                return r, x, y - 1
            # move to another ring
            if r in (0, 1) and x == 1 and y == 2:
                return r + 1, x, y
            if r in (1, 2) and x == 1 and y == 0:
                return r - 1, x, y

        # down
        if direction == Direction.DOWN:
            # move on same ring
            if y in (0, 1) and x in (0, 2):
                return r, x, y + 1
            # move to another ring
            if r in (0, 1) and x == 1 and y == 0:
                return r + 1, x, y
            if r in (1, 2) and x == 1 and y == 2:
                return r - 1, x, y

        # right
        if direction == Direction.RIGHT:
            # move on same ring
            if x in (0, 1) and y in (0, 2):
                return r, x + 1, y
            # move to another ring
            if r in (0, 1) and x == 0 and y == 1:
                return r + 1, x, y
            if r in (1, 2) and x == 2 and y == 1:
                return r - 1, x, y

        # left
        if direction == Direction.LEFT:
            # move on same ring
            if x in (1, 2) and y in (0, 2):
                return r, x - 1, y
            # move to another ring
            if r in (0, 1) and x == 2 and y == 1:
                return r + 1, x, y
            if r in (1, 2) and x == 0 and y == 1:
                return r - 1, x, y

        return None

    def can_move(self, player: Player) -> bool:
        pieces: List[Piece] = self.pieces.sprites()
        for piece in pieces:
            if piece.player != player or piece.status != PieceStatus.BOARD:
                continue
            if self.can_move_piece(piece.position):
                return True
        return False

    def can_move_piece(self, coords: COORDINATES) -> bool:
        if self.get_possible_directions(coords):
            return True
        else:
            return False

    def is_move_legal(self, coords: COORDINATES, direction: Direction) -> bool:
        check_access(coords)
        return self._get_dest_coord(coords, direction) is not None

    def get_possible_directions(self, coords: COORDINATES) -> List[Direction]:
        check_access(coords)

        field = self.get_field(coords)

        if isinstance(field, Empty):
            raise IllegalMove('Field is empty')

        legal_directions = []
        for direction in Direction:
            dest_coords = self._get_dest_coord(coords, direction)
            if dest_coords:
                if isinstance(self.get_field(dest_coords), Empty):
                    legal_directions.append(direction)
        return legal_directions

    def move_piece(self, coords: COORDINATES, direction: Direction, player: Player = None) -> None:
        check_access(coords)
        if isinstance(self.get_field(coords), Empty):
            raise IllegalMove('Field is empty')

        if player and player != self.get_field(coords).player:
            raise IllegalMove('This piece belongs to the other player.')

        if not self.is_move_legal(coords, direction):
            raise IllegalMove("You can't move there")

        dest = self._get_dest_coord(coords, direction)
        # swap
        self._swap(coords, dest)

    def get_board_as_str(self) -> str:
        """returns a str representation of the board"""
        string = \
            '{}────────{}────────{}\n'.format(
                '┌' if isinstance(self.board[0][0][0], Empty) else self.board[0][0][0].player.get_repr_1_char(),
                '┬' if isinstance(self.board[0][1][0], Empty) else self.board[0][1][0].player.get_repr_1_char(),
                '┐' if isinstance(self.board[0][2][0], Empty) else self.board[0][2][0].player.get_repr_1_char(),
            ) + \
            '│  {}─────{}─────{}  │\n'.format(
                '┌' if isinstance(self.board[1][0][0], Empty) else self.board[1][0][0].player.get_repr_1_char(),
                '┼' if isinstance(self.board[1][1][0], Empty) else self.board[1][1][0].player.get_repr_1_char(),
                '┐' if isinstance(self.board[1][2][0], Empty) else self.board[1][2][0].player.get_repr_1_char(),
            ) + \
            '│  │  {}──{}──{}  │  │\n'.format(
                '┌' if isinstance(self.board[2][0][0], Empty) else self.board[2][0][0].player.get_repr_1_char(),
                '┴' if isinstance(self.board[2][1][0], Empty) else self.board[2][1][0].player.get_repr_1_char(),
                '┐' if isinstance(self.board[2][2][0], Empty) else self.board[2][2][0].player.get_repr_1_char(),
            ) + \
            '{}──{}──{}     {}──{}──{}\n'.format(
                '├' if isinstance(self.board[0][0][1], Empty) else self.board[0][0][1].player.get_repr_1_char(),
                '┼' if isinstance(self.board[1][0][1], Empty) else self.board[1][0][1].player.get_repr_1_char(),
                '┤' if isinstance(self.board[2][0][1], Empty) else self.board[2][0][1].player.get_repr_1_char(),
                '├' if isinstance(self.board[2][2][1], Empty) else self.board[2][2][1].player.get_repr_1_char(),
                '┼' if isinstance(self.board[1][2][1], Empty) else self.board[1][2][1].player.get_repr_1_char(),
                '┤' if isinstance(self.board[0][2][1], Empty) else self.board[0][2][1].player.get_repr_1_char(),
            ) + \
            '│  │  {}──{}──{}  │  │\n'.format(
                '└' if isinstance(self.board[2][0][2], Empty) else self.board[2][0][2].player.get_repr_1_char(),
                '┬' if isinstance(self.board[2][1][2], Empty) else self.board[2][1][2].player.get_repr_1_char(),
                '┘' if isinstance(self.board[2][2][2], Empty) else self.board[2][2][2].player.get_repr_1_char(),
            ) + \
            '│  {}─────{}─────{}  │\n'.format(
                '└' if isinstance(self.board[1][0][2], Empty) else self.board[1][0][2].player.get_repr_1_char(),
                '┼' if isinstance(self.board[1][1][2], Empty) else self.board[1][1][2].player.get_repr_1_char(),
                '┘' if isinstance(self.board[1][2][2], Empty) else self.board[1][2][2].player.get_repr_1_char(),
            ) + \
            '{}────────{}────────{}\n'.format(
                '└' if isinstance(self.board[0][0][2], Empty) else self.board[0][0][2].player.get_repr_1_char(),
                '┴' if isinstance(self.board[0][1][2], Empty) else self.board[0][1][2].player.get_repr_1_char(),
                '┘' if isinstance(self.board[0][2][2], Empty) else self.board[0][2][2].player.get_repr_1_char(),
            )
        return string

    def print_board(self) -> None:
        """prints a str representation of the board"""
        print(self.get_board_as_str())


def _flatten(lists: List[List[Any | List[Any]]]) -> List[Any]:
    res = []
    for sublist in lists:
        if hasattr(sublist, '__iter__'):
            res.extend(_flatten(sublist))
        else:
            res.append(sublist)
    return res


def _get_board_position(coords: COORDINATES) -> SCREEN_COORDINATES:
    r, x, y = coords
    return _POSITIONS_BOARD[r][x][y]


def _load_sound(path):
    class NoneSound:
        def play(self):
            pass

    if not pg.mixer or not pg.mixer.get_init():
        return NoneSound()

    sound = pg.mixer.Sound(path)

    return sound


def _get_collides(sprite: Piece | Mouse, group: pg.sprite.AbstractGroup) -> Piece | Empty | None:
    collides = pg.sprite.spritecollide(sprite, group, False, pg.sprite.collide_circle)
    if len(collides) == 0:
        return None
    if len(collides) > 1:
        raise FatalError("Multiple Piece sprites overlap")
    return collides[0]


def check_access(coords) -> None:
    r, x, y = coords
    if r < 0 or r > 2:
        raise AccessIllegalField('r mest be in (0,1,2).')
    if x < 0 or x > 2:
        raise AccessIllegalField('x mest be in (0,1,2).')
    if y < 0 or y > 2:
        raise AccessIllegalField('y mest be in (0,1,2).')
    if x == y == 1:
        raise AccessIllegalField("You can't access the \"middle\" field")
