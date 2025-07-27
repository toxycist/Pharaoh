import time
from shared_definitions import *

HOST: str = ''
PORT: int = 1717

connections: Dict[Tuple[socket.socket, Any], int] = {}

def poke_the_client(conn: socket.socket, player_num: int) -> None:
    while True:
        time.sleep(0.5)
        if conn.fileno() == -1:
            # if len(connections) == 0 it means the dictionary is being cleaned up, else just a normal disconnection
            if len(connections) == 0:
                print(f"{addr} [PLAYER {player_num}] terminated.")
            else:
                print(f"{addr} [PLAYER {player_num}] disconnected. Unable to continue the game session. Terminating connections...")
                for conn_addr in list(connections.keys()):
                    conn_addr[0].close()
                connections.clear()
            return

def reject_client(conn: socket.socket, addr: Any) -> None:
    print(f"{addr} connected. Lobby is full, rejecting...")
    with conn:
        try:
            sendall_with_end(conn, SOCKET_LOBBY_FULL)
            data: bytes = b""
            while data != b"":
                data = conn.recv(1024) # wait until the client disconnects
            return
        finally:
            print(f"{addr} disconnected")
            return

def handle_client(conn: socket.socket, addr: Any) -> None:
    player_num: int = connections[(conn, addr)]

    poke_the_client_thread: threading.Thread = threading.Thread(target=poke_the_client, args=(conn, player_num))
    poke_the_client_thread.start()

    print(f"{addr} [PLAYER {player_num}] connected")
    with conn:
        try:
            other_player: socket.socket | None = None
            while True:
                encoded_data: bytes = recvall(conn)
                decoded_data: str = encoded_data.decode()
                print(f"{addr} [PLAYER {player_num}]: {decoded_data}")
                if encoded_data == SOCKET_CONNECTION_ESTABLISHED:
                    sendall_with_end(conn, SOCKET_CONNECTION_ESTABLISHED)
                    sendall_with_end(conn, player_num.to_bytes())
                    connections[(conn, addr)] = "ready"
                elif encoded_data == SOCKET_SHARED_ENTITIES_UPDATE:
                    public_entities: Dict[Tuple[int, int], List[Entity]] = pickle.loads(recvall(conn))
                    print(f"{addr} [PLAYER {player_num}] Received entities: ", end = "")
                    print(public_entities)

                    entities_sent: bool = False
                    while not entities_sent:
                        for other_conn_addr in list(connections.keys()):
                            if other_conn_addr != (conn, addr) and connections[other_conn_addr] == "ready":
                                other_player: socket = other_conn_addr[0]
                                sendall_with_end(other_player, SOCKET_SHARED_ENTITIES_UPDATE)
                                sendall_with_end(other_player, pickle.dumps(public_entities))
                                entities_sent = True
                elif encoded_data == SOCKET_YOUR_TURN:
                    sendall_with_end(other_player, SOCKET_YOUR_TURN)
        except Exception:
            return

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    print(f"Listening on {HOST}:{PORT}")

    while True:
        conn: socket.socket
        addr: Any
        conn, addr = s.accept()
        if len(connections) < 2:
            connections[(conn, addr)] = (len(connections) + 1) # set player number
            client_thread: threading.Thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()
        else:
            rejection_thread: threading.Thread = threading.Thread(target=reject_client, args=(conn, addr))
            rejection_thread.start()