import sys

from networking import Server, Client


if sys.argv[1] == "server":
    server = Server(sys.argv[2], int(sys.argv[3]))

    while 1:
        data = input()
        for client in server.clients:
            client.send({'message': data})

elif sys.argv[1] == "client":
    client = Client(sys.argv[2], int(sys.argv[3]))
    client.connect()

    while not client.base_client.dead:
        print(client.base_client.recv())