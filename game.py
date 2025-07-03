import keyboard

GAME_FIELD_WIDTH = 81
GAME_FIELD_HEIGHT = 21  
MIN_X = 0
MIN_Y = 0
MAX_X = GAME_FIELD_WIDTH - 1
MAX_Y = GAME_FIELD_HEIGHT - 1
footer = ""

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

class ColoredString:
    def __init__(self, string, color=colors.GRAY):
        self.string = string
        self.color = color
    def __repr__(self):
        return_str = ''
        if self.color == colors.RAINBOW:
            for i in range(0, len(self.string)):
                return_str += (main_colors[i%4] + self.string[i] + colors.ENDC)
        else:
            return_str = self.color + self.string + colors.ENDC

        return return_str

class Card(ColoredString):
    pass

entities = {}

def add_new_entity(entity_string, coords):
    entities[coords] = entity_string

def display_game_field():
    for y in range(0, GAME_FIELD_HEIGHT):
        x = 0
        while x < GAME_FIELD_WIDTH:
            if (x, y) in entities:
                print(entities[(x, y)], end='')
                x += len(entities[(x,y)].string)
            else:
                print(' ', end='')
                x += 1
        print()
    print(ColoredString(footer))

add_new_entity(ColoredString("╭" + "─" * (GAME_FIELD_WIDTH - 2) + "╮"), (MIN_X, MIN_Y))
for i in range(1, GAME_FIELD_HEIGHT - 1):
    add_new_entity(ColoredString("│"), (MIN_X, i))
    add_new_entity(ColoredString("│"), (MAX_X, i))
add_new_entity(ColoredString("╰" + "─" * (GAME_FIELD_WIDTH - 2) + "╯"), (MIN_X, MAX_Y))

footer = "Press spacebar when you are ready."
display_game_field()
print("Zoom in until you no longer see this message.")
keyboard.wait('space')