import pickle
import socket
import threading
import re
from enum import Enum, auto
from typing import Dict, Tuple, List, Type, Any, Callable, overload
from _collections_abc import Iterable
from collections import namedtuple
from sortedcontainers import SortedList

GAME_FIELD_WIDTH: int = 81
GAME_FIELD_HEIGHT: int = 21  
MIN_X: int = 0
MIN_Y: int = 0
MAX_X: int = GAME_FIELD_WIDTH - 1
MAX_Y: int = GAME_FIELD_HEIGHT - 1

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

MAIN_COLORS: List[str] = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]
SUPER_COLORS: List[str] = [colors.RAINBOW]
WARRIOR_FACE_VALUES: List[str] = [face_values.NUM1, face_values.NUM2, face_values.NUM3, 
                                  face_values.NUM4, face_values.NUM5, face_values.NUM6, 
                                  face_values.NUM7, face_values.NUM8, face_values.NUM9, face_values.PLUS_2]
BANDAGE_FACE_VALUES: List[str] = [face_values.FACE_VALUE_BANDAGE, face_values.LEVEL_BANDAGE, face_values.COMBINED_BANDAGE]
BUILDING_FACE_VALUES: List[str] = [face_values.HOSPITAL, face_values.BARRACKS]
SUPER_BUILDING_FACE_VALUES: List[str] = [(SUPER_BUILDING_PREFIX + face_value) for face_value in BUILDING_FACE_VALUES]

Coordinates = namedtuple("Coordinates", ["x", "y"])

def remove_color_codes(s: str) -> str:
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', s)

def index_by_identity(iterable: Iterable, obj: Any) -> int | None:
    for i, item in enumerate(iterable):
        if item is obj:  # ← identity comparison
            return i
    return None

class Entity:
    def __init__(self, content: str, color: str = colors.GRAY, display_priority: int = 0, coords: Coordinates = None, selectable: bool = False, public: bool = False) -> None:
        if not hasattr(self, 'content'):
            self.content: str = content
        if not hasattr(self, 'color'):
            self.color: str = color
        self.selectable = selectable
        self.coords = Coordinates(coords[0], coords[1]) if coords else None # an Entity with no coords will not be displayed unless it is a part of a larger structure, which will display it
        self.display_priority = display_priority # higher value means this Entity is drawn above others at the same position. negative number to hide the Entity from screen
        self.public = public

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
    def __init__(self, scope: SortedList[Entity] = []) -> None:
        self.selected = None
        self.__scope: SortedList[Entity] = scope
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

    def show(self) -> None:
        if len(self.selectable_scope) > 0 and self not in self.__scope:
            self.select(index_in_scope = 0)
    
    def hide(self) -> None:
        if self in self.__scope:
            self.__scope.remove(self)
    
    def select(self, index_in_scope: int) -> None:
        self.selected = self.selectable_scope[index_in_scope]
        self.__scope.discard(self)

        if (self.selected.coords.y == MAX_Y - 1):
            self.coords = Coordinates(self.selected.coords.x, self.selected.coords.y - 1)
            self.content = CURSOR_DOWN
        else:
            self.coords = Coordinates(self.selected.coords.x, self.selected.coords.y + 1)
            self.content = CURSOR_UP
            
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
    def __init__(self, state_index: int, coords: Tuple[int, int] = None, selectable: bool = True, public: bool = False) -> None: ...
    
    @overload
    def __init__(self, state: CardState, coords: Tuple[int, int] = None, selectable: bool = True, public: bool = False) -> None: ...

    def __init__( # provide either state or state index, but not both. if card coordinates are None, it should be a part of a CardList
        self, 
        state: CardState = None, 
        state_index: int = None, 
        coords: Tuple[int, int] = None,
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

    def __init__(self, building_type: str, level: str = colors.GREEN, coords: Tuple[int, int] = None, public: bool = True) -> None:
        try:
            state = next(state for state in type(self).STATES if state.level == level and state.face_value == building_type)
        except StopIteration:
            raise ValueError(f"{building_type} cannot be of level {level}")
        
        super().__init__(state = state, coords = coords, public = public)

class WarriorCard(Card):
    STATES: List[CardState] = [CardState(level = level, face_value = face_value, pos_in_level = WARRIOR_FACE_VALUES.index(face_value)) for level in MAIN_COLORS for face_value in WARRIOR_FACE_VALUES]
    TYPE_NAME: str = "Warriors"
    def __init__(self, coords: Tuple[int, int] = None, power: int = 0, public: bool = False) -> None:
        super().__init__(state_index = power, coords = coords, public = public)

class GuardCard(WarriorCard):
    TYPE_NAME: str = "Guards"
    def __init__(self, coords: Tuple[int, int] = None, power: int = 0, public: bool = True) -> None:
        super().__init__(power = power, coords = coords, public = public)


class CardList(Entity):
    def __init__(self, coords: Tuple[int, int], card_type: Type[Card], cards: List[Card] | None = None, selectable: bool = True, public: bool = True) -> None:
        self.card_type: Type[Card] = card_type
        self.__cards: List[Card] = cards if cards is not None else []
        super().__init__(content = self.content, coords = coords, color = colors.NONE, selectable = selectable, public = public)
    
    def __repr__(self) -> str:
        return self.label_string
    
    @property
    def content(self) -> str:
        return remove_color_codes(repr(self))
    
    @property
    def label_string(self) -> str:
        return self.card_type.TYPE_NAME + ":"
    
    def get_public_slice(self) -> 'CardList':
        public_cards: List[Card] = [card for card in self.__cards if card.public]
        return CardList(coords = self.coords, card_type = self.card_type, cards = public_cards, public = True)

    def remove(self, card: Card) -> None:
        self.__cards.remove(card)
    
    def append(self, card: Card) -> None: #TODO: use update_card_coordinates
        card.coords = Coordinates(self.coords.x + len(self.label_string) + ((len(self.__cards) + 1) * 2), self.coords.y) # index is multiplied by two, because the cards are separated by whitespaces
        self.__cards.append(card)
    
    def __setitem__(self, index: int, card: Card) -> None:
        card.coords = self.__cards[index].coords
        self.__cards[index] = card

    def update_card_coordinates(self, start: int, end: int):
        for i in range(start, end):
            self.__cards[i].coords = Coordinates(self.coords.x + len(self.label_string) + ((i + 1) * 2), self.coords.y) # index is multiplied by two, because the cards are separated by whitespaces

    def set_coords(self, new_coords) -> None:
        if self.coords != new_coords:
            super().set_coords(new_coords)
            self.update_card_coordinates(0, len(self.__cards))

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

def recvall(conn: socket.socket) -> bytes:
    data: bytes = b''
    while SOCKET_END_MSG not in data:
        try:
            more: bytes = conn.recv(1)
        except ConnectionResetError:
            raise
        data += more
    return data[:-5]

def sendall_with_end(s: socket.socket, message: bytes) -> None:
    s.sendall(message + SOCKET_END_MSG)