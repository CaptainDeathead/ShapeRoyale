import pygame as pg
import pygame_gui
import os
import sys
import asyncio

#from sound import generate_sine_wave

from menus import MainMenu, EndScreen
from bullet import Bullet
from shape import Player, Shape
from powerups import Powerup
from utils import AnimManager, FONTS_PATH
from eventfeed import EventFeed, GameEvent

from leaderboard import Leaderboard
from joystick import TouchJoystick

from networking import Server, Client, BaseClient, WebSocketServer, WebSocketClient

from time import time, sleep
from json import loads
from math import dist, sqrt, floor, ceil, atan2, degrees
from random import randint, choice, uniform, Random, randrange

from copy import deepcopy
from typing import List, Sequence, Dict

startup_str = """
    ||
╭────────╮
│        │
│        │
│        │
╰────────╯
"""

print(startup_str)

pg.init()

class Sound:
    def __init__(self, *args) -> None: ...
    def play(self, *args) -> None: ...
    def set_volume(self, *args) -> None: ...

class Screen(pg.Surface):
    def __init__(self, rect: pg.Rect, flags: int = 0) -> None:
        self.positioning_rect = rect

        super().__init__(rect.size, flags)

    @property
    def x(self) -> int: return self.positioning_rect.x

    @property
    def y(self) -> int: return self.positioning_rect.y

    @property
    def pos(self) -> Sequence[int]: return (self.positioning_rect.x, self.positioning_rect.y)

class Safezone:
    NUM_POINTS = 100
    DISTANCE_TO_MOVE_REDUCTION = 1000
    TARGET_RADIUS_ALLOWANCE = 1.05
    SCALING = 80
    SPEED = 100

    def __init__(self, screen_width: int, screen_height: int, map_size_x: int, map_size_y: int, phase_config: Dict[int, Dict]) -> None:
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.map_size_x = map_size_x
        self.map_size_y = map_size_y

        self.phase_config = phase_config
        self.phase_index = 0
        self.start_radius = self.phase_config[self.phase_index]["radius"]

        self.color = pg.Color(255, 0, 0)

        self.surface = pg.Surface((screen_width, screen_height))

        self.anims = []

        self.left_wall = 0
        self.right_wall = self.map_size_x
        self.top_wall = 0
        self.bottom_wall = self.map_size_y

        self.dt = 0.016 # 60fps

        self.next_phase()

    def next_phase(self) -> None:
        if self.phase_index >= len(self.phase_config):
            self.target_radius = 0
            return

        if self.phase_index > 0: return

        self.phase_index += 1

        self.target = self.phase_config[self.phase_index]["target"]
        self.target_radius = self.phase_config[self.phase_index]["radius"]
        self.zone_speed = self.SPEED

        #self.anims.append(AnimManager().new(self, "left_wall", self.target[0] - self.target_radius, self.zone_speed))
        #self.anims.append(AnimManager().new(self, "right_wall", self.target[0] + self.target_radius, -self.zone_speed))
        #self.anims.append(AnimManager().new(self, "top_wall", self.target[1] - self.target_radius, self.zone_speed))
        #self.anims.append(AnimManager().new(self, "bottom_wall", self.target[1] + self.target_radius, -self.zone_speed))
        self.anims.append(AnimManager().new(self, "left_wall", self.right_wall, self.zone_speed))
        self.anims.append(AnimManager().new(self, "right_wall", self.left_wall, -self.zone_speed))
        self.anims.append(AnimManager().new(self, "top_wall", self.bottom_wall, self.zone_speed))
        self.anims.append(AnimManager().new(self, "bottom_wall", self.top_wall, -self.zone_speed))

    def update(self, dt: float) -> None:
        self.dt = dt

        for anim in self.anims:
            if not anim.finished:
                return

        self.next_phase()

    def get_wall_distance(self, player: Shape) -> tuple[float, float, float, float]:
        left_wall = self.left_wall - player.x
        right_wall = self.right_wall - player.x 
        top_wall = self.top_wall - player.y
        bottom_wall = self.bottom_wall - player.y

        if left_wall > self.screen_width / 2 or right_wall < self.screen_width / 2 or top_wall > self.screen_height / 2 or bottom_wall < self.screen_height / 2:
            #player.add_poison(None, 30 * self.dt, 0.0, 2.0)
            player.take_damage((50 + player.health_regen_rate) * self.dt / player.zone_resistance)

        return (left_wall, right_wall, top_wall, bottom_wall)

    def blit(self, screen: pg.Surface, draw_parent: Shape) -> None:
        self.surface.fill((0, 0, 0))
        self.surface.set_alpha(180)

        left_wall, right_wall, top_wall, bottom_wall = self.get_wall_distance(draw_parent)

        pg.draw.rect(self.surface, (255, 0, 0), (0, 0, left_wall, screen.height))
        pg.draw.rect(self.surface, (255, 0, 0), (right_wall, 0, screen.width - right_wall, screen.height))
        pg.draw.rect(self.surface, (255, 0, 0), (0, 0, screen.width, top_wall))
        pg.draw.rect(self.surface, (255, 0, 0), (0, bottom_wall, screen.width, screen.height - bottom_wall))

        screen.blit(self.surface, (0, 0))

class ShapeRoyale:
    PYGAME_INFO: any = pg.display.Info()
    #WIDTH: int = PYGAME_INFO.current_w
    #HEIGHT: int = PYGAME_INFO.current_h
    WIDTH: int = 1920
    HEIGHT: int = 1080

    MAP_SIZE = 30_000
    MAP_SIZE_X = MAP_SIZE
    MAP_SIZE_Y = MAP_SIZE

    NUM_PHASES = 4
    NUM_PLAYERS = 100
    NUM_POWERUP_SECTIONS = 24 
    NUM_POWERUPS = NUM_POWERUP_SECTIONS * 20 # this must be divisible by the NUM_POWERUP_SECTIONS
    POWERUP_SECTION_SIZE = MAP_SIZE / NUM_POWERUP_SECTIONS

    MAX_BULLET_TRAVEL_DIST = 2000

    BG_COLOR = (0, 0, 0)

    def __init__(self, display_surf: pg.Surface | None = None, client: Client | None = None, server: Server | None = None, main_menu_manager: pygame_gui.UIManager | None = None) -> None:
        if not (self.NUM_POWERUPS / self.NUM_POWERUP_SECTIONS).is_integer() or self.NUM_POWERUPS % self.NUM_POWERUP_SECTIONS != 0:
            raise Exception("NUM_POWERUPS must be divisible by NUM_POWERUP_SECTIONS such that the resualt is a valid integer!")

        info = pg.display.get_desktop_sizes()[0]
        #self.WIDTH = min(info[0], 1920)
        #self.HEIGHT = min(info[1], 1080)
        self.WIDTH = 1920
        self.HEIGHT = 1080
        
        if display_surf is None:
            self.screen = pg.display.set_mode((self.WIDTH, self.HEIGHT), pg.SRCALPHA | pg.FULLSCREEN | pg.SCALED, display=0)
        else:
            self.screen = display_surf

        self.anim_manager = AnimManager()
        self.eventfeed = EventFeed(self.screen, pg.Font(f"{FONTS_PATH}/PressStart2P.ttf", 20))

        self.server = server
        self.client = client
        self.player_name = "player"
        self.main_menu_manager = main_menu_manager
        self.dead_server = None
        self.auto_start = False

        self.clock = pg.time.Clock()

    async def run(self) -> None:
        if self.client is not None:
            await self.join_server(self.client.HOST, self.client.PORT, self.player_name, self.client.uuid) # Client will be dead so we reset
        elif self.server is not None:
            await self.host_server(self.server.HOST, self.server.PORT) # Server will be dead so we reset

        if sys.platform == "emscripten":
            import js
            params = js.eval("new URLSearchParams(window.location.search)")
            host = params.get("host")
            port = params.get("port")

            if host is not None and port is not None and self.client is None:
                await self.join_server(host, port, self.player_name)

        if len(sys.argv) > 1:
            if sys.argv[1] == "host":
                await self.host_server(sys.argv[2], sys.argv[3])
                self.auto_start = True
                pg.Sound = Sound # For headless servers
            elif sys.argv[1] == "join":
                await self.join_server()

        if len(sys.argv) == 4 and (self.client is not None or self.server is not None):
            self.player_name = sys.argv[3]

        self.main_menu = MainMenu(self.screen, self.server, self.client, self.player_name, manager=self.main_menu_manager, auto_start=self.auto_start)
        await self.main_menu.main()
        self.player_name = self.main_menu.player_name

        if not self.main_menu.singleplayer and self.server is None and self.client is None:
            if self.main_menu.host:
                await self.host_server(self.main_menu.server_ip, self.main_menu.server_port)
                self.main_menu = MainMenu(self.screen, self.server, self.client, self.player_name, self.main_menu.player.shape_index, self.main_menu.manager)
            else:
                await self.join_server(self.main_menu.server_ip, self.main_menu.server_port, self.main_menu.player_name)
                self.main_menu = MainMenu(self.screen, self.server, self.client, self.player_name, self.main_menu.player.shape_index, self.main_menu.manager)

            await self.main_menu.main()

        self.squad_size = self.main_menu.squad_size

        self.manager = pygame_gui.UIManager((self.WIDTH, self.HEIGHT))

        real_player_info = {0: (self.main_menu.player.shape_index, self.main_menu.player_name, None)}

        if self.server is not None:
            start_wait_time = time()
            clients_responded = []
            while (len(real_player_info)-1 != len(self.server.clients)) and time() - start_wait_time < 5: # 5 seconds
                await asyncio.sleep(0)
                for i, client in enumerate(self.server.clients):
                    for message in client.data_stream:
                        print(message)
                        for dtype, query in message.items():
                            if dtype != "answer" or "send_starting_info" not in query:
                                continue
                            
                            player_name = query["send_starting_info"]["name"]
                            if len(player_name) > 25:
                                player_name = player_name[:25]

                            real_player_info[i+1] = (query["send_starting_info"]["shape_index"], player_name, client)
                            clients_responded.append(client)

            self.clients = clients_responded

        self.bullet_img = pg.transform.smoothscale(pg.image.load("./Data/assets/Bullet_Sprite.png").convert_alpha(), (10, 10))

        self.generate_safezone_phases(self.NUM_PHASES)
        self.safezone = Safezone(self.screen.width, self.screen.height, self.MAP_SIZE_X, self.MAP_SIZE_Y, self.phase_config)

        self.shape_names = ["Square", "Triangle", "Circle"]
        self.shape_images = {
            "SquareFriendly": pg.transform.smoothscale(pg.image.load("./Data/assets/Square_Sprite_Player.png"), (100, 100)).convert_alpha(),
            "SquareEnemy": pg.transform.smoothscale(pg.image.load("./Data/assets/Square_Sprite_Enemy.png"), (100, 100)).convert_alpha(),
            "TriangleFriendly": pg.transform.smoothscale(pg.image.load("./Data/assets/Triangle_Sprite_Player.png"), (100, 100)).convert_alpha(),
            "TriangleEnemy": pg.transform.smoothscale(pg.image.load("./Data/assets/Triangle_Sprite_Enemy.png"), (100, 100)).convert_alpha(),
            "CircleFriendly": pg.transform.smoothscale(pg.image.load("./Data/assets/Circle_Sprite_Player.png"), (100, 100)).convert_alpha(),
            "CircleEnemy": pg.transform.smoothscale(pg.image.load("./Data/assets/Circle_Sprite_Enemy.png"), (100, 100)).convert_alpha()
        }
        
        with open("./Data/shapes.json", "r") as f:
            self.shape_info = loads(f.read())

        with open("./Data/powerups.json", "r") as f:
            self.powerup_info = loads(f.read())

        self.powerup_grid = [[[] for _ in range(self.NUM_POWERUP_SECTIONS)] for _ in range(self.NUM_POWERUP_SECTIONS)]

        self.bullets = []
        self.dead_players = []

        self.players = []
        self.powerups = []

        self.powerup_stage_1_seed = randrange(2**32)
        self.powerup_stage_2_seed = randrange(2**32)

        if self.client is None:
            self.players = self.generate_players(real_player_info)
            self.powerups = await self.generate_powerups(self.powerup_stage_1_seed)

        self.sounds = {
            "hitHurt": pg.Sound("./Data/assets/Sounds/hitHurt.wav"),
            "laserShoot": pg.Sound("./Data/assets/Sounds/laserShoot.wav"),
            "powerUp": pg.Sound("./Data/assets/Sounds/powerUp.wav"),
        }
        self.sounds["hitHurt"].set_volume(0.70)
        self.sounds["laserShoot"].set_volume(0.70)
        self.sounds["powerUp"].set_volume(0.50)

        self.powerup_sections = [(i*self.POWERUP_SECTION_SIZE, (i+1)*self.POWERUP_SECTION_SIZE) for i in range(self.NUM_POWERUP_SECTIONS)]
        self.powerup_section_index = 0

        self.fps_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 15)
        self.spectating_lbl = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 60).render("You are spectating!", True, (255, 255, 255))

        self.ping = 0
        self.last_ping = 0

        self.spectator_index = 0
        self.spectating = self.main_menu.spectating
        self.spectator_player = None
        
        if len(self.players) > 0:
            self.player.is_player = not self.spectating
            self.starting_player = self.players[0]

        self.minimap_surf = pg.Surface((200, 200), pg.SRCALPHA)

        self.end_screen = None
        self.has_done_bonus_powerups = False

        self.movement_joystick = TouchJoystick(self.screen, (300, self.screen.height - 300))
        self.aim_joystick = TouchJoystick(self.screen, (self.screen.width - 300, self.screen.height - 300))

        self.active_fingers = {}

        #self.leaderboard = Leaderboard(self.screen, self.manager, [self.player_lb_info(player) for player in self.players])
        #self.leaderboard.window.hide()

        await self.main()
 
    @property
    def player(self) -> Player:
        try:
            return self.players[self.spectator_index]
        except:
            return self.players[0]

    def get_player(self, player_index: int) -> Shape | None:
        for player in self.players:
            if player.index == player_index:
                return player
        
        for player in self.dead_players:
            if player.index == player_index:
                return player

        return None

    def player_lb_info(self, player: Shape) -> Dict[str, any]:
        ret_dict = player.to_dict()
        ret_dict.update(player.to_winner_dict())

        squad = []
        for index in ret_dict["squad"]:
            squad.append(self.get_player(index).player_name)

        ret_dict["squad"] = squad

        return ret_dict

    async def host_server(self, ip: str, port: int) -> None:
        #self.server = Server(ip, port)
        self.server = WebSocketServer(ip, port)
        self.server_task = asyncio.create_task(self.server.start())

    async def join_server(self, ip: str, port: int, name: str, existing_uuid: str | None = None) -> Client:
        self.screen.fill((0, 0, 0))
        loading_lbl = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 60).render("Connecting to server...", True, (255, 255, 255))
        self.screen.blit(loading_lbl, (self.WIDTH // 2 - loading_lbl.width // 2, self.HEIGHT // 2 - loading_lbl.height // 2))

        self.client = WebSocketClient(ip, port, existing_uuid=existing_uuid)
        self.connect_task = asyncio.create_task(self.client.connect(max_retries=1))
        while not self.client.connected:
            dt = self.clock.tick(60) / 1000.0
            pg.display.flip()
            await asyncio.sleep(0)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit(0)

        self.player_name = name

        return self.client

    def generate_safezone_phases(self, num_phases: int) -> None:
        phase_config = {}

        #radius = (self.MAP_SIZE * sqrt(2)) // 2
        radius = self.MAP_SIZE // 2
        target = (self.MAP_SIZE_X / 2, self.MAP_SIZE_Y / 2)
        time = 60

        time_reduction = time // (num_phases - 1)

        for p in range(num_phases - 1):
            phase_config[p] = {
                "radius": radius,
                "target": target,
                "time": time
            }

            radius //= 2
            target = (randint(int(target[0] - radius), int(target[0] + radius)), randint(int(target[1] - radius), int(target[1] + radius)))
            time -= time_reduction

        phase_config[num_phases - 1] = {
            "radius": 0,
            "target": target,
            "time": 0
        }

        self.phase_config = phase_config

    def generate_players(self, real_player_info: List[tuple[int, str, Client | None]]) -> List[Shape]:
        shapes = []
        squads = [[] for squad in self.main_menu.active_squads]

        for i, (shape_index, name, client) in dict(sorted(real_player_info.items(), key=lambda item: item[0])).items():
            print(shape_index, name, client)
            shape_type = self.shape_names[shape_index]
            new_shape = Shape(
                self.MAP_SIZE, randint(3000, self.MAP_SIZE_X-3000), randint(3000, self.MAP_SIZE_Y-3000), i, shape_type, self.shape_info, self.shape_images[f"{shape_type}Friendly"],
                self.shape_images[f"{shape_type}Enemy"], self.bullets, self.bullet_img, True, [], client, name
            )
            
            curr_squad = []
            print(f"Squads: {self.main_menu.active_squads}")
            for squad_index, squad in enumerate(self.main_menu.active_squads):
                if i-1 in squad: # i-1 because the server has been inserted first into the indexes (trust me)
                    curr_squad = squads[squad_index]

            if len(curr_squad) > 0:
                new_shape.x, new_shape.y = curr_squad[-1].x + 200, curr_squad[-1].y

            curr_squad.append(new_shape)
            new_shape.squad = curr_squad
            shapes.append(new_shape)

            #if len(curr_squad) == self.squad_size:
            #    squads.append(curr_squad)
            #    curr_squad = []

        for i in range(len(shapes), self.NUM_PLAYERS):
        #for i in range(0):
            name = choice(self.shape_names)
            new_shape = Shape(
                self.MAP_SIZE, randint(3000, self.MAP_SIZE_X-3000), randint(3000, self.MAP_SIZE_Y-3000), i, name, self.shape_info, self.shape_images[f"{name}Friendly"],
                self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, is_player=False, squad=[], player_name=f"Bot {i+1}"
            )
            new_shape.squad.append(new_shape)
            shapes.append(new_shape)

        return shapes

    async def generate_powerups(self, seed: int, starting_index: int = 0, spawn_min_x: float = 0, spawn_max_x: float = MAP_SIZE-1, spawn_min_y: float = 0, spawn_max_y: float = MAP_SIZE-1) -> List[Powerup]:
        powerups = []

        common_rarity_max = self.powerup_info["Common"]["spawn_chance"]
        uncommon_rarity_max = self.powerup_info["Uncommon"]["spawn_chance"]
        rare_rarity_max = self.powerup_info["Rare"]["spawn_chance"]
        legendary_rarity_max = self.powerup_info["Legendary"]["spawn_chance"]

        rng = Random(seed)

        for i in range(self.NUM_POWERUPS):
            await asyncio.sleep(0)
            rarity_number = rng.uniform(0.0, 1.0)

            if rarity_number <= legendary_rarity_max: rarity = "Legendary"
            elif rarity_number <= legendary_rarity_max + rare_rarity_max: rarity = "Rare"
            elif rarity_number <= legendary_rarity_max + rare_rarity_max + uncommon_rarity_max: rarity = "Uncommon"
            else: rarity = "Common"

            powerup = Powerup(rng.randint(spawn_min_x, spawn_max_x), rng.randint(spawn_min_y, spawn_max_y), rarity, self.powerup_info, self.on_powerup_pickup, starting_index+i, rng.choice(list(self.powerup_info[rarity]["types"])))
            powerups.append(powerup)
            self.powerup_grid[floor(powerup.y / self.POWERUP_SECTION_SIZE)][floor(powerup.x / self.POWERUP_SECTION_SIZE)].append(powerup)

        return powerups

    def on_powerup_pickup(self, powerup: Powerup) -> None:
        if powerup in self.powerups:
            self.powerups.remove(powerup)

    async def restart(self) -> None:
        self.__init__(self.screen, self.client, self.dead_server, self.main_menu.manager)
        await self.run()

    async def main(self) -> None:
        dt_mut = 1
        dt_sum = 0

        if self.server is not None:
            player_data = [player.to_dict() for player in self.players]
            for i, client in enumerate(self.server.clients):
                await client.send({"answer": {"powerup_set": {"seed": self.powerup_stage_1_seed, "stage": 1}}})
                await client.send({"answer": {"player_set": player_data}})
                    #client.send({"answer": {"player_set": True}})
                await client.send({"answer": {"player_index": i+1}})

        if self.client is not None:
            done = False
            import js
            js.console.log("waiting for first main info")
            
            last_info_req = 0
            while not done:
                #self.client.send({"answer": {"send_starting_info": {"shape_index": self.main_menu.player.shape_index, "name": self.player_name}}})
                await asyncio.sleep(0)

                if self.spectating and time() - last_info_req > 0.5:
                    js.console.log("Requesting starting info")
                    self.client.send({"answer": {"send_starting_info": {"shape_index": self.main_menu.player.shape_index, "name": self.player_name}}})
                    last_info_req = time()

                for message in self.client.base_client.data_stream:
                    for dtype, query in message.items():
                        if dtype != "answer":
                            continue

                        if "powerup_set" in query:
                            js.console.log("Received powerup_set")
                            if query["powerup_set"]["stage"] == 1:
                                self.powerups = await self.generate_powerups(query["powerup_set"]["seed"])
                            else:
                                self.powerups.extend(await self.generate_powerups(query["powerup_set"]["seed"], self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))

                        elif "player_set" in query:
                            js.console.log("Received player_set")
                            self.players = [Shape(self.MAP_SIZE, player_desc["x"], player_desc["y"], player_desc["index"], player_desc["shape_name"], self.shape_info, self.shape_images[f"{player_desc["shape_name"]}Friendly"], self.shape_images[f"{player_desc["shape_name"]}Enemy"], self.bullets, self.bullet_img, player_desc["is_player"], player_desc["squad"], None, player_desc["player_name"]) for player_desc in query["player_set"]]
                            for player in self.players:
                                player.last_update = time()
                                player.squad = [self.get_player(squad_member) for squad_member in player.squad]

                        elif "player_index" in query:
                            js.console.log("Received player_index")
                            self.spectator_index = query["player_index"]
                            #self.spectating = True

                        if self.players == []:
                            self.client.send({"question": "player_set"})

                        if self.powerups != [] and self.players != [] and self.spectator_index != 0: done = True

            print(self.players, self.spectator_index)
            js.console.log("Received all starting info.")

            self.player.squad.append(self.player)
            self.starting_player = self.players[self.spectator_index]

        if self.server is not None:
            await asyncio.sleep(2) # Give clients time to catch up

        print("on")
        self.spectator_player = self.player
        starting_player = self.player
        while 1:
            await asyncio.sleep(0)

            if len(self.players) <= 1:
                if len(self.players) == 0:
                    print(f"Tie")
                    return
                else:
                    print(f"Winner: {self.players[0]}")
                    dt_mut *= 0.99
                    if self.end_screen is None:
                        self.end_screen = EndScreen(self.screen, self.starting_player, self.players[0])

                    if self.server is not None:
                        for client in self.server.clients:
                            await client.send({"answer": {"winner": self.player.to_winner_dict()}})

            dt = min((self.clock.tick(60) / 1000.0) * dt_mut, 1)
            dt_sum += dt

            if dt == 1:
                print("Slow server framerate")

            self.manager.update(dt / dt_mut)

            if self.client is not None:
                for message in self.client.base_client.data_stream:
                    for dtype, query in message.items():
                        if dtype != "answer":
                            continue

                        if "player_update" in query:
                            update = query["player_update"]
                            for player_update in update:
                                target_player = None
                                for player in self.players:
                                    if player.index == player_update["index"]:
                                        target_player = player
                                        break

                                if target_player is not None:
                                    for key, value in player_update.items():
                                        if key in ("x", "y", "rotation") and target_player == self.player and not self.spectating:
                                            continue

                                        setattr(target_player, key, value)

                                    target_player.last_update = time()

                        if "wall_update" in query:
                            update = query["wall_update"]
                            self.safezone.left_wall = update["left_wall"]
                            self.safezone.right_wall = update["right_wall"]
                            self.safezone.top_wall = update["top_wall"]
                            self.safezone.bottom_wall = update["bottom_wall"]

                        if "winner" in query:
                            update = query["winner"]
                            target_player = None
                            for player in self.players:
                                if player.index == update["index"]:
                                    target_player = player
                                    break
                            
                            if target_player is not None:
                                for key, value in update.items():
                                    setattr(target_player, key, value)

                                self.players = [target_player]

                        if "player_remove" in query:
                            target_player = None
                            for player in self.players:
                                if player.index == query["player_remove"]:
                                    target_player = player
                                    break
                            
                            if target_player is not None:
                                #if target_player.index < self.spectator_index:
                                #    self.spectator_index -= 1

                                self.players.remove(target_player)
                                self.dead_players.append(target_player)

                                self.eventfeed.add(GameEvent(f"{target_player.player_name} was killed.", (0, 0, 255) if target_player in starting_player.squad else (255, 0, 0)))

                        if "set_bullets" in query:
                            update = query["set_bullets"]
                            self.bullets = []
                            for bullet in update:
                                target_player = None
                                for player in self.players:
                                    if player.index == bullet["parent_index"]:
                                        target_player = player
                                        break

                                self.bullets.append(Bullet(target_player, bullet["x"], bullet["y"], bullet["velocity"], bullet["damage"], 1, 1, 1, 1, self.bullet_img))

                        if "powerup_add" in query:
                            powerup_desc = query["powerup_add"]

                            new_powerup = Powerup(
                                powerup_desc["x"], powerup_desc["y"], powerup_desc["rarity"], self.powerup_info, self.on_powerup_pickup, powerup_desc["index"], powerup_desc["name"]
                            )

                            self.powerups.append(new_powerup)

                            grid_square = self.powerup_grid[floor(new_powerup.y / self.POWERUP_SECTION_SIZE)][floor(new_powerup.x / self.POWERUP_SECTION_SIZE)]
                            grid_square.append(new_powerup)

                        if "powerup_remove" in query:
                            update = query["powerup_remove"]

                            target_powerup = None
                            for powerup in self.powerups:
                                if powerup.index == update["powerup_index"]:
                                    target_powerup = powerup
                                    break
                            
                            if target_powerup is not None:
                                grid_square = self.powerup_grid[floor(target_powerup.y / self.POWERUP_SECTION_SIZE)][floor(target_powerup.x / self.POWERUP_SECTION_SIZE)]
                                if target_powerup in grid_square:
                                    grid_square.remove(target_powerup)

                                if target_powerup in self.powerups:
                                    self.powerups.remove(target_powerup)

                        if "powerup_set" in query:
                            if query["powerup_set"]["stage"] == 1:
                                self.powerups = await self.generate_powerups(query["powerup_set"]["seed"])
                            else:
                                self.NUM_POWERUPS = self.NUM_POWERUP_SECTIONS * 10
                                self.powerups.extend(await self.generate_powerups(query["powerup_set"]["seed"], self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))

                        if "ping" in query:
                            self.ping = time() - query["ping"]

            elif self.server is not None:
                for client in self.server.clients:
                    for message in client.data_stream:
                        for dtype, query in message.items():
                            if dtype == "answer":
                                if "player_pos_update" in query:
                                    update = query["player_pos_update"]
                                    target_player = None
                                    for player in self.players:
                                        if player.index == update["index"]:
                                            target_player = player
                                            break

                                    if target_player is not None:
                                        for key, value in update.items():
                                            match key:
                                                case "vel": value = pg.Vector2(value[0], value[1])

                                            setattr(target_player, key, value)

                                elif "player_shoot" in query:
                                    target_player = None
                                    for player in self.players:
                                        if player.index == query["player_shoot"]["index"]:
                                            target_player = player
                                            break
                                    
                                    if target_player is not None:
                                        target_player.shoot()

                                elif "send_starting_info" in query:
                                    print("Sending starting info on random request.")
                                    player_data = [player.to_dict() for player in self.players]
                                    await client.send({"answer": {"powerup_set": {"seed": self.powerup_stage_1_seed, "stage": 1}}})
                                    await client.send({"answer": {"player_set": player_data}})
                                        #client.send({"answer": {"player_set": True}})
                                    await client.send({"answer": {"player_index": -1}})

                            else:
                                if "player_set" in query:
                                    player_data = [player.to_dict() for player in self.players]
                                    await client.send({"answer": {"player_set": player_data}})

                                elif "ping" in query:
                                    await client.send({"answer": {"ping": query["ping"]}})

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    if self.server is not None:
                        self.server.shutdown()
                    pg.quit()
                    sys.exit(0)

                if self.spectating:
                    if event.type == pg.MOUSEBUTTONDOWN:
                        if event.button == 3:
                            self.spectator_index -= 1
                            if self.spectator_index < 0:
                                self.spectator_index = len(self.players) - 1

                            self.spectator_player = self.player
                            
                        elif event.button == 1:
                            self.spectator_index = (self.spectator_index + 1) % len(self.players)
                            self.spectator_player = self.player

                if event.type == pg.KEYDOWN:
                    #if event.key in [pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN, pg.K_a, pg.K_d, pg.K_w, pg.K_s, pg.K_SPACE]:
                    #    if self.player.showing_powerup_popup:
                    #        self.player.showing_powerup_popup = False
                    if event.key == pg.K_RETURN:
                        if self.end_screen is not None:
                            await self.restart()
                            return

                if event.type == pg.FINGERUP:
                    if event.finger_id in self.active_fingers:
                        del self.active_fingers[event.finger_id]

                if event.type == pg.FINGERDOWN:
                    self.active_fingers[event.finger_id] = (event.x*self.WIDTH, event.y*self.HEIGHT)

                    if self.end_screen is not None:
                        await self.restart()
                        return

                if event.type == pg.FINGERMOTION:
                    self.active_fingers[event.finger_id] = (event.x*self.WIDTH, event.y*self.HEIGHT)

                self.manager.process_events(event)

            #fingermotion_events.append((pg.mouse.get_pos()[0], pg.mouse.get_pos()[1], 0))

            num_powerups = len(self.powerups)
            num_powerups_in_sec = 0
            for y in self.powerup_grid:
                num_powerups_in_sec += len(y)

            #print(num_powerups, num_powerups_in_sec)
            if self.spectator_player not in self.players:
                self.spectator_player = self.player

            self.spectator_index = self.players.index(self.spectator_player)

            self.anim_manager.update(dt)
            self.safezone.update(dt)

            self.screen.fill(self.BG_COLOR)

            gridline_spacing = 400
            shifted_player_x = int(self.player.x - self.player.x % gridline_spacing)
            for x in range(shifted_player_x, shifted_player_x + self.WIDTH + gridline_spacing, gridline_spacing):
                offset_x = (x - self.player.x)
                pg.draw.line(self.screen, (100, 100, 100), (offset_x, 0), (offset_x, self.HEIGHT), width=2)

            shifted_player_y = int(self.player.y - self.player.y % gridline_spacing)
            for y in range(shifted_player_y, shifted_player_y + self.HEIGHT + gridline_spacing, gridline_spacing):
                offset_y = (y - self.player.y)
                pg.draw.line(self.screen, (100, 100, 100), (0, offset_y), (self.WIDTH, offset_y), width=2)

            self.safezone.blit(self.screen, self.player)

            x_walls_dist = self.safezone.right_wall - self.safezone.left_wall
            y_walls_dist = self.safezone.bottom_wall - self.safezone.top_wall

            if x_walls_dist < self.MAP_SIZE / 1.66 and y_walls_dist < self.MAP_SIZE / 1.66 and not self.has_done_bonus_powerups and self.client is None:
                self.NUM_POWERUPS = self.NUM_POWERUP_SECTIONS * 10 # half
                self.powerups.extend(await self.generate_powerups(self.powerup_stage_2_seed, self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))
                self.has_done_bonus_powerups = True

                if self.server is not None:
                    for client in self.server.clients:
                        await client.send({"answer": {"powerup_set": {"seed": self.powerup_stage_2_seed, "stage": 2}}})

            keys = pg.key.get_pressed()

            if not self.spectating:
                key_movement = False
                if keys[pg.K_w]:
                    self.player.move_up(dt)
                    key_movement = True
                if keys[pg.K_d]:
                    self.player.move_right(dt)
                    key_movement = True
                if keys[pg.K_s]:
                    self.player.move_down(dt)
                    key_movement = True
                if keys[pg.K_a]:
                    self.player.move_left(dt)
                    key_movement = True

                if keys[pg.K_UP]: self.player.rotation = 0
                elif keys[pg.K_RIGHT]: self.player.rotation = 270
                elif keys[pg.K_DOWN]: self.player.rotation = 180
                elif keys[pg.K_LEFT]: self.player.rotation = 90

                mx, my = pg.mouse.get_pos()
                self.player.rotation = -degrees(atan2((self.HEIGHT / 2 - my), (self.WIDTH / 2 - mx))) + 90

                if (self.movement_joystick.joy_x != 0 or self.movement_joystick.joy_y != 0) and not key_movement:
                    self.player.move_right(self.movement_joystick.joy_x * dt)
                    self.player.move_down(self.movement_joystick.joy_y * dt)
                    self.player.rotation = -self.movement_joystick.joy_angle - 90

                if self.aim_joystick.joy_x != 0 or self.aim_joystick.joy_y != 0:
                    self.player.rotation = -self.aim_joystick.joy_angle - 90
                    #self.player.shoot()

                if self.client is not None:
                    if not self.spectating:
                        self.client.send({"answer": {"player_pos_update": {"x": self.player.x, "y": self.player.y, "rotation": self.player.rotation, "index": self.player.index, "vel": tuple(self.player.vel)}}})

                if keys[pg.K_SPACE] or pg.mouse.get_pressed()[0]:
                    if self.player.shoot():
                        self.sounds["laserShoot"].play()
                    
                    if self.client is not None:
                        if not self.spectating:
                            self.client.send({"answer": {"player_shoot": {"index": self.player.index}}})

                elif keys[pg.K_LSHIFT]:
                    if self.player.showing_powerup_popup:
                        self.player.showing_powerup_popup = False
                
            self.minimap_surf.fill((0, 0, 0))

            for powerup in self.powerups:
                powerup.draw(self.screen, self.player)
                self.minimap_surf.set_at((powerup.x / self.MAP_SIZE * 200, powerup.y / self.MAP_SIZE * 200), (255, 255, 255))

            dead_players = []

            for bullet in self.bullets:
                bullet.move(dt)

            for i, player in enumerate(self.players):
                if len(player.squad) == len(self.players):
                    # TODO: Verify this works
                    # FREE FOR ALL
                    for squad_member in player.squad:
                        if squad_member == player: continue
                        squad_member.squad = [squad_member]
                    
                    player.squad = [player]

                #player.shoot()
                player.update(dt)

                left_wall, right_wall, top_wall, bottom_wall = self.safezone.get_wall_distance(player)

                closest_bullet = None
                closest_dist = float('inf')
                close_bullets = []

                bullets_to_remove = []
                for bullet in self.bullets:
                    if player == self.player:
                        bullet.draw(self.screen, self.player)

                    bullet_dist = dist((bullet.x, bullet.y), (player.x, player.y))
                    #if bullet_dist < 2000:
                    #    close_bullets.append(bullet)
                    close_bullets.append(bullet)
                    
                    if bullet.parent in player.squad: continue

                    if player.global_rect.colliderect(bullet.rect):
                        if player == self.player:
                            self.sounds["hitHurt"].play()

                        if self.client is None:
                            damage = bullet.hit(player)
                            bullet.parent.shots_hit += 1
                            bullet.parent.total_damage += damage

                            if player.dead:
                                bullet.parent.kills += 1

                            bullets_to_remove.append(bullet)
                        
                    if bullet.distance_travelled > self.MAX_BULLET_TRAVEL_DIST and self.client is None:
                        bullets_to_remove.append(bullet)

                    if bullet not in bullets_to_remove:
                        if bullet_dist < closest_dist:
                            closest_dist = bullet_dist
                            closest_bullet = bullet

                for bullet in bullets_to_remove:
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)

                if self.server is not None:
                    if player.index != 0 and player.index <= len(self.server.clients):
                        await self.server.clients[player.index-1].send({"answer": {"set_bullets": [bullet.to_dict() for bullet in close_bullets]}})

                close_powerups = []
                closest_powerup = None
                closest_dist = float('inf')
                for y_offset in range(-1, 2):
                    y_tile = min(self.NUM_POWERUP_SECTIONS - 1, max(0, floor(player.y / self.POWERUP_SECTION_SIZE) + y_offset))
                    for x_offset in range(-1, 2):
                        x_tile = min(self.NUM_POWERUP_SECTIONS - 1, max(0, floor(player.x / self.POWERUP_SECTION_SIZE) + x_offset))
                        for powerup in self.powerup_grid[y_tile][x_tile]:
                            powerup_dist_x = abs(powerup.x - player.x)
                            powerup_dist_y = abs(powerup.y - player.y)
            
                            #powerup_dist = dist((powerup.x, powerup.y), (player.x, player.y))
                            powerup_dist = sqrt(powerup_dist_x ** 2 + powerup_dist_y ** 2)

                            if powerup_dist > 1000: continue

                            if powerup_dist <= player.rect.w:
                                if player == self.player:
                                    self.sounds["powerUp"].play()

                                if self.client is None or 1:
                                    self.powerup_grid[floor(powerup.y / self.POWERUP_SECTION_SIZE)][floor(powerup.x / self.POWERUP_SECTION_SIZE)].remove(powerup)
                                    
                                    if self.server is not None:
                                        for client in self.server.clients:
                                            await client.send({"answer": {"powerup_remove": {"powerup_index": powerup.index}}})

                                    powerup.pickup(player)
                            else:
                                close_powerups.append(powerup)

                            if powerup_dist < closest_dist:
                                closest_dist = powerup_dist
                                closest_powerup = powerup
                    
                if player == self.player and closest_powerup is not None:
                    ... # DEBUG STUFF
                    #pg.draw.circle(self.screen, (255, 255, 255), (closest_powerup.x - closest_powerup.image.width // 2 - (player.x - self.WIDTH // 2 + closest_powerup.image.width // 2), closest_powerup.y - closest_powerup.image.height // 2 - (player.y - self.HEIGHT // 2 + closest_powerup.image.height // 2)), 5)

                player.set_close_powerups(close_powerups)
                player.draw(self.screen, self.player, starting_player.squad)

                closest_player = None
                closest_dist = float('inf')
                close_players = []
                for other_player in self.players:
                    player_dist = dist((other_player.x, other_player.y), (player.x, player.y))
                    if player_dist < 2000:
                        close_players.append(other_player)

                    if other_player is player: continue

                    if player_dist < closest_dist:
                        closest_dist = player_dist
                        closest_player = other_player

                if not player.is_player:
                    left_wall += self.WIDTH / 2
                    right_wall -= self.WIDTH / 2
                    top_wall += self.WIDTH / 2
                    bottom_wall += self.WIDTH / 2

                    right_wall_dist = max(0, min(1, (player.x - self.safezone.left_wall + self.WIDTH / 2) / (self.safezone.right_wall - self.safezone.left_wall + 0.00000000000000000001)))
                    left_wall_dist = 1 - right_wall_dist
                    bottom_wall_dist = max(0, min(1, (player.y - self.safezone.top_wall + self.HEIGHT / 2) / (self.safezone.bottom_wall - self.safezone.top_wall + 0.00000000000000000001)))
                    top_wall_dist = 1 - bottom_wall_dist

                    danger = max(left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist)

                    if self.client is None:
                        if self.server is None:
                            player.ai_move(dt, (int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)), (left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist), closest_powerup, closest_player, closest_bullet)
                        else:
                            if player.index > len(self.server.clients):
                                player.ai_move(dt, (int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)), (left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist), closest_powerup, closest_player, closest_bullet)

                if player.dead and self.client is None:
                    dead_players.append(player)
                    self.eventfeed.add(GameEvent(f"{player.player_name} was killed.", (0, 0, 255) if player in starting_player.squad else (255, 0, 0)))

                if self.client is not None:
                    if time() - self.last_ping > 1:
                        self.client.send({"question": {"ping": time()}})
                        self.last_ping = time()

                    if time() - player.last_update > 3:
                        if len(self.eventfeed.event_queue) < 10:
                            self.eventfeed.add(GameEvent("Slow connection!", pg.Color(255, 150, 0)))
                        #player.x = -1000

            for dead_player in dead_players:
                if len(self.players) == 1: continue

                if dead_player == self.player:
                    self.spectating = True

                for rarity, powerup_info, on_pickup in dead_player.collected_powerups:
                    new_powerup = Powerup(min(self.MAP_SIZE_X - 1, max(0, dead_player.x + randint(-50, 50))), min(self.MAP_SIZE_Y-1, max(0, dead_player.y + randint(-50, 50))), rarity, powerup_info, on_pickup, len(self.powerups))
                    self.powerups.append(new_powerup)
                    self.powerup_grid[floor(new_powerup.y / self.POWERUP_SECTION_SIZE)][floor(new_powerup.x / self.POWERUP_SECTION_SIZE)].append(new_powerup)

                    if self.server is not None:
                        for client in self.server.clients:
                            await client.send({"answer": {"powerup_add": new_powerup.to_dict()}})

                if self.server is not None:
                    for client in self.server.clients:
                        await client.send({"answer": {"player_remove": dead_player.index}})

                self.players.remove(dead_player)
                
                #if self.spectating and dead_player.index < self.player.index:
                #    self.spectator_index -= 1

                self.dead_players.append(dead_player)

            if self.server is not None:
                game_player_info = {"answer": {"player_update": [game_player.to_full_dict() for game_player in self.players]}}
                wall_info =  {"answer": {"wall_update": {"left_wall": self.safezone.left_wall, "right_wall": self.safezone.right_wall, "top_wall": self.safezone.top_wall, "bottom_wall": self.safezone.bottom_wall}}}
                for client in self.server.clients:
                    await client.send(game_player_info)
                    await client.send(wall_info)

            if self.starting_player.index != self.player.index:
                self.spectating = True

            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, 0, (self.safezone.left_wall - self.WIDTH / 2) / self.MAP_SIZE * 200, 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), ((self.safezone.right_wall) / self.MAP_SIZE * 200, 0, 200, 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, 0, 200, (self.safezone.top_wall - self.HEIGHT / 2) / self.MAP_SIZE * 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, (self.safezone.bottom_wall + self.HEIGHT / 2) / self.MAP_SIZE * 200, 200, 200))

            pg.draw.rect(self.minimap_surf, (0, 0, 255), (self.player.x / self.MAP_SIZE * 200 - 3, self.player.y / self.MAP_SIZE * 200 - 3, 6, 6))

            for friendly in self.player.squad:
                if friendly == self.player: continue
                pg.draw.rect(self.minimap_surf, (0, 255, 0), (friendly.x / self.MAP_SIZE * 200 - 2, friendly.y / self.MAP_SIZE * 200 - 2, 4, 4))

            pg.draw.rect(self.screen, (255, 255, 255), (self.WIDTH - 252, 48, 204, 204), width=2)
            self.screen.blit(self.minimap_surf, (self.WIDTH - 250, 50))

            fingermotion_list = [(x, y, finger_id) for finger_id, (x, y) in self.active_fingers.items()]
            self.movement_joystick.draw(fingermotion_list)
            self.aim_joystick.draw(fingermotion_list)

            if self.spectating:
                self.screen.blit(self.spectating_lbl, (self.WIDTH / 2 - self.spectating_lbl.width / 2, 50))

            fps_lbl = self.fps_font.render(f"{self.clock.get_fps():.2f}", True, (255, 255, 255))
            alive_lbl = self.fps_font.render(f"{len(self.players)} alive", True, (255, 255, 255))
            ping_lbl = self.fps_font.render(f"{int(self.ping*1000)}ms", True, (255*min(self.ping, 1), 255*min(1/(self.ping + 0.00000000000001), 1), 0))
            self.screen.blit(fps_lbl, (self.WIDTH - fps_lbl.width - 10, 10))
            self.screen.blit(alive_lbl, (self.WIDTH - 50 - alive_lbl.width, 260))
            self.screen.blit(ping_lbl, (self.WIDTH - 50 - ping_lbl.width, 280))

            self.powerup_section_index += 1
            if self.powerup_section_index >= self.NUM_POWERUP_SECTIONS: self.powerup_section_index = 0

            #self.spectator_index = min(self.spectator_index, max(0, len(self.players)-1))
            #if self.spectator_index < 0:
            #    self.spectator_index = 0

            #self.spectator_player = self.player

            if self.end_screen is not None and dt_mut < 0.10:
                if self.server is not None:
                    #self.server.shutdown()
                    print("Closing server...")
                    self.server.server.close()
                    await self.server.server.wait_closed()
                    self.server_task.cancel()
                    print("Server closed.")
                    self.dead_server = self.server
                    self.server = None

                    if self.auto_start:
                        return

                elif self.client is not None:
                    self.client.allow_reconnect = False
                    self.connect_task.cancel()

                self.end_screen.draw()
 
                if not hasattr(self, "leaderboard"):
                    all_players = [player for player in self.players]
                    all_players.extend(list(reversed(self.dead_players)))
                    self.leaderboard = Leaderboard(self.screen, self.manager, [self.player_lb_info(player) for player in all_players])
                else:
                    if self.leaderboard is None:
                        all_players = [player for player in self.players]
                        all_players.extend(list(reversed(self.dead_players)))
                        self.leaderboard = Leaderboard(self.screen, self.manager, [self.player_lb_info(player) for player in all_players])

                # Disable leaderboard because its annoying
                self.leaderboard = None

            self.eventfeed.update(dt)
            self.manager.draw_ui(self.screen)

            pg.display.flip()

async def main():
    display_surf = None
    while 1:
        sr = ShapeRoyale(display_surf)
        await sr.run()
        display_surf = sr.screen
        if not sr.auto_start:
            break

if __name__ == "__main__":
    asyncio.run(main())