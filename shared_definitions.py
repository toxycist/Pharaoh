import pickle
import socket
import threading
import re
from enum import Enum, auto
from typing import Dict, Tuple, List, Type, Any, overload
from collections import namedtuple

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
CURSOR: str = "▲"

MAIN_COLORS: List[str] = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]
SUPER_COLORS: List[str] = [colors.RAINBOW]
WARRIOR_FACE_VALUES: List[str] = [face_values.NUM1, face_values.NUM2, face_values.NUM3, 
                                  face_values.NUM4, face_values.NUM5, face_values.NUM6, 
                                  face_values.NUM7, face_values.NUM8, face_values.NUM9, face_values.PLUS_2]
BANDAGE_FACE_VALUES: List[str] = [face_values.FACE_VALUE_BANDAGE, face_values.LEVEL_BANDAGE, face_values.COMBINED_BANDAGE]
BUILDING_FACE_VALUES: List[str] = [face_values.HOSPITAL, face_values.BARRACKS]
SUPER_BUILDING_FACE_VALUES: List[str] = [(SUPER_BUILDING_PREFIX + face_value) for face_value in BUILDING_FACE_VALUES]

Coordinates = namedtuple("Coordinates", ["x", "y"])

class Entity:
    def __init__(self, content: str, color: str = colors.GRAY, display_priority: int = 0, coords: Tuple[int, int] = None, public: bool = False) -> None:
        if not hasattr(self, 'content'):
            self.content: str = content
        if not hasattr(self, 'color'):
            self.color: str = color
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
    
    def switch_public(self) -> None:
        self.public = not self.public
    
    def set_display_priority(self, to: int) -> None:
        self.display_priority = to

# class Cursor(Entity):
#     def __init__(self) -> None:
#         self.selection_scope: Dict[Tuple[int, int], Entity] = []
#         super().__init__(content=CURSOR, color=colors.WHITE, display_priority=-1, public=False)

#     def show(self) -> None:
#         self.set_display_priority(1)
    
#     def hide(self) -> None:
#         self.set_display_priority(-1)

class CardState():
    def __init__(self, level: str, face_value: str, pos_in_level: int) -> None:
        self.level = level
        self.face_value = face_value
        self.pos_in_level = pos_in_level
    
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
    def __init__(self, state_index: int, coords: Tuple[int, int] = None, public: bool = False) -> None: ... # if card coordinates are None, it should be a part of a CardList
    
    @overload
    def __init__(self, state: CardState, coords: Tuple[int, int] = None, public: bool = False) -> None: ... # if card coordinates are None, it should be a part of a CardList

    def __init__( # provide either state or state index, but not both
        self, 
        state: CardState = None, 
        state_index: int = None, 
        coords: Tuple[int, int] = None, 
        public: bool = False
    ) -> None:
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

def remove_color_codes(s: str) -> str:
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', s)

class CardList(Entity):
    def __init__(self, coords: Tuple[int, int], card_type: Type[Card], cards: List[Card] | None = None, public: bool = True) -> None:
        self.card_type: Type[Card] = card_type
        self.__cards: List[Card] = cards if cards is not None else []
        super().__init__(content = self.content, coords = coords, color = colors.NONE, public = public)
    
    def __repr__(self) -> str:
        string_repr: str = self.card_type.TYPE_NAME + ":"
        if self.__cards:
            for card in self.__cards:
                string_repr += " " + repr(card)
        else:
            string_repr += " ***"
        return string_repr
    
    @property
    def content(self) -> str:
        return remove_color_codes(repr(self))
    
    def get_public_slice(self) -> 'CardList':
        public_cards: List[Card] = [public_card for public_card in self.__cards if public_card.public]
        return CardList(coords = self.coords, card_type = self.card_type, cards = public_cards, public = True)
    
    def remove(self, card: Card) -> None:
        self.__cards.remove(card)
    
    def append(self, card: Card) -> None:
        self.__cards.append(card)
    
    def __setitem__(self, index: int, card: Card) -> None:
        self.__cards[index] = card

    def __getitem__(self, index: int) -> Card:
        return self.__cards[index]
    
    def __bool__(self) -> bool:
        return self is not None
    
    def __len__(self) -> int:
        return len(self.__cards)
    
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