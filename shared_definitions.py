import pickle
import socket
import threading
import re
from enum import Enum, auto

class colors:
    NONE = None
    GRAY = '\033[90m'
    WHITE = '\033[37m'
    RAINBOW = ''
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

class face_values:
    PHARAOH = "↰"
    HOSPITAL = "HOS☩"
    SUPER_BARRACKS = "SUPⵌ"
    BARRACKS = "ⵌ"
    LEVEL_BANDAGE = "☛"
    FACE_VALUE_BANDAGE = "+"
    COMBINED_BANDAGE = "⇄"
    PLUS_2 = "+2"
    NUM1 = "1"
    NUM2 = "2"
    NUM3 = "3"
    NUM4 = "4"
    NUM5 = "5"
    NUM6 = "6"
    NUM7 = "7"
    NUM8 = "8"
    NUM9 = "9"

main_colors = [colors.GREEN, colors.BLUE, colors.YELLOW, colors.RED]
numerical_face_values = [face_values.NUM1, face_values.NUM2, face_values.NUM3, face_values.NUM4, face_values.NUM5, face_values.NUM6, face_values.NUM7, face_values.NUM8, face_values.NUM9, face_values.PLUS_2]
MAX_WARRIOR_CARD_POWER = len(main_colors) * len(numerical_face_values) - 1

class Entity:
    def __init__(self, content, color = colors.GRAY, public = False):
        if not hasattr(self, 'content'): # this is needed because in subclasses there may be a content property which is not settable. because of that an error may occur during super().__init__()
            self.content = content
        self.color = color
        self.public = public
    def __repr__(self):
        return_str = ''
        if self.color == colors.RAINBOW:
            for i in range(0, len(self.content)):
                return_str += (main_colors[i%4] + self.content[i] + colors.ENDC)
        elif self.color == colors.NONE:
            return_str = self.content
        else:
            return_str = self.color + self.content + colors.ENDC

        return return_str
    
    def switch_public(self):
        self.public = not self.public

class WarriorCard(Entity):
    type_name = "Warriors"
    __id_counter = 0
    def __init__(self, face_value, level, public = False):
        super(WarriorCard, self).__init__(face_value, level, public)
        self.id = type(self).__id_counter
        type(self).__id_counter += 1
        if face_value in numerical_face_values:
            self.power = (main_colors.index(self.color) * len(numerical_face_values)) + numerical_face_values.index(self.content)

    def __refresh_string_and_color(self):
        try:
            self.color = main_colors[self.power // len(numerical_face_values)]
            self.content = numerical_face_values[self.power % len(numerical_face_values)]
            return 1
        except IndexError:
            self.power = MAX_WARRIOR_CARD_POWER
            return 0
    
    def upgrade_level(self, by=1):
        self.power += by * len(numerical_face_values)
        return self.__refresh_string_and_color()

    def upgrade_value(self, by=1):
        self.power += by
        return self.__refresh_string_and_color()

class GuardCard(WarriorCard):
    type_name = "Guards"
    __id_counter = 0
    def __init__(self, face_value = face_values.NUM1, level = colors.GREEN, public = True):
        super(GuardCard, self).__init__(face_value, level, public)

def remove_color_codes(str):
    return re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]').sub('', str)

class CardList(Entity):
    def __init__(self, card_type, cards=None, public=True):
        self.card_type = card_type
        self.__cards = cards if cards is not None else []
        super(CardList, self).__init__(self.content, colors.NONE, public)
    
    def __repr__(self):
        string_repr = self.card_type.type_name + ":"
        if self.__cards:
            for card in self.__cards:
                string_repr += " " + repr(card)
        else:
            string_repr += " ***"
            
        return string_repr
    
    @property
    def content(self):
        return remove_color_codes(repr(self))
    
    def get_public_cards(self):
        public_cards = [public_card for public_card in self.__cards if public_card.public]
        return CardList(self.card_type, public_cards, public = True)
    
    def remove(self, card):
        self.__cards.remove(card)
        self.content = repr(self)
    
    def append(self, card):
        self.__cards.append(card)
    
    def __setitem__(self, index, card):
        self.__cards[index] = card

    def __getitem__(self, index):
        return self.__cards[index]
    
    def __len__(self):
        return len(self.content)

SOCKET_END_MSG = b"<END>"
SOCKET_CONNECTION_ESTABLISHED = b"CONNECTION ESTABLISHED"
SOCKET_LOBBY_FULL = b"LOBBY FULL"
SOCKET_SHARED_ENTITIES_UPDATE = b"SHARED ENTITIES UPDATE"
SOCKET_YOUR_TURN = b"YOUR TURN"

def recvall(conn):
    data = b''
    while SOCKET_END_MSG not in data:
        try:
            more = conn.recv(1)
        except ConnectionResetError:
            raise
        data += more
    return data[:-5]

def sendall_with_end(s, message):
    s.sendall(message + SOCKET_END_MSG)