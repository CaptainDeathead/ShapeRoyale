import json
import socket
import zlib
import asyncio
import uuid

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
        #if not self.is_client:
        #    self.recv_thread.start()
    
    @property
    def data_stream(self) -> Generator:
        data = self.raw_data_stream
        self.raw_data_stream = []
        #if len(data) > 0:
        #    print(f"Removing: {data}")
        yield from data

    def disconnect(self) -> None:
        print(f"Disconnecting client {self.addr}.")

        self.dead = True
        try:
            self.recv_thread.join()
        except Exception as e:
            print(f"BaseClient - Error while joining recv_thread! {e}.")

    async def poll_recv(self) -> None:
        async for message in self.conn:
            #print(message)
            try:
                #data = zlib.decompress(message).decode()
                ...
            except Exception as e:
                print(f"BaseClient - Error while receiving data! {e}.")
                continue

            try:
                json_data = json.loads(message)
            except Exception as e:
                print(f"BaseClient - Error while loading json data! {e}.")
                continue

            if json_data == {}:
                continue

            self.raw_data_stream.append(json_data)

        print("Connection to client closed")
        
    def sendnoto(self, json_data: dict[any, any]) -> None:
        self.send(json_data, to=False)

    async def server_send(self, json_data: dict[any, any], to: bool = True) -> None:
        data = json.dumps(json_data)
        #raw_data = zlib.compress(data.encode())
        raw_data = data
        data_size = len(raw_data).to_bytes(4, byteorder="big") # 4 bytes

        #print(f"BaseClient - Sending data: {raw_data}")
        try:
            #self.conn.sendto(data_size + raw_data, self.addr)
            await self.conn.send(raw_data)
        except Exception as e:
            print(f"BaseClient - Error while sending data! {e}.")

    def send(self, json_data: dict[any, any], to: bool = True) -> None:
        #if to:
        #    json_data["to"] = list(self.addr)

        data = json.dumps(json_data)
        #raw_data = zlib.compress(data.encode())
        raw_data = data
        data_size = len(raw_data).to_bytes(4, byteorder="big") # 4 bytes

        #print(f"BaseClient - Sending data: {raw_data}")
        try:
            #self.conn.sendto(data_size + raw_data, self.addr)
            self.conn.send(raw_data)
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

class WebSocketClient:
    def __init__(self, host: str, port: int, existing_uuid: str | None = None) -> None:
        self.HOST = host
        self.PORT = port

        self.ws = None
        self.base_client = None

        self.connected = False

        import js
        js.console.log(f"Given uuid: {existing_uuid}")
        self.uuid = str(uuid.uuid4()) if existing_uuid is None else existing_uuid
        js.console.log(f"Chosen uuid: {self.uuid}")

        self.allow_reconnect = True

    def on_open(self, event):
        print("Connected")
        self.connected = True
        self.base_client = BaseClient(self.ws, (self.HOST, self.PORT), True)

    def on_message(self, event):
        #print(event.data)
        import js
        #js.console.log(event.data)
        try:
            #data = zlib.decompress(event.data).decode()
            ...
        except Exception as e:
            print(f"BaseClient - Error while receiving data! {e}.")
            return

        try:
            json_data = json.loads(event.data)
        except Exception as e:
            print(f"BaseClient - Error while loading json data! {e}.")
            return

        if json_data == {}:
            return

        self.base_client.raw_data_stream.append(json_data)

    def on_close(self, event):
        self.connected = False
        print(f"conn closed: {event.code}, {event.reason}")
        import js
        js.console.log(f"conn closed: {event.code}, {event.reason}")

        if self.allow_reconnect:
            asyncio.create_task(self.connect())

    def send(self, data):
        import js
        if self.base_client is not None:
            self.base_client.send(data)
            #js.console.log(str(data))
        else:
            print("BaseClient is None!")
            js.console.log("BaseClient is None!")

    async def connect(self, max_retries = None) -> bool:
        import js
        import traceback

        try:
            print("Connecting...")
            self.ws = js.eval(f'new WebSocket("ws://{self.HOST}:{self.PORT}")')

            self.ws.onopen = self.on_open
            self.ws.onmessage = self.on_message
            self.ws.onclose = self.on_close

            while 1:
                try:
                    self.ws.send(json.dumps({"auth": self.uuid}))
                    break
                except Exception as e:
                    #js.console.log(f"{self.ws.send}")
                    js.console.log(f"Error while sending auth: {e}")
                    js.console.log(f"{traceback.format_exc()}")
                    await asyncio.sleep(0.1)

            while self.connected:
                #self.ws.send("alive")
                await asyncio.sleep(1)

        except Exception as e:
            print(f"WSClient - Error while connecting: {e}")
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
        for client in self.clients:
            client.conn.close()

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            print(f"Server - Error while shutting down! {e}.")
        
        self.sock.close()

class WebSocketServer:
    def __init__(self, host: str, port: str) -> None:
        self.HOST = host
        self.PORT = port

        import importlib 
        self.websockets = importlib.import_module("websockets")
        self.clients = []
        self.server = None

    async def sendall(self, msg):
        for client in self.clients:
            await client.send(msg)

    async def gatekeeper(self, ws):
        print("Server - Gatekeeping client (awaiting auth)...")
        async for message in ws:
            try:
                data = json.loads(message)

                if data.get("auth"):
                    client_id = data.get("auth")
                    for client in self.clients:
                        if client.addr[1] == client_id:
                            client.conn = ws
                            client.dead = False
                            print(f"Server - Client with uuid ({client_id}) reconnected!")
                            await client.poll_recv()
                            return

                    await self.handler(ws, client_id)
                    return

            except Exception as e:
                print(f"Server - Error while connecting client: {e}")

    async def handler(self, ws, client_id):
        bc = BaseClient(ws, ("", client_id), False)
        bc.send = bc.server_send
        self.clients.append(bc)
        print(f"Server - New client connected with uuid ({client_id})!")
        await bc.poll_recv()

    async def broadcast(self, message):
        for client in self.clients:
            try:
                await client.ws.send(message)
            except Exception as e:
                print(f"Server - Error while sending message! {e}.")

    async def start(self):
        while 1:
            try:
                self.server = await self.websockets.serve(self.gatekeeper, self.HOST, self.PORT)
                break
            except OSError as e:
                print(f"Server - Bind failed: {e}")

        print(f"Server started on ws://{self.HOST}:{self.PORT}")
        await asyncio.Future()