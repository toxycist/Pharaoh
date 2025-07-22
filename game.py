import keyboard
import dotenv
from os import system, getenv
import random
from shared_definitions import *
import sys
import math

dotenv.load_dotenv()
HOST: str | None = getenv('IP')
PORT: int = 1717

GAME_FIELD_WIDTH: int = 81
GAME_FIELD_HEIGHT: int = 21  
MIN_X: int = 0
MIN_Y: int = 0
MAX_X: int = GAME_FIELD_WIDTH - 1
MAX_Y: int = GAME_FIELD_HEIGHT - 1
PLAYER_SIDE_HEIGHT: int = 4
PHARAOH_COORDINATES: Tuple[int, int] = (10, MAX_Y - 3)
GUARD_COORDINATES: List[Tuple[int, int]] = [(7, MAX_Y - 3), (13, MAX_Y - 3)]
MAIN_WARRIOR_LIST_COORDINATES: Tuple[int, int] = (23, MAX_Y - 5)
MAIN_BANDAGE_LIST_COORDINATES: Tuple[int, int] = (23, MAX_Y - 3)

class PlayerManager:
    close_game: bool = False
    player_num: int = 0
    my_turn: bool = False
    my_entities: Dict[Tuple[int, int], Entity] = {} # (x, y) is used as a key
    main_warrior_list: CardList = CardList(WarriorCard)
    main_bandage_list: CardList = CardList(BandageCard)
    received_entities: Dict[Tuple[int, int], Entity] = {}
    footer: str = ""
    second_player_joined: bool = False

def add_new_entity(entity: Entity, coords: Tuple[int, int] | List[Tuple[int, int]]) -> None:
    if isinstance(coords, list):
        for coords_pair in coords:
            PlayerManager.my_entities[coords_pair] = entity
    else:
        PlayerManager.my_entities[coords] = entity

def display_game_field() -> None:
    for y in range(0, GAME_FIELD_HEIGHT):
        x = 0
        while x < GAME_FIELD_WIDTH:
            entity: Entity | None = PlayerManager.my_entities.get((x, y)) or PlayerManager.received_entities.get((x, y))
            if entity:
                print(entity, end='')
                x += len(entity.content)
            else:
                print(' ', end='')
                x += 1
        print()
    print(Entity(PlayerManager.footer))

def refresh_screen() -> None:
    system('cls')
    display_game_field()

def send_public_entities() -> None:
    public_entities: Dict[Tuple[int, int], Entity] = {}
    for entity_with_coords in PlayerManager.my_entities.items():
        if entity_with_coords[1].public:
            if isinstance(entity_with_coords[1], CardList):
                public_entities[entity_with_coords[0]] = entity_with_coords[1].get_public_cards()
            else:
                public_entities[entity_with_coords[0]] = entity_with_coords[1]
    sendall_with_end(s, SOCKET_SHARED_ENTITIES_UPDATE)
    sendall_with_end(s, pickle.dumps(public_entities))

def receive_public_entities() -> int | None:
    encoded_data: bytes = recvall(s)
    if encoded_data == SOCKET_SHARED_ENTITIES_UPDATE:
        received_entities: Dict[Tuple[int, int], Entity] = pickle.loads(recvall(s))
        for entity_with_coords in received_entities.items():
            PlayerManager.received_entities[(entity_with_coords[0][0], abs(entity_with_coords[0][1]-MAX_Y))] = entity_with_coords[1] # reverse y coordinate and add to the received entity list
        refresh_screen()
        return 1
    elif encoded_data == SOCKET_YOUR_TURN:
        PlayerManager.my_turn = True
        return 0

def end_turn() -> None:
    sendall_with_end(s, SOCKET_YOUR_TURN)
    PlayerManager.my_turn = False

##### [DIFFICULT ZONE] PROBABILITIES
def triangular_number(n: int) -> int:
    return (n**2 + n) / 2 # factorial, but with sum

def get_triangular_sector(n: int) -> int:
    return int((math.sqrt(1 + 8 * n) - 1) // 2) + 1 # this formula returns the number m, such that argument number n is greater than or equal to the m-th triangular number

face_value = level = combined = 0

def draw_a_card(card_type: type[Entity], to_cardlist: CardList, public: bool) -> None:
    picked_card_power: int = abs(card_type.COUNT - get_triangular_sector(random.randint(1, triangular_number(card_type.COUNT)))) # reversing the triangular sector number is needed because weak cards should be more common
    to_cardlist.append(card_type(power = picked_card_power, public = True))

    global face_value, level, combined
    match picked_card_power:
        case 0:
            face_value += 1
        case 1:
            level += 1
        case 2:
            combined += 1
#####

add_new_entity(Entity("╭" + "─" * (GAME_FIELD_WIDTH - 2) + "╮"), (MIN_X, MIN_Y))
for y in range(1, GAME_FIELD_HEIGHT - 1):
    add_new_entity(Entity("│"), [(MIN_X, y), (MAX_X, y)])
add_new_entity(Entity("╰" + "─" * (GAME_FIELD_WIDTH - 2) + "╯"), (MIN_X, MAX_Y))

PlayerManager.footer = "Press spacebar when you are ready."
display_game_field()
keyboard.wait('space')
system('cls')
print("Connecting to the server...")

s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.connect((HOST, PORT))
    sendall_with_end(s, SOCKET_CONNECTION_ESTABLISHED)
    data: bytes = recvall(s) # receive SOCKET_CONNECTION_ESTABLISHED or SOCKET_LOBBY_FULL
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
    add_new_entity(Entity(PHARAOH, colors.WHITE, public=True), PHARAOH_COORDINATES)
    add_new_entity(GuardCard(), GUARD_COORDINATES[0])
    add_new_entity(GuardCard(), GUARD_COORDINATES[1])

    add_new_entity(PlayerManager.main_warrior_list, MAIN_WARRIOR_LIST_COORDINATES)
    add_new_entity(PlayerManager.main_bandage_list, MAIN_BANDAGE_LIST_COORDINATES)

    refresh_screen()

    send_public_entities()
    receive_public_entities()

    PlayerManager.second_player_joined = True

    while not PlayerManager.close_game:
        if PlayerManager.my_turn:
            
            ### TEST
            keyboard.wait('space')
            for i in range(0, 100):
                if i % 2 == 0:
                    draw_a_card(card_type = WarriorCard, to_cardlist = PlayerManager.main_warrior_list, public = True)
                else:
                    draw_a_card(card_type = BandageCard, to_cardlist = PlayerManager.main_bandage_list, public = True)
                refresh_screen()
            ###

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