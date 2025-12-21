import dotenv
from os import system, getenv, name as _os_name
import random
from shared_definitions import *
import sys
import math

if _os_name == "nt":
    import msvcrt
    def getch() -> str:
        return msvcrt.getch().decode("latin-1")
else:
    import tty
    import termios
    def getch() -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    
class escape_sequences:
    if _os_name == "nt":
        ESCAPE_SEQUENCE_LENGTH = 2

        ESCAPE = "\xe0"
        ARROW_UP = "\xe0H"
        ARROW_DOWN = "\xe0P"
        ARROW_LEFT = "\xe0K"
        ARROW_RIGHT = "\xe0M"
        CTRL_C = "\x03"
    else:
        ESCAPE_SEQUENCE_LENGTH = 3

        ESCAPE = "\x1b"
        ARROW_UP = "\x1b[A"
        ARROW_DOWN = "\x1b[B"
        ARROW_LEFT = "\x1b[D"
        ARROW_RIGHT = "\x1b[C"
        CTRL_C = "\x03"

def clear_screen() -> None:
    system('cls' if _os_name == 'nt' else 'clear')

def close_game_on_space() -> None:
    while ' ' != getch(): pass
    GameController.close_game = True
    sys.exit()

dotenv.load_dotenv()
HOST: str | None = getenv('IP')
PORT: int = 1717

PLAYER_SIDE_HEIGHT: int = 4
# coordinates should always be in the form of (x, y)
PHARAOH_COORDINATES = Coordinates(MIN_X + 10, MAX_Y - 3)
GUARD_COORDINATES_LIST: List[Coordinates] = [Coordinates(MIN_X + 7, MAX_Y - 3), Coordinates(MIN_X + 13, MAX_Y - 3)]
MAIN_WARRIOR_LIST_COORDINATES = Coordinates(MIN_X + 23, MAX_Y - 5)
MAIN_BANDAGE_LIST_COORDINATES = Coordinates(MIN_X + 23, MAX_Y - 3)
MAIN_BUILDING_LIST_COORDINATES = Coordinates(MIN_X + 23, MAX_Y - 1)
FOOTER_START_COORDINATES = Coordinates(MIN_X, MAX_Y + 1)

class GameController:
    close_game: bool = False
    player_num: int = 0
    player_color: str = colors.NONE
    my_turn: bool = False
    my_entities: SortedList[Entity] = SortedList(key = lambda e: (e.coords.y, e.coords.x) if e.coords else (-1, -1)) # apparently fuckass SortedList uses its key even when checking for membership, so providing a value without coords just fucking crashes the program. this is why the check for e.coords is needed
    received_entities: SortedList[Entity] = SortedList(key = lambda e: (e.coords.y, e.coords.x))
    main_warrior_list: CardList = CardList(card_type = WarriorCard, coords = MAIN_WARRIOR_LIST_COORDINATES)
    main_bandage_list: CardList = CardList(card_type = BandageCard, coords = MAIN_BANDAGE_LIST_COORDINATES)
    main_building_list: CardList = CardList(card_type = BuildingCard, coords = MAIN_BUILDING_LIST_COORDINATES)
    cursor = None | Cursor # cursor is set outside of class body, because it needs a callback to a class method get_shift_to_free_space
    guard_list: List[GuardCard] = [GuardCard(coords = GUARD_COORDINATES_LIST[0]), GuardCard(coords = GUARD_COORDINATES_LIST[1])]
    footer: SortedList[Entity] = SortedList(key = lambda e: (e.coords.y, e.coords.x))
    second_player_joined: bool = False

    controls: Dict[str, Callable] = {}

    def __new__(cls):
        raise RuntimeError(f"class {cls} is not meant to be instantiated")

    @classproperty
    def all_entities(cls) -> SortedList[Entity]:
        return SortedList(cls.my_entities + cls.received_entities + cls.footer, key = lambda e: (e.coords.y, e.coords.x))

    @classmethod
    def display_entity(cls, entity_to_display: Entity, start_x: int, start_y: int) -> Tuple[int, int]:
        x = start_x
        y = start_y
        while entity_to_display.coords != (x, y):
            if entity_to_display.coords.y == y:
                if entity_to_display.coords.x < x:
                    break
                print(' ', end='')
                x += 1
            else:
                print()
                y += 1
                x = 0
        print(entity_to_display, end='')
        x += len(entity_to_display.content)
        return (x, y)

    @classmethod
    def display_game_field(cls) -> None:
        x: int = 0
        y: int = 0
        for entity in cls.all_entities:
            x, y = cls.display_entity(entity_to_display = entity, start_x = x, start_y = y)
            if isinstance(entity, Iterable): # TODO: does not work with new cursor logic, the cursor is drawn only after all other elements of the cardlist
                for e in entity:
                    x, y = cls.display_entity(entity_to_display = e, start_x = x, start_y = y)
        print("") # flush the buffer while also moving the cursor to the next line(to avoid distracting players)

    @classmethod
    def set_footer(cls, entity: Entity | List[Entity]) -> None:
        cls.footer.clear()
        if isinstance(entity, Iterable):
            cls.footer.update(entity)
        else:
            cls.footer.add(entity)
    
    @classmethod
    def get_shift_to_free_space(cls, entity: Entity) -> Tuple[int, int]:
        shifts = (
            (-1, 0),
            (len(entity.content), 0),
            (0, 1),
            (0, -1)
        )

        for shift_x, shift_y in shifts:
            dummy_entity = Entity("", coords = Coordinates(entity.coords.x + shift_x, entity.coords.y + shift_y))
            index_of_the_shift = cls.all_entities.bisect_right(dummy_entity)
            closest_left: Entity = cls.all_entities[index_of_the_shift - 1] if index_of_the_shift > 0 else None
            if closest_left.coords.x + len(closest_left.content) <= (entity.coords.x + shift_x):
                return (shift_x, shift_y)
            
        return None

    @classmethod
    def refresh_screen(cls) -> None:
        clear_screen()
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
                entity.set_coords(Coordinates(entity.coords.x, MIN_Y + abs(entity.coords.y - MAX_Y))) # reverse y coordinate of the received entity, so it will be displayed on the other player's side
                cls.received_entities.add(entity)
            return True
        elif encoded_data == SOCKET_YOUR_TURN:
            cls.my_turn = True
            return False
        
    @classmethod
    def end_turn(cls) -> None:
        sendall_with_end(s, SOCKET_YOUR_TURN)
        cls.my_turn = False

GameController.cursor = Cursor(GameController.get_shift_to_free_space, scope = GameController.my_entities)

##### [DIFFICULT ZONE] PROBABILITIES ##### TODO: #1
def triangular_number(n: int) -> int:
    return (n**2 + n) / 2 # factorial, but with sum

def get_triangular_sector(n: int) -> int:
    return int((math.sqrt(1 + 8 * n) - 1) // 2) + 1 # this formula returns the number m, such that argument number n is greater than or equal to the m-th triangular number

def draw_a_card(card_type: type[Entity], to_cardlist: CardList, public: bool) -> None:
    picked_card_power: int = abs(card_type.COUNT - get_triangular_sector(random.randint(1, triangular_number(card_type.COUNT)))) # reversing the triangular sector number is needed because weak cards should be more common
    to_cardlist.append(card_type(power = picked_card_power, public = True))
#####

class ActionEntry(Entity):
    def __init__(self, content: str, action: Callable, coords: Coordinates, color = colors.NONE, selectable = True, public = False):
        super().__init__(content, color, coords, selectable, public)
        self.action = action

def create_action_menu(entity: Entity) -> List[Entity]: # warning: the returned list is not sorted
    menu: List[Entity] = []

    if isinstance(entity, BandageCard) and entity.content == face_values.FACE_VALUE_BANDAGE:
        menu.append(ActionEntry("Upgrade the value of a certain card", 
                                coords = (FOOTER_START_COORDINATES.x + 2, FOOTER_START_COORDINATES.y + 1 + len(menu)),
                                action = lambda: (
                                    GameController.cursor.selected.upgrade_level(), 
                                    GameController.refresh_screen(), 
                                    GameController.send_public_entities(), 
                                    GameController.end_turn())))
        menu.append(ActionEntry("Upgrade the value of a certain card", 
                                coords = (FOOTER_START_COORDINATES.x + 2, FOOTER_START_COORDINATES.y + 1 + len(menu)),
                                action = lambda: (
                                    GameController.cursor.selected.upgrade_level(), 
                                    GameController.refresh_screen(), 
                                    GameController.send_public_entities(), 
                                    GameController.end_turn())))
        menu.append(ActionEntry("Upgrade the value of a certain card", 
                                coords = (FOOTER_START_COORDINATES.x + 2, FOOTER_START_COORDINATES.y + 1 + len(menu)),
                                action = lambda: (
                                    GameController.cursor.selected.upgrade_level(), 
                                    GameController.refresh_screen(), 
                                    GameController.send_public_entities(), 
                                    GameController.end_turn())))
    else:
        return [Entity("No action can be performed by this entity.", colors.NONE, coords = FOOTER_START_COORDINATES)]
    
    number_of_entries = len(menu)

    menu += [Entity(content = UPPER_FIELD_BORDER, color = GameController.player_color, coords = FOOTER_START_COORDINATES), 
             Entity(content = LOWER_FIELD_BORDER, color = GameController.player_color, coords = (FOOTER_START_COORDINATES.x, FOOTER_START_COORDINATES.y + 1 + number_of_entries))]
    
    for y in range(number_of_entries):
        menu += [Entity(content = LATERAL_FIELD_BORDER_CHARACTER, color = GameController.player_color, coords = (FOOTER_START_COORDINATES.x, FOOTER_START_COORDINATES.y + y + 1)),
                 Entity(content = LATERAL_FIELD_BORDER_CHARACTER, color = GameController.player_color, coords = (FOOTER_START_COORDINATES.x + (GAME_FIELD_WIDTH - 1), FOOTER_START_COORDINATES.y + y + 1))]

    return menu

GameController.my_entities.update([Entity(content = UPPER_FIELD_BORDER, coords = (MIN_X, MIN_Y)),
                                   Entity(content = LOWER_FIELD_BORDER, coords = (MIN_X, MAX_Y))])
for y in range(MIN_Y + 1, MAX_Y):
    GameController.my_entities.update([Entity(content = LATERAL_FIELD_BORDER_CHARACTER, coords = (MIN_X, y)),
                                       Entity(content = LATERAL_FIELD_BORDER_CHARACTER, coords = (MAX_X, y))])

GameController.set_footer(Entity("Press spacebar when you are ready.", colors.NONE, coords = FOOTER_START_COORDINATES))
GameController.refresh_screen()
while ' ' != getch(): pass
clear_screen()
print("Connecting to the server...")

s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.connect((HOST, PORT))
    sendall_with_end(s, SOCKET_CONNECTION_ESTABLISHED)
    data: bytes = recvall(s) # receive SOCKET_CONNECTION_ESTABLISHED or SOCKET_LOBBY_FULL
    if data == SOCKET_LOBBY_FULL:
        clear_screen()
        print("The game has already started, please wait until it is finished. Press spacebar to exit.")
        GameController.close_game = True
        while ' ' != getch(): pass
        sys.exit()
    data = recvall(s) # receive player number

    GameController.player_num = int.from_bytes(data)
    GameController.player_color = PLAYER_COLORS[GameController.player_num]
    GameController.set_footer(Entity(f"You are player {GameController.player_num}.", colors.NONE, coords = FOOTER_START_COORDINATES))

    GameController.my_entities.add(Entity(content = PLAYER_SIDE_BORDER, 
                                          coords = (MIN_X + 1, MAX_Y - (PLAYER_SIDE_HEIGHT + 2)), 
                                          color = GameController.player_color))
    GameController.my_entities.add(Entity(content = PLAYER_SIDE_BORDER, 
                                          coords = (MIN_X + 1, MIN_Y + (PLAYER_SIDE_HEIGHT + 2)), 
                                          color = PLAYER_COLORS[1 + (GameController.player_num + 1 - 1) % (len(PLAYER_COLORS) - 1)]))
                                          # the color is taken from PLAYER_COLORS by adding 1 to the player_num and wrapping around back to index 1 if player_num + 1 is out of bounds
    if GameController.player_num == 1:
        GameController.my_turn = True
    
    GameController.my_entities.add(Entity(content = PHARAOH, coords = PHARAOH_COORDINATES, color = colors.WHITE, public=True))

    for guard_card in GameController.guard_list:
        GameController.my_entities.add(guard_card)

    GameController.my_entities.add(GameController.main_warrior_list)
    GameController.my_entities.add(GameController.main_bandage_list)
    GameController.my_entities.add(GameController.main_building_list)

    ## TESTING
    GameController.main_bandage_list.append(BandageCard(CardState(colors.GREEN, face_values.FACE_VALUE_BANDAGE, pos_in_level=1), public = True))
    GameController.main_warrior_list.append(WarriorCard(power = 0, public = True))

    # GameController.my_entities.add(WarriorCard(power = 0, public = True, coords = Coordinates(17, 17)))
    # GameController.my_entities.add(WarriorCard(power = 1, public = True, coords = Coordinates(17, 18)))
    # GameController.my_entities.add(WarriorCard(power = 2, public = True, coords = Coordinates(17, 16)))
    # GameController.my_entities.add(WarriorCard(power = 3, public = True, coords = Coordinates(16, 17)))
    # GameController.my_entities.add(WarriorCard(power = 4, public = True, coords = Coordinates(18, 17)))
    ##

    GameController.refresh_screen()

    GameController.send_public_entities()
    GameController.receive_public_entities()

    GameController.second_player_joined = True

    GameController.controls = {
        escape_sequences.CTRL_C: lambda: (
            (_ for _ in []).throw(KeyboardInterrupt) # a small hack to raise exceptions from lambda functions
            ),
        escape_sequences.ARROW_UP: lambda: (
            GameController.cursor.select_previous(), 
            GameController.refresh_screen()
            ),
        escape_sequences.ARROW_LEFT: lambda: (
            GameController.cursor.select_previous(), 
            GameController.refresh_screen()
            ),
        escape_sequences.ARROW_DOWN: lambda: (
            GameController.cursor.select_next(), 
            GameController.refresh_screen()
            ),
        escape_sequences.ARROW_RIGHT: lambda: (
            GameController.cursor.select_next(), 
            GameController.refresh_screen()
            ),
        ' ': lambda: (
            GameController.cursor.selected.action()
            if isinstance(GameController.cursor.selected, ActionEntry)
            else (
                GameController.set_footer(create_action_menu(GameController.cursor.selected)),
                GameController.refresh_screen()
                )
            ),
        '1': lambda: (
            GameController.main_warrior_list.append(WarriorCard(power = 0, public = True)), 
            GameController.refresh_screen(), 
            GameController.send_public_entities(), 
            GameController.end_turn()
            ),
        '2': lambda: (
            GameController.main_bandage_list.append(BandageCard(state_index = 0, public = True)), 
            GameController.refresh_screen(), 
            GameController.send_public_entities(), 
            GameController.end_turn()
            ),
        '3': lambda: (
            GameController.main_building_list.append(BuildingCard(building_type = face_values.HOSPITAL)), 
            GameController.refresh_screen(), 
            GameController.send_public_entities(), 
            GameController.end_turn()
            )
    }

    while not GameController.close_game:
        if GameController.my_turn:

            if _os_name == "nt":
                while msvcrt.kbhit():
                    getch()
            
            GameController.cursor.show()
            GameController.refresh_screen()

            while GameController.my_turn:
                key = getch()
                if key == escape_sequences.ESCAPE:
                    for i in range(escape_sequences.ESCAPE_SEQUENCE_LENGTH - 1):
                        key += getch()

                if key not in GameController.controls:
                    continue
                else:
                    GameController.controls[key]()
        else:
            GameController.cursor.hide()
            GameController.refresh_screen()
            while GameController.receive_public_entities():
                GameController.refresh_screen()

except (KeyboardInterrupt): # KeyboardInterrupt
    sys.exit()

except (ConnectionRefusedError, TimeoutError, ConnectionResetError): # the error occurs while trying to establish the connection
    clear_screen()
    print("Server is offline, unable to connect. Press spacebar to exit.")
    close_game_on_space()

except (BrokenPipeError, ConnectionError): # the error occurs while trying to send or read data from the server
    clear_screen()
    print("Server has disconnected. Press spacebar to exit.")
    close_game_on_space()
    
except TerminationRequest: # received a termination request from the server
    clear_screen()
    print("Your opponent has disconnected, unable to continue. Press spacebar to exit.")
    close_game_on_space()