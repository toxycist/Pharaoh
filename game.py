import keyboard
import dotenv
from os import system, getenv
import random
from shared_definitions import *
import sys

dotenv.load_dotenv()
HOST = getenv('IP')
PORT = 1717

GAME_FIELD_WIDTH = 81
GAME_FIELD_HEIGHT = 21  
MIN_X = 0
MIN_Y = 0
MAX_X = GAME_FIELD_WIDTH - 1
MAX_Y = GAME_FIELD_HEIGHT - 1
PLAYER_SIDE_HEIGHT = 4
PHARAOH_COORDINATES = (10, MAX_Y - 3)
GUARD_COORDINATES = [(7, MAX_Y - 3), (13, MAX_Y - 3)]
MAIN_WARRIOR_LIST_COORDINATES = (23, MAX_Y - 5)

class deck(Enum):
    WARRIOR = auto()
    BANDAGE = auto()
    BUILDING = auto()

class PlayerManager():
    close_game = False
    player_num = 0
    my_turn = False
    my_entities = {} # the structure of my_entities is as follows: my_entities[(x, y)] = Entity object
    main_warrior_list = CardList(WarriorCard)
    received_entities = {}
    footer = ""
    second_player_joined = False

def add_new_entity(entity_string, coords):
    if isinstance(coords, list):
        for coords_pair in coords:
            PlayerManager.my_entities[coords_pair] = entity_string
    else:
        PlayerManager.my_entities[coords] = entity_string

def display_game_field():
    for y in range(0, GAME_FIELD_HEIGHT):
        x = 0
        while x < GAME_FIELD_WIDTH:
            entity = PlayerManager.my_entities.get((x, y)) or PlayerManager.received_entities.get((x, y))
            if entity:
                print(entity, end='')
                x += len(entity.content)
            else:
                print(' ', end='')
                x += 1
        print()
    print(Entity(PlayerManager.footer))

def refresh_screen():
    system('cls')
    display_game_field()

def send_public_entities():
    public_entities = {}
    for entity_with_coords in PlayerManager.my_entities.items():
        if entity_with_coords[1].public:
            if isinstance(entity_with_coords[1], CardList):
                public_entities[entity_with_coords[0]] = entity_with_coords[1].get_public_cards()
            else:
                public_entities[entity_with_coords[0]] = entity_with_coords[1]
    sendall_with_end(s, SOCKET_SHARED_ENTITIES_UPDATE)
    sendall_with_end(s, pickle.dumps(public_entities))

def receive_public_entities():
    encoded_data = recvall(s)
    if encoded_data == SOCKET_SHARED_ENTITIES_UPDATE:
        received_entities = pickle.loads(recvall(s))
        for entity_with_coords in received_entities.items():
            PlayerManager.received_entities[(entity_with_coords[0][0], abs(entity_with_coords[0][1]-MAX_Y))] = entity_with_coords[1] # reverse y coordinate and add to the received entity list
        refresh_screen()
        return 1
    elif encoded_data == SOCKET_YOUR_TURN:
        PlayerManager.my_turn = True
        return 0

def end_turn():
    sendall_with_end(s, SOCKET_YOUR_TURN)
    PlayerManager.my_turn = False

def draw_a_card(from_deck, to_cardlist, public):
    match from_deck:
        case deck.WARRIOR:
            to_cardlist.append(WarriorCard(face_values.NUM1, colors.GREEN, public))

add_new_entity(Entity("╭" + "─" * (GAME_FIELD_WIDTH - 2) + "╮"), (MIN_X, MIN_Y))
for y in range(1, GAME_FIELD_HEIGHT - 1):
    add_new_entity(Entity("│"), [(MIN_X, y), (MAX_X, y)])
add_new_entity(Entity("╰" + "─" * (GAME_FIELD_WIDTH - 2) + "╯"), (MIN_X, MAX_Y))

PlayerManager.footer = "Press spacebar when you are ready."
display_game_field()
keyboard.wait('space')
system('cls')
print("Connecting to the server...")

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.connect((HOST, PORT))
    sendall_with_end(s, SOCKET_CONNECTION_ESTABLISHED)
    data = recvall(s) # receive SOCKET_CONNECTION_ESTABLISHED or SOCKET_LOBBY_FULL
    if data == SOCKET_LOBBY_FULL:
        system('cls')
        print("The game has already started, please wait until it is finished. Press spacebar to exit.")
        PlayerManager.close_game = True
        keyboard.wait('space')
        sys.exit()
    data = recvall(s) # receive player number

    PlayerManager.player_num = int.from_bytes(data)
    PlayerManager.footer = f"You are player {PlayerManager.player_num}."
    if PlayerManager.player_num == 1:
        add_new_entity(Entity("-" * (GAME_FIELD_WIDTH - 2), colors.YELLOW), (1, PLAYER_SIDE_HEIGHT + 2))
        add_new_entity(Entity("-" * (GAME_FIELD_WIDTH - 2), colors.BLUE), (1, MAX_Y - (PLAYER_SIDE_HEIGHT + 2)))
        PlayerManager.my_turn = True
    elif PlayerManager.player_num == 2:
        add_new_entity(Entity("-" * (GAME_FIELD_WIDTH - 2), colors.YELLOW), (1, MAX_Y - (PLAYER_SIDE_HEIGHT + 2)))
        add_new_entity(Entity("-" * (GAME_FIELD_WIDTH - 2), colors.BLUE), (1, PLAYER_SIDE_HEIGHT + 2))
    add_new_entity(Entity(face_values.PHARAOH, colors.WHITE, public=True), PHARAOH_COORDINATES)
    add_new_entity(GuardCard(), GUARD_COORDINATES[0])
    add_new_entity(GuardCard(), GUARD_COORDINATES[1])

    add_new_entity(PlayerManager.main_warrior_list, MAIN_WARRIOR_LIST_COORDINATES)

    refresh_screen()

    send_public_entities()
    receive_public_entities()

    PlayerManager.second_player_joined = True

    while not PlayerManager.close_game:
        if PlayerManager.my_turn:
            keyboard.wait('space')

            draw_a_card(from_deck = deck.WARRIOR, to_cardlist = PlayerManager.main_warrior_list, public = True)

            refresh_screen()
            send_public_entities()
            end_turn()
        else:
            while receive_public_entities():
                pass
except (ConnectionRefusedError, TimeoutError, ConnectionResetError):
    system('cls') 
    print(("Your opponent has disconnected, unable to continue." if PlayerManager.second_player_joined else "Server is offline, unable to connect.") + " Press spacebar to exit.")
    PlayerManager.close_game = True
    keyboard.wait('space')
    sys.exit()