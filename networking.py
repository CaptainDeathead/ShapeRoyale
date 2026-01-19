import json
import socket
import zlib

from time import sleep
from threading import Thread
from typing import Generator

class BaseClient:
    def __init__(self, conn: socket.socket, addr: tuple[str, int], is_client: bool) -> None:
        self.conn = conn
        self.addr = addr
        #self.sockname = list(self.conn.getsockname())
        self.is_client = is_client

        self.dead = False
        self.raw_data_stream = []

        self.disconnect_on_fail = not self.is_client

        self.recv_thread = Thread(target=self.poll_recv, daemon=True)
        if not self.is_client:
            self.recv_thread.start()
    
    @property
    def data_stream(self) -> Generator:
        data = self.raw_data_stream
        self.raw_data_stream = []
        yield from data

    def disconnect(self) -> None:
        print(f"Disconnecting client {self.addr}.")

        self.dead = True
        try:
            self.recv_thread.join()
        except Exception as e:
            print(f"BaseClient - Error while joining recv_thread! {e}.")

    def poll_recv(self) -> None:
        while 1:
            data = self.recv()
            if data == {}:
                continue

            self.raw_data_stream.append(data)
        
    def sendnoto(self, json_data: dict[any, any]) -> None:
        self.send(json_data, to=False)

    def send(self, json_data: dict[any, any], to: bool = True) -> None:
        #if to:
        #    json_data["to"] = list(self.addr)

        data = json.dumps(json_data)
        raw_data = zlib.compress(data.encode())
        data_size = len(raw_data).to_bytes(4, byteorder="big") # 4 bytes

        try:
            self.conn.sendto(data_size + raw_data, self.addr)
            #self.conn.sendto(zlib.compress(raw_data), self.addr)
        except Exception as e:
            print(f"BaseClient - Error while sending data! {e}.")

    def proc_recv(self, raw_data: bytes) -> None:
        data = zlib.decompress(raw_data).decode()
        #print(data)

        try:
            json_data = json.loads(data)

            if json_data.get("question") == "hello?":
                print("Sent init.")
                self.send({"answer": "hi"})
                return
            #jif json_data.get("to", self.sockname) != self.sockname:
            #    return {}

        except Exception as e:
            print(f"BaseClient - Error while loading json data! {e}. Assuming the server disconnected (connection dead).")
            self.disconnect()
            return {}

        self.raw_data_stream.append(json_data)

    def recv_exact(self, n: int) -> bytes:
        buf = b''
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Connection bad")
            buf += chunk
        return buf

    def recv(self) -> dict[any, any]:
        try:
            data_size = int.from_bytes(self.recv_exact(4), byteorder="big")
        except Exception as e:
            print(f"BaseClient - Error while receiving data size! {e}. Attempting to clear receive buffer!")
            exit()
            try:
                self.conn.recv(99999)
            except Exception as e1:
                print(f"BaseClient - Error while clearing buffer due to error! {e1}. Assuming this connection is dead.")
                if self.disconnect_on_fail:
                    self.disconnect()
                return {}

        try:
            raw_data = zlib.decompress(self.recv_exact(data_size))
        except Exception as e:
            print(f"BaseClient - Error while receiving data! {e}. Attempting to clear receive buffer!")
            try:
                self.conn.recv(4096)
            except Exception as e1:
                print(f"BaseClient - Error while clearing buffer due to error! {e1}. Assuming this connection is dead.")
                if self.disconnect_on_fail:
                    self.disconnect()
                return {}
            return {}

        data = raw_data.decode()
        #print(data)

        try:
            json_data = json.loads(data)
            #jif json_data.get("to", self.sockname) != self.sockname:
            #    return {}

        except Exception as e:
            print(f"BaseClient - Error while loading json data! {e}. Assuming the server disconnected (connection dead).")
            if self.disconnect_on_fail:
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

        return self.base_client.sendnoto

    @property
    def recv(self) -> object:
        if self.base_client is None:
            raise Exception(f"Client - Error while getting recv! Cannot receive data when not connected (No BaseClient)!")

        if self.base_client.dead:
            raise Exception(f"Client - Error while getting recv! Cannot receive data when not connected (Connection dead)!")

        return self.base_client.recv

    def connect(self, max_retries: bool = 3) -> bool:
        curr_try = 0
            
        if self.base_client is None:
            self.base_client = BaseClient(self.sock, (self.HOST, self.PORT), True)

        while curr_try < max_retries:
            curr_try += 1
            print("Connecting...")
            try:
                self.sock.connect((self.HOST, self.PORT))
                self.base_client.recv_thread.start()
                return True
            except:
                ...

        return False
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

    def handle_client(self, conn: bytes, addr: tuple[str, int]) -> None:
        for client in self.clients:
            if client.addr == addr:
                #client.proc_recv(data)
                return

        print(f"Client with addr {addr} connected!")

        self.clients.append(BaseClient(conn, addr, False))
        #self.clients[-1].send({"answer": "hi"})

    def sendall(self, json_data: dict[any, any]) -> None:
        for client in self.clients:
            client.send(json_data)
        
    def start(self) -> None:
        print(f"Running server on {(self.HOST, self.PORT)}...")

        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()

        while 1:
            conn, addr = self.sock.accept()
            #data, addr = self.sock.recvfrom(2048)
            self.handle_client(conn, addr)

    def shutdown(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            print(f"Server - Error while shutting down! {e}.")
        
        self.sock.close()