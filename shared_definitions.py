import pickle
import socket
import threading
import re
from enum import Enum, auto
from typing import Dict, Tuple, List, Type, Any
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

LEVEL_COLORS: List[str] = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]

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
                return_str += (LEVEL_COLORS[i%4] + self.content[i] + colors.ENDC)
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
    
class Card(Entity):
    FACE_VALUES: List[str] = [] # MANDATORY OVERRIDE
    POSSIBLE_COLORS: List[str] = LEVEL_COLORS
    TYPE_NAME: str = "Cards"

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.COUNT = len(cls.FACE_VALUES) * len(cls.POSSIBLE_COLORS)
        cls.MAX_POWER = cls.COUNT - 1

    def __init__(self, power: int, coords: Tuple[int, int] = None, public: bool = False) -> None: # if card coordinates are None it should be a part of a CardList
        self.power: int = power
        super().__init__(content = self.content, coords = coords, color = self.color, public = public)
    
    @property
    def color(self) -> str:
        return type(self).POSSIBLE_COLORS[self.power // len(type(self).FACE_VALUES)]
    
    @property
    def content(self) -> str:
        return type(self).FACE_VALUES[self.power % len(type(self).FACE_VALUES)]
    
    def __eq__(self, other: 'Card'):
        return type(self) == type(other) and self.power == other.power

    def __hash__(self):
        return hash((type(self), self.power))
    
    def upgrade_level(self, by: int = 1) -> 'Card':
        self.power = min(self.power + by * len(type(self).FACE_VALUES), type(self).MAX_POWER)
        return self

    def upgrade_value(self, by: int = 1) -> 'Card':
        self.power = min(self.power + by, type(self).MAX_POWER)

#TODO: #2

class BandageCard(Card):
    FACE_VALUES: List[str] = [face_values.FACE_VALUE_BANDAGE, face_values.LEVEL_BANDAGE, face_values.COMBINED_BANDAGE]
    TYPE_NAME: str = "Bandages"

class BuildingCard(Card):
    FACE_VALUES: List[str] = [face_values.HOSPITAL, face_values.BARRACKS]
    POSSIBLE_COLORS: List[str] = LEVEL_COLORS
    TYPE_NAME: str = "Buildings"

    def __init__(self, building_type: str, level: str = colors.GREEN, coords: Tuple[int, int] = None, public: bool = True) -> None:
        if building_type not in type(self).FACE_VALUES:
            raise ValueError(f"Invalid face_value: {building_type!r}. Must be one of {type(self).FACE_VALUES}")
        if level not in type(self).POSSIBLE_COLORS:
            raise ValueError(f"Invalid level: {level!r}. Must be one of {type(self).POSSIBLE_COLORS}")
        
        face_value_index: int = type(self).FACE_VALUES.index(building_type)
        face_values_count: int = len(type(self).FACE_VALUES)
        level_index: int = type(self).POSSIBLE_COLORS.index(level)
        super().__init__(power = level_index * face_values_count + face_value_index, coords = coords, public = public)
    
    def upgrade_level(self, by: int = 1) -> 'BuildingCard': # the return value of this method should always be reassigned: building_card = building_card.upgrade_level()
        max_level = len(type(self).POSSIBLE_COLORS) - 1
        current_level = type(self).POSSIBLE_COLORS.index(self.color)

        if current_level == max_level:
            return SuperBuildingCard(building_type = self.content, public = self.public)
        
        super().upgrade_level(by)
        return self

class SuperBuildingCard(BuildingCard): #FIXME: #3
    FACE_VALUES: List[str] = [SUPER_BUILDING_PREFIX + face_values.HOSPITAL, SUPER_BUILDING_PREFIX + face_values.BARRACKS]
    POSSIBLE_COLORS: List[str] = [colors.RAINBOW]

    def upgrade_level(self) -> False:
        return False

    def __init__(self, building_type: str, coords: Tuple[int, int] = None, public: bool = True) -> None:
        Card.__init__(self, coords = coords, power = type(self).FACE_VALUES.index(SUPER_BUILDING_PREFIX + building_type), public = public)

class WarriorCard(Card):
    FACE_VALUES: List[str] = [
        face_values.NUM1, face_values.NUM2, face_values.NUM3, face_values.NUM4,
        face_values.NUM5, face_values.NUM6, face_values.NUM7, face_values.NUM8,
        face_values.NUM9, face_values.PLUS_2
    ]
    TYPE_NAME: str = "Warriors"

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
        return any(c.power == card.power and type(c) == type(card) for c in self.__cards)

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