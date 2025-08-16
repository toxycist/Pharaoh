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

PLAYER_SIDE_HEIGHT: int = 4
# coordinates should always be in the form of (x, y)
PHARAOH_COORDINATES: Tuple[int, int] = (10, MAX_Y - 3)
GUARD_COORDINATES: List[Tuple[int, int]] = [(7, MAX_Y - 3), (13, MAX_Y - 3)]
MAIN_WARRIOR_LIST_COORDINATES: Tuple[int, int] = (23, MAX_Y - 5)
MAIN_BANDAGE_LIST_COORDINATES: Tuple[int, int] = (23, MAX_Y - 3)
MAIN_BUILDING_LIST_COORDINATES: Tuple[int, int] = (23, MAX_Y - 1)

class GameController:
    close_game: bool = False
    player_num: int = 0
    my_turn: bool = False
    my_entities: SortedList[Entity] = SortedList(key=lambda e: (e.coords.y, e.coords.x) if e.coords else (-1, -1)) # apparently fuckass SortedList uses its key even when checking for membership, so providing a value without coords just fucking crashes the program. this is why yje check for e.coords is needed
    received_entities: SortedList[Entity] = SortedList(key=lambda e: (e.coords.y, e.coords.x))
    main_warrior_list: CardList = CardList(card_type = WarriorCard, coords = MAIN_WARRIOR_LIST_COORDINATES)
    main_bandage_list: CardList = CardList(card_type = BandageCard, coords = MAIN_BANDAGE_LIST_COORDINATES)
    main_building_list: CardList = CardList(card_type = BuildingCard, coords = MAIN_BUILDING_LIST_COORDINATES)
    guard_list: List[GuardCard] = [GuardCard(coords = GUARD_COORDINATES[0]), GuardCard(coords = GUARD_COORDINATES[1])]
    cursor: Cursor = Cursor(scope = my_entities)
    footer: Entity = Entity(content = "", coords = (0, GAME_FIELD_HEIGHT))
    second_player_joined: bool = False

    controls: Dict[str, Callable] = {}

    def __new__(cls):
        raise RuntimeError(f"class {cls} is not meant to be instantiated")

    @classmethod
    def add_new_entity(cls, entity: Entity) -> None:
        cls.my_entities.add(entity)

    @classmethod
    def display_game_field(cls) -> None:
        all_entities: SortedList[Entity] = cls.my_entities + cls.received_entities
        x: int = 0
        y: int = 0
        for entity in all_entities:
            while entity.coords != (x, y):
                if entity.coords.y == y:
                    if entity.coords.x < x:
                        break
                    print(' ', end='')
                    x += 1
                else:
                    print()
                    y += 1
                    x = 0
            candidate_entities: List[Entity] = [e for e in all_entities if e.coords == entity.coords and e.display_priority >= 0]
            entity_to_display: Entity = max(candidate_entities, key = lambda e: e.display_priority, default = None)
            print(entity_to_display, end='')
            x += len(entity_to_display.content)
        print(cls.footer)
    
    @classmethod
    def refresh_screen(cls) -> None:
        system('cls')
        cls.display_game_field()

    @classmethod
    def send_public_entities(cls) -> None:
        public_entities: List[Entity] = []
        for public_entity in [e for e in cls.my_entities if e.public]:
            if isinstance(public_entity, CardList):
                public_entities.append(public_entity.get_public_slice())
            else:
                public_entities.append(public_entity)
        sendall_with_end(s, SOCKET_SHARED_ENTITIES_UPDATE)
        sendall_with_end(s, pickle.dumps(public_entities))

    @classmethod
    def receive_public_entities(cls) -> int | None:
        encoded_data: bytes = recvall(s)
        if encoded_data == SOCKET_SHARED_ENTITIES_UPDATE:
            received_entities: List[Entity] = pickle.loads(recvall(s))
            cls.received_entities.clear() # clear previously received entities
            for entity in received_entities:
                entity.coords = Coordinates(entity.coords.x, abs(entity.coords.y - MAX_Y)) # reverse y coordinate of the received entity, so it will be displayed on the other player's side
                cls.received_entities.add(entity)
            return 1
        elif encoded_data == SOCKET_YOUR_TURN:
            cls.my_turn = True
            return 0
        
    @classmethod
    def end_turn(cls) -> None:
        sendall_with_end(s, SOCKET_YOUR_TURN)
        cls.my_turn = False

##### [DIFFICULT ZONE] PROBABILITIES ##### TODO: #1
def triangular_number(n: int) -> int:
    return (n**2 + n) / 2 # factorial, but with sum

def get_triangular_sector(n: int) -> int:
    return int((math.sqrt(1 + 8 * n) - 1) // 2) + 1 # this formula returns the number m, such that argument number n is greater than or equal to the m-th triangular number

def draw_a_card(card_type: type[Entity], to_cardlist: CardList, public: bool) -> None:
    picked_card_power: int = abs(card_type.COUNT - get_triangular_sector(random.randint(1, triangular_number(card_type.COUNT)))) # reversing the triangular sector number is needed because weak cards should be more common
    to_cardlist.append(card_type(power = picked_card_power, public = True))
#####

GameController.add_new_entity(Entity(content = "╭" + "─" * (GAME_FIELD_WIDTH - 2) + "╮", coords = (MIN_X, MIN_Y)))
for y in range(1, GAME_FIELD_HEIGHT - 1):
    GameController.add_new_entity(Entity(content = "│", coords = (MIN_X, y)))
    GameController.add_new_entity(Entity(content = "│", coords = (MAX_X, y)))
GameController.add_new_entity(Entity(content = "╰" + "─" * (GAME_FIELD_WIDTH - 2) + "╯", coords = (MIN_X, MAX_Y)))

GameController.add_new_entity(GameController.footer)

GameController.footer = "Press spacebar when you are ready."
GameController.display_game_field()
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
        GameController.close_game = True
        keyboard.wait('space')
        sys.exit()
    data = recvall(s) # receive player number

    GameController.player_num = int.from_bytes(data)
    GameController.footer = f"You are player {GameController.player_num}."
    if GameController.player_num == 1:
        GameController.add_new_entity(Entity(content = "-" * (GAME_FIELD_WIDTH - 2), coords = (1, PLAYER_SIDE_HEIGHT + 2), color = colors.YELLOW))
        GameController.add_new_entity(Entity(content = "-" * (GAME_FIELD_WIDTH - 2), coords = (1, MAX_Y - (PLAYER_SIDE_HEIGHT + 2)), color = colors.BLUE))
        GameController.my_turn = True
    elif GameController.player_num == 2:
        GameController.add_new_entity(Entity(content = "-" * (GAME_FIELD_WIDTH - 2), coords = (1, PLAYER_SIDE_HEIGHT + 2), color = colors.BLUE))
        GameController.add_new_entity(Entity(content = "-" * (GAME_FIELD_WIDTH - 2), coords = (1, MAX_Y - (PLAYER_SIDE_HEIGHT + 2)), color = colors.YELLOW))
    GameController.add_new_entity(Entity(content = PHARAOH, coords = PHARAOH_COORDINATES, color = colors.WHITE, public=True))

    for guard_card in GameController.guard_list:
        GameController.add_new_entity(guard_card)

    GameController.add_new_entity(GameController.main_warrior_list)
    GameController.add_new_entity(GameController.main_bandage_list)
    GameController.add_new_entity(GameController.main_building_list)

    GameController.refresh_screen()

    GameController.send_public_entities()
    GameController.receive_public_entities()

    GameController.second_player_joined = True

    def test_function() -> None:
        if not len(GameController.main_warrior_list):
            GameController.main_warrior_list.append(WarriorCard(power = 0, public = True))
            GameController.main_bandage_list.append(BandageCard(state_index = 0, public = True))
            GameController.main_building_list.append(BuildingCard(building_type = face_values.HOSPITAL))
        else:
            GameController.main_warrior_list[0].upgrade_level()
            GameController.main_bandage_list[0].upgrade_level()
            GameController.main_building_list[0].upgrade_level()

        GameController.refresh_screen()
        GameController.send_public_entities()

        GameController.end_turn()

    GameController.controls = {
        "left": lambda: (GameController.cursor.select_previous(), GameController.refresh_screen()),
        "right": lambda: (GameController.cursor.select_next(), GameController.refresh_screen()),
        "space": test_function
    }

    while not GameController.close_game:
        if GameController.my_turn:
            GameController.cursor.show()
            GameController.refresh_screen()

            while GameController.my_turn:
                event = keyboard.read_event()
                if event.event_type == keyboard.KEY_DOWN:
                    if event.name not in GameController.controls:
                        continue
                    else:
                        GameController.controls[event.name]()
        else:
            GameController.cursor.hide()
            GameController.refresh_screen()
            while GameController.receive_public_entities():
                GameController.refresh_screen()

except (ConnectionRefusedError, TimeoutError, ConnectionResetError):
    system('cls') 
    print(("Your opponent has disconnected, unable to continue." if GameController.second_player_joined else "Server is offline, unable to connect.") + " Press spacebar to exit.")
    GameController.close_game = True
    keyboard.wait('space')
    sys.exit()