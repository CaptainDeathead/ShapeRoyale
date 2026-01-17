import json
import socket

from threading import Thread

class BaseClient:
    def __init__(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        self.conn = conn
        self.addr = addr

        self.dead = False

    def disconnect(self) -> None:
        print(f"Disconnecting client {self.addr}.")

        self.dead = True
        self.conn.close()

    def send(self, json_data: dict[any, any]) -> None:
        data = json.dumps(json_data)
        raw_data = data.encode()
        data_size = len(raw_data).to_bytes(4, byteorder="big") # 4 bytes

        try:
            self.conn.sendall(data_size + raw_data)
        except Exception as e:
            print(f"BaseClient - Error while sending data! {e}.")

    def recv(self) -> dict[any, any]:
        try:
            data_size = int.from_bytes(self.conn.recv(4), byteorder="big")
        except Exception as e:
            print(f"BaseClient - Error while receiving data size! {e}. Attempting to clear receive buffer!")
            try:
                self.conn.recv(99999)
            except Exception as e1:
                print(f"BaseClient - Error while clearing buffer due to error! {e1}. Assuming this connection is dead.")
                self.disconnect()
                return {}

        try:
            raw_data = self.conn.recv(data_size)
        except Exception as e:
            print(f"BaseClient - Error while receiving data! {e}. Attempting to clear receive buffer!")
            try:
                self.conn.recv(99999)
            except Exception as e1:
                print(f"BaseClient - Error while clearing buffer due to error! {e1}. Assuming this connection is dead.")
                self.disconnect()
                return {}

        data = raw_data.decode()

        try:
            json_data = json.loads(data)
        except Exception as e:
            print(f"BaseClient - Error while loading json data! {e}. Assuming the server disconnected (connection dead).")
            self.disconnect()
            return {}

        return json_data

class Client:
    def __init__(self, host: str, port: int) -> None:
        self.HOST = host
        self.PORT = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.base_client = None

    @property
    def send(self) -> object:
        if self.base_client is None:
            raise Exception(f"Client - Error while getting send! Cannot send data when not connected (No BaseClient)!")

        if self.base_client.dead:
            raise Exception(f"Client - Error while getting send! Cannot send data when not connected (Connection dead)!")

        return self.base_client.send

    @property
    def recv(self) -> object:
        if self.base_client is None:
            raise Exception(f"Client - Error while getting recv! Cannot receive data when not connected (No BaseClient)!")

        if self.base_client.dead:
            raise Exception(f"Client - Error while getting recv! Cannot receive data when not connected (Connection dead)!")

        return self.base_client.recv

    def connect(self) -> None:
        print("Connecting...")
        self.sock.connect((self.HOST, self.PORT))
        self.base_client = BaseClient(self.sock, (self.HOST, self.PORT))
        print("Connected successfully!")

class Server:
    def __init__(self, host: str, port: int) -> None:
        self.HOST = host
        self.PORT = port

        self.clients = []

        self.outgoing_blocks = {}
        self.incoming_blocks = {}

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server_thread = Thread(target=self.start, daemon=True)
        self.server_thread.start()
    
    @property
    def address(self) -> tuple[str, int]: return (self.ip, self.port)

    @property
    def num_connections(self) -> int: return len(self.clients)

    def handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        print(f"Client with addr {addr} connected!")

        self.clients.append(BaseClient(conn, addr))
        
    def start(self) -> None:
        print(f"Running server on {(self.HOST, self.PORT)}...")

        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()

        while 1:
            conn, addr = self.sock.accept()
            self.handle_client(conn, addr)