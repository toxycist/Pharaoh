import select
import time
from shared_definitions import *

HOST: str = ''
PORT: int = 1717

connections: Dict[Tuple[socket.socket, Any], int] = {}

PLAYER_COLORS = [colors.BLUE, colors.YELLOW]

def print_player_info(player_color: str, player_addr: Any, player_num: int, info):
    print(player_color + f"{player_addr} [PLAYER {player_num}] " + colors.ENDC + info)

def print_player_msg(player_color: str, player_addr: Any, player_num: int, msg):
    print(player_color + f"{player_addr} [PLAYER {player_num}]: " + colors.ENDC + msg)

def reject_client(conn: socket.socket, addr: Any) -> None:
    print_player_info(colors.RED, addr, len(PLAYER_COLORS) + 1, "connected. Lobby is full, rejecting...")
    with conn:
        try:
            sendall_with_end(conn, SOCKET_LOBBY_FULL)
            data: bytes = b""
            while data:
                data = conn.recv(1024) # wait until the client disconnects
            return
        finally:
            print_player_info(colors.RED, addr, len(PLAYER_COLORS) + 1, "disconnected")
            return
        
def handle_client(conn: socket.socket, addr: Any) -> None:
    player_num: int = connections[(conn, addr)]
    player_color = PLAYER_COLORS[player_num - 1]

    print_player_info(player_color, addr, player_num, "connected")
    with conn:
        try:
            other_player = None
            while True:
                encoded_data: bytes = recvall(conn)
                decoded_data: str = encoded_data.decode()
                print_player_msg(player_color, addr, player_num, decoded_data)
                if encoded_data == SOCKET_CONNECTION_ESTABLISHED:
                    sendall_with_end(conn, SOCKET_CONNECTION_ESTABLISHED)
                    sendall_with_end(conn, player_num.to_bytes())
                    connections[(conn, addr)] = "ready"

                elif encoded_data == SOCKET_SHARED_ENTITIES_UPDATE:
                    public_entities: List[Entity] = pickle.loads(recvall(conn))
                    for entity in public_entities:
                        print_player_info(player_color, addr, player_num, f"Received entity [{entity}] at {entity.coords}")

                        if isinstance(entity, Iterable) and len(entity) > 0:
                            print_player_info(player_color, addr, player_num, f"Entity [{entity}] contains:")
                            for e in entity:
                                print_player_info(player_color, addr, player_num, f"[{e}] at {e.coords}")

                    entities_sent: bool = False
                    while not entities_sent: # this could be an endless loop if the second player hasn't yet joined, so if this player disconnects, we need to handle that
                        if len(connections) > 1:
                            other_conn_addr = next((conn_addr for conn_addr in list(connections.keys()) if conn_addr != (conn, addr)), None)
                            if other_conn_addr and connections[other_conn_addr] == "ready":
                                other_player: socket.socket = other_conn_addr[0]
                                sendall_with_end(other_player, SOCKET_SHARED_ENTITIES_UPDATE)
                                sendall_with_end(other_player, pickle.dumps(public_entities))
                                entities_sent = True
                        else:
                            incoming_data, _, _ = select.select([conn], [], [], 1.0) # timeout for recv is set to 1 second
                            if incoming_data: # probably a disconnection, because the client should not have anything to say at this point
                                recvall(conn)
                            else:
                                continue

                elif encoded_data == SOCKET_YOUR_TURN:
                    sendall_with_end(other_player, SOCKET_YOUR_TURN)
        except ConnectionError:
            if len(connections) == 0: # the error is initiated by another connection, which has already cleared up the list of connections
                conn.close()
                print_player_info(player_color, addr, player_num, "terminated")
            else: # the error is initiated by this connection
                conn.close()
                print_player_info(player_color, addr, player_num, "disconnected")
                if other_player:
                    print("Unable to continue the game session. Terminating remaining connections...")
                    sendall_with_end(other_player, SOCKET_TERMINATION_REQUEST)
                    other_player.shutdown(socket.SHUT_RDWR)
                connections.clear()
            return

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Listening on {HOST}:{PORT}")

    while True:
        conn: socket.socket
        addr: Any
        conn, addr = s.accept()
        if len(connections) < 2:
            connections[(conn, addr)] = len(connections) + 1 # set player number
            client_thread: threading.Thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()
        else:
            rejection_thread: threading.Thread = threading.Thread(target=reject_client, args=(conn, addr))
            rejection_thread.start()