import pickle
import socket
import threading
import re
from enum import Enum, auto
from typing import Dict, Tuple, List, Type, Any

class colors:
    NONE: None = None
    GRAY: str = '\033[90m'
    WHITE: str = '\033[37m'
    RAINBOW: str = ''
    GREEN: str = '\033[92m'
    BLUE: str = '\033[94m'
    YELLOW: str = '\033[93m'
    RED: str = '\033[91m'
    ENDC: str = '\033[0m'

class face_values:
    HOSPITAL: str = "HOS☩"
    SUPER_BARRACKS: str = "SUPⵌ"
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

main_colors: List[str] = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]
numerical_face_values: List[str] = [
    face_values.NUM1, face_values.NUM2, face_values.NUM3, face_values.NUM4,
    face_values.NUM5, face_values.NUM6, face_values.NUM7, face_values.NUM8,
    face_values.NUM9, face_values.PLUS_2
]

WARRIOR_CARDS_COUNT: int = len(numerical_face_values) * len(main_colors)
MAX_WARRIOR_CARD_POWER: int = WARRIOR_CARDS_COUNT - 1

class Entity:
    def __init__(self, content: str, color: str = colors.GRAY, public: bool = False) -> None:
        if not hasattr(self, 'content'):
            self.content: str = content
        if not hasattr(self, 'color'):
            self.color: str = color
        self.public: bool = public

    def __repr__(self) -> str:
        return_str: str = ''
        if self.color == colors.RAINBOW:
            for i in range(0, len(self.content)):
                return_str += (main_colors[i%4] + self.content[i] + colors.ENDC)
        elif self.color == colors.NONE:
            return_str = self.content
        else:
            return_str = self.color + self.content + colors.ENDC

        return return_str
    
    def switch_public(self) -> None:
        self.public = not self.public

class WarriorCard(Entity):
    type_name: str = "Warriors"
    __id_counter: int = 0
    def __init__(self, power: int, public: bool = False) -> None:
        self.power: int = power
        super(WarriorCard, self).__init__(self.content, self.color, public)
        self.id: int = type(self).__id_counter
        type(self).__id_counter += 1
    
    @property
    def color(self) -> str:
        return main_colors[self.power // len(numerical_face_values)]
    
    @property
    def content(self) -> str:
        return numerical_face_values[self.power % len(numerical_face_values)]
    
    def upgrade_level(self, by: int = 1) -> None:
        if self.power <= MAX_WARRIOR_CARD_POWER:
            self.power += by * len(numerical_face_values)

    def upgrade_value(self, by: int = 1) -> None:
        if self.power <= MAX_WARRIOR_CARD_POWER:
            self.power += by

class GuardCard(WarriorCard):
    type_name: str = "Guards"
    __id_counter: int = 0
    def __init__(self, power: int = 0, public: bool = True) -> None:
        super(GuardCard, self).__init__(power, public)

def remove_color_codes(s: str) -> str:
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', s)

class CardList(Entity):
    def __init__(self, card_type: Type[Entity], cards: List[Entity] | None = None, public: bool = True) -> None:
        self.card_type: Type[Entity] = card_type
        self.__cards: List[Entity] = cards if cards is not None else []
        super(CardList, self).__init__(self.content, colors.NONE, public)
    
    def __repr__(self) -> str:
        string_repr: str = self.card_type.type_name + ":"
        if self.__cards:
            for card in self.__cards:
                string_repr += " " + repr(card)
        else:
            string_repr += " ***"
        return string_repr
    
    @property
    def content(self) -> str:
        return remove_color_codes(repr(self))
    
    def get_public_cards(self) -> 'CardList':
        public_cards: List[Entity] = [public_card for public_card in self.__cards if public_card.public]
        return CardList(self.card_type, public_cards, public = True)
    
    def remove(self, card: Entity) -> None:
        self.__cards.remove(card)
    
    def append(self, card: Entity) -> None:
        self.__cards.append(card)
    
    def __setitem__(self, index: int, card: Entity) -> None:
        self.__cards[index] = card

    def __getitem__(self, index: int) -> Entity:
        return self.__cards[index]
    
    def __bool__(self) -> bool:
        return self is not None
    
    def __len__(self) -> int:
        return len(self.__cards)
    
    def __contains__(self, card: Entity) -> bool:
        if not isinstance(card, self.card_type):
            return False
        return any(c.power == card.power for c in self.__cards)

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