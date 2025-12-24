import pickle
import socket
import threading
import re
from typing import Dict, Tuple, List, Type, Any, Callable, overload
from _collections_abc import Iterable
from collections import namedtuple
from sortedcontainers import SortedList

GAME_FIELD_WIDTH: int = 81 # starts from 1
GAME_FIELD_HEIGHT: int = 21 # starts from 1
MIN_X: int = 0
MIN_Y: int = 0
MAX_X: int = MIN_X + (GAME_FIELD_WIDTH - 1) # starts from 0
MAX_Y: int = MIN_Y + (GAME_FIELD_HEIGHT - 1) # starts from 0

class colors:
    NONE: None = None
    GRAY: str = '\033[90m'
    WHITE: str = '\033[37m'
    RAINBOW: str = "RAINBOW"
    GREEN: str = '\033[92m'
    BLUE: str = '\033[94m'
    YELLOW: str = '\033[93m'
    RED: str = '\033[91m'
    ENDC: str = '\033[0m'

class face_values:
    HOSPITAL: str = "☩"
    BARRACKS: str = "ⵌ"
    LEVEL_BANDAGE: str = "☛"
    FACE_VALUE_BANDAGE: str = "+"
    COMBINED_BANDAGE: str = "⇄"
    PLUS_2: str = "+2"
    NUM1: str = "1"
    NUM2: str = "2"
    NUM3: str = "3"
    NUM4: str = "4"
    NUM5: str = "5"
    NUM6: str = "6"
    NUM7: str = "7"
    NUM8: str = "8"
    NUM9: str = "9"
PHARAOH: str = "↰"
SUPER_BUILDING_PREFIX: str = "SUP"

CURSOR_UP: str = "▲"
CURSOR_DOWN: str = "▼"
CURSOR_RIGHT: str = "▶"
CURSOR_LEFT: str = "◀"

UPPER_FIELD_BORDER: str = ("╭" + "─" * (GAME_FIELD_WIDTH - 2) + "╮")
LOWER_FIELD_BORDER: str = ("╰" + "─" * (GAME_FIELD_WIDTH - 2) + "╯")
LATERAL_FIELD_BORDER_CHARACTER: str = "│"
PLAYER_SIDE_BORDER: str = ("-" * (GAME_FIELD_WIDTH - 2))

PLAYER_COLORS: List[str] = [colors.NONE, colors.BLUE, colors.YELLOW] # PLAYER_COLORS[0] is colors.NONE so that each player's corresponding color is at the index player_num, not player_num - 1
MAIN_COLORS: List[str] = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]
SUPER_COLORS: List[str] = [colors.RAINBOW]
WARRIOR_FACE_VALUES: List[str] = [face_values.NUM1, face_values.NUM2, face_values.NUM3, 
                                  face_values.NUM4, face_values.NUM5, face_values.NUM6, 
                                  face_values.NUM7, face_values.NUM8, face_values.NUM9, face_values.PLUS_2]
BANDAGE_FACE_VALUES: List[str] = [face_values.FACE_VALUE_BANDAGE, face_values.LEVEL_BANDAGE, face_values.COMBINED_BANDAGE]
BUILDING_FACE_VALUES: List[str] = [face_values.HOSPITAL, face_values.BARRACKS]
SUPER_BUILDING_FACE_VALUES: List[str] = [SUPER_BUILDING_PREFIX + face_values.BARRACKS]

Coordinates = namedtuple("Coordinates", ["x", "y"])

def remove_color_codes(s: str) -> str:
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', s)

def index_by_identity(iterable: Iterable, obj: Any) -> int | None:
    for i, item in enumerate(iterable):
        if item is obj:  # ← identity comparison
            return i
    return None

class classproperty:
    def __init__(self, fget):
        self.fget = fget
    def __get__(self, instance, owner):
        return self.fget(owner)

class Entity:
    def __init__(self, content: str, color: str = colors.GRAY, coords: Coordinates = None, selectable: bool = False, public: bool = False, help_string: str = "") -> None:
        if not hasattr(self, 'content'):
            self.content: str = content
        if not hasattr(self, 'color'):
            self.color: str = color
        self.selectable = selectable
        self.coords = Coordinates(coords[0], coords[1]) if coords else None # an Entity with no coords will not be displayed unless it is a part of a larger structure, which will display it
        self.public = public
        self.help_string = help_string

    def __repr__(self) -> str:
        return_str: str = ''
        if self.color == colors.RAINBOW:
            for i in range(0, len(self.content)):
                return_str += (MAIN_COLORS[i%4] + self.content[i] + colors.ENDC)
        elif self.color == colors.NONE:
            return_str = self.content
        else:
            return_str = self.color + self.content + colors.ENDC

        return return_str
    
    def set_coords(self, new_coords: Coordinates) -> None:
        self.coords = new_coords

class Cursor(Entity):
    def __init__(self, shift_to_free_space_getter: Callable[[Entity], Tuple[int, int]], scope: SortedList[Entity] = []) -> None:
        self.selected = None
        self.__scope: SortedList[Entity] = scope
        self.get_shift_to_free_space = shift_to_free_space_getter
        super().__init__(content=CURSOR_UP, color=colors.WHITE, public=False)

    @property
    def selectable_scope(self) -> List[Entity]:
        scope: List[Entity] = []
        for entity in self.__scope:
            if entity.selectable:
                scope.append(entity)
            if isinstance(entity, CardList):
                for e in entity:
                    if e.selectable:
                        scope.append(e)

        return scope
    
    @property
    def index_in_scope(self) -> int | None:
        return index_by_identity(iterable = self.selectable_scope, obj = self.selected)
    
    def set_scope(self, new_scope: SortedList[Entity]) -> None:
        self.hide()
        self.__scope = new_scope
        self.show()
    
    def get_scope(self) -> SortedList[Entity]:
        return self.__scope

    def show(self) -> None:
        if len(self.selectable_scope) > 0 and self not in self.__scope:
            self.select(index_in_scope = 0)
    
    def hide(self) -> None:
        if self in self.__scope:
            self.__scope.remove(self)
    
    def select(self, index_in_scope: int) -> None:
        self.selected = self.selectable_scope[index_in_scope]
        self.__scope.discard(self)

        shift = self.get_shift_to_free_space(self.selected)
        icons = {
            (0,  1): CURSOR_UP,
            (0, -1): CURSOR_DOWN,
            (-1,  0): CURSOR_RIGHT,
            (len(self.selected.content),  0): CURSOR_LEFT
        }
        self.coords = Coordinates(self.selected.coords.x + shift[0], self.selected.coords.y + shift[1])
        self.content = icons[shift]
            
        self.__scope.add(self)
    
    def select_next(self) -> None:
        index_in_scope: int = index_by_identity(iterable = self.selectable_scope, obj = self.selected)
        if (index_in_scope != len(self.selectable_scope) - 1):
            self.select(index_in_scope + 1)
    
    def select_previous(self) -> None:
        index_in_scope: int = index_by_identity(iterable = self.selectable_scope, obj = self.selected)
        if (index_in_scope != 0):
            self.select(index_in_scope - 1)

class CardState():
    def __init__(self, level: str, face_value: str, pos_in_level: int, specific_states: Dict = {}) -> None:
        self.level = level
        self.face_value = face_value
        self.pos_in_level = pos_in_level
        self.specific_states = specific_states # syntax: {'name': str, 'value': Any}
    
    def __eq__(self, other: 'CardState') -> bool:
        if not isinstance(other, CardState):
            return False
        return self.level == other.level and self.pos_in_level == other.pos_in_level

    def __hash__(self) -> int:
        return hash(self.level, self.pos_in_level)

class Card(Entity):
    STATES: List[CardState] = [] # MANDATORY OVERRIDE
    TYPE_NAME: str = "Cards"
    SUPPORTS_VALUE_UPGRADES: bool = True

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.COUNT = len(cls.STATES)
        cls.LAST_STATE_INDEX = cls.COUNT - 1

    @overload
    def __init__(self, state_index: int, coords: Coordinates = None, selectable: bool = True, public: bool = False) -> None: ...
    @overload
    def __init__(self, state: CardState, coords: Coordinates = None, selectable: bool = True, public: bool = False) -> None: ...

    def __init__( # provide either state or state index, but not both. if card coordinates are None, it should be a part of a CardList
        self, 
        state: CardState = None, 
        state_index: int = None, 
        coords: Coordinates = None,
        selectable: bool = True, 
        public: bool = False
    ) -> None:
        """provide either state or state index, but not both. if card coordinates are None, it should be a part of a CardList"""
        if not (state == None) ^ (state_index == None):
            raise ValueError("state xor state_index must be provided")

        if state is not None:
            self.state = state
            self.state_index = type(self).STATES.index(state)
        else:
            self.state_index = state_index
            self.state = type(self).STATES[self.state_index]

        super().__init__(
            content = self.content, 
            coords = coords,
            color = self.color,
            selectable = selectable,
            public = public
        )
    
    @property
    def color(self) -> str:
        return self.state.level
    
    @property
    def content(self) -> str:
        return self.state.face_value

    def __eq__(self, other: 'Card') -> bool:
        return type(self) == type(other) and self.state == other.state

    def __hash__(self) -> int:
        return hash((type(self), self.state_index))
    
    def upgrade_level(self, by: int = 1) -> None:
        index_iterator = self.state_index

        while index_iterator < type(self).LAST_STATE_INDEX and by > 0:
            index_iterator += 1
            new_state = type(self).STATES[index_iterator]
            if new_state.level != self.state.level and new_state.pos_in_level == self.state.pos_in_level:
                self.state_index = index_iterator
                self.state = new_state
                by -= 1
        
        if type(self).SUPPORTS_VALUE_UPGRADES and index_iterator == type(self).LAST_STATE_INDEX and by > 0:
            self.state_index = index_iterator
            self.state = type(self).STATES[index_iterator]

    def upgrade_value(self, by: int = 1) -> None:
        self.state_index = min(self.state_index + by, type(self).LAST_STATE_INDEX)
        self.state = type(self).STATES[self.state_index]

#TODO: #2

class BandageCard(Card):
    STATES: List[CardState] = [CardState(level = level, face_value = face_value, pos_in_level = BANDAGE_FACE_VALUES.index(face_value)) for level in MAIN_COLORS for face_value in BANDAGE_FACE_VALUES]
    TYPE_NAME: str = "Bandages"

class BuildingCard(Card):
    STATES: List[CardState] = ([CardState(level = level, face_value = face_value, pos_in_level = BUILDING_FACE_VALUES.index(face_value)) for level in MAIN_COLORS for face_value in BUILDING_FACE_VALUES] + 
                               [CardState(level = level, face_value = face_value, pos_in_level = SUPER_BUILDING_FACE_VALUES.index(face_value)) for level in SUPER_COLORS for face_value in SUPER_BUILDING_FACE_VALUES])
    SUPPORTS_VALUE_UPGRADES = False
    TYPE_NAME: str = "Buildings"

    def __init__(self, building_type: str, level: str = colors.GREEN, coords: Coordinates = None, public: bool = True) -> None:
        #TODO: fix docstring
        try:
            state = next(state for state in type(self).STATES if state.level == level and state.face_value == building_type)
        except StopIteration:
            raise ValueError(f"{building_type} cannot be of level {level}")
        
        super().__init__(state = state, coords = coords, public = public)

class WarriorCard(Card):
    STATES: List[CardState] = [CardState(level = level, face_value = face_value, pos_in_level = WARRIOR_FACE_VALUES.index(face_value)) for level in MAIN_COLORS for face_value in WARRIOR_FACE_VALUES]
    TYPE_NAME: str = "Warriors"
    def __init__(self, coords: Coordinates = None, power: int = 0, public: bool = False) -> None:
        #TODO: fix docstring
        super().__init__(state_index = power, coords = coords, public = public)

class GuardCard(WarriorCard):
    TYPE_NAME: str = "Guards"
    def __init__(self, coords: Coordinates = None, power: int = 0, public: bool = True) -> None:
        super().__init__(power = power, coords = coords, public = public)

class CardList(Entity):
    def __init__(self, coords: Coordinates, card_type: Type[Card], cards: List[Card] | None = None, selectable: bool = True, public: bool = True) -> None:
        self.card_type: Type[Card] = card_type
        self.__cards: List[Card] = cards if cards is not None else []
        super().__init__(content = self.content, coords = coords, color = colors.NONE, selectable = selectable, public = public)
    
    def __repr__(self) -> str:
        return self.label_string
    
    @property
    def content(self) -> str:
        return repr(self)
    
    @property
    def label_string(self) -> str:
        return self.card_type.TYPE_NAME + ":"
    
    def get_public_slice(self) -> 'CardList':
        public_cards: List[Card] = [card for card in self.__cards if card.public]
        return CardList(coords = self.coords, card_type = self.card_type, cards = public_cards, public = True)

    def remove(self, card: Card) -> None:
        self.__cards.remove(card)
    
    def append(self, card: Card) -> None:
        self.__cards.append(card)
        self.update_card_coordinates(index = len(self.__cards) - 1)
    
    def __setitem__(self, index: int, card: Card) -> None:
        card.coords = self.__cards[index].coords
        self.__cards[index] = card

    @overload
    def update_card_coordinates(self, begin: int, end: int) -> None: ...
    @overload
    def update_card_coordinates(self, index: int) -> None: ...

    def update_card_coordinates(self, begin: int = None, end: int = None, index: int = 0):
        for i in range(begin if begin is not None else index, end if end is not None else (index + 1)):
            self.__cards[i].coords = Coordinates(self.coords.x + len(self.label_string) + (i * 2 + 1), self.coords.y) # index is multiplied by two, because the cards are separated by whitespaces

    def set_coords(self, new_coords) -> None:
        if self.coords != new_coords:
            super().set_coords(new_coords)
            self.update_card_coordinates(begin = 0, end = len(self.__cards))

    def __getitem__(self, index: int) -> Card:
        return self.__cards[index]
    
    def __bool__(self) -> bool:
        return self is not None
    
    def __len__(self) -> int:
        return len(self.__cards)
    
    def __iter__(self):
        return iter(self.__cards) 
    
    def __contains__(self, card: Card) -> bool:
        if not isinstance(card, self.card_type):
            return False
        return any((c == card) for c in self.__cards)

SOCKET_END_MSG: bytes = b"<END>"
SOCKET_CONNECTION_ESTABLISHED: bytes = b"CONNECTION ESTABLISHED"
SOCKET_LOBBY_FULL: bytes = b"LOBBY FULL"
SOCKET_SHARED_ENTITIES_UPDATE: bytes = b"SHARED ENTITIES UPDATE"
SOCKET_YOUR_TURN: bytes = b"YOUR TURN"
SOCKET_TERMINATION_REQUEST = b"TERMINATE"

class TerminationRequest(Exception):
    pass

def recvall(conn: socket.socket) -> bytes:
    data: bytes = b''
    while SOCKET_END_MSG not in data:
        more: bytes = conn.recv(1)
        if not more:
            raise ConnectionError
        data += more
    stripped_data = data[:-5]
    if stripped_data == SOCKET_TERMINATION_REQUEST:
        raise TerminationRequest
    return stripped_data

def sendall_with_end(s: socket.socket, message: bytes) -> None:
    s.sendall(message + SOCKET_END_MSG)