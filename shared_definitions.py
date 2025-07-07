import pickle
import socket
import threading

class colors:
    GRAY = '\033[90m'
    WHITE = '\033[37m'
    RAINBOW = ''
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

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
numerical_face_values = [NUM1, NUM2, NUM3, NUM4, NUM5, NUM6, NUM7, NUM8, NUM9, PLUS_2]
MAX_WARRIOR_CARD_POWER = len(main_colors) * len(numerical_face_values) - 1

class Entity:
    def __init__(self, content, color = colors.GRAY, public = False):
        self.content = content
        self.color = color
        self.public = public
    def __repr__(self):
        return_str = ''
        if self.color == colors.RAINBOW:
            for i in range(0, len(self.content)):
                return_str += (main_colors[i%4] + self.content[i] + colors.ENDC)
        else:
            return_str = self.color + self.content + colors.ENDC

        return return_str

class WarriorCard(Entity):
    def __init__(self, face_value, level, public = False):
        super(WarriorCard, self).__init__(face_value, level, public)
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