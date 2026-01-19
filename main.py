import pygame as pg
import os
import sys

#from sound import generate_sine_wave

from menus import MainMenu, EndScreen
from bullet import Bullet
from shape import Player, Shape
from powerups import Powerup
from utils import AnimManager, FONTS_PATH

from networking import Server, Client, BaseClient

from time import time, sleep
from json import loads
from math import dist, sqrt, floor, ceil
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
    SPEED = 50

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
            player.add_poison(None, 100 * self.dt, 0.0, 2.0)
            player.take_damage(50 * self.dt / player.zone_resistance)

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
    WIDTH: int = PYGAME_INFO.current_w
    HEIGHT: int = PYGAME_INFO.current_h

    MAP_SIZE = 30_000
    MAP_SIZE_X = MAP_SIZE
    MAP_SIZE_Y = MAP_SIZE

    NUM_PHASES = 4
    NUM_PLAYERS = 100
    NUM_POWERUP_SECTIONS = 24 
    NUM_POWERUPS = NUM_POWERUP_SECTIONS * 20 # this must be divisible by the NUM_POWERUP_SECTIONS
    POWERUP_SECTION_SIZE = MAP_SIZE / NUM_POWERUP_SECTIONS

    MAX_BULLET_TRAVEL_DIST = 2000

    def __init__(self, display_surf: pg.Surface | None = None) -> None:
        if not (self.NUM_POWERUPS / self.NUM_POWERUP_SECTIONS).is_integer() or self.NUM_POWERUPS % self.NUM_POWERUP_SECTIONS != 0:
            raise Exception("NUM_POWERUPS must be divisible by NUM_POWERUP_SECTIONS such that the resualt is a valid integer!")

        info = pg.display.get_desktop_sizes()[0]
        self.WIDTH = info[0]
        self.HEIGHT = info[1]
        
        if display_surf is None:
            self.screen = pg.display.set_mode((self.WIDTH, self.HEIGHT), pg.SRCALPHA | pg.FULLSCREEN, display=0)
        else:
            self.screen = display_surf

        self.anim_manager = AnimManager()

        self.server = None
        self.client = None
        self.player_name = "player"

        if len(sys.argv) > 1:
            if sys.argv[1] == "host":
                self.host_server()
            elif sys.argv[1] == "join":
                self.join_server()

        if len(sys.argv) == 4 and (self.client is not None or self.server is not None):
            self.player_name = sys.argv[3]

        self.main_menu = MainMenu(self.screen, self.server, self.client, self.player_name)

        real_player_info = [(self.main_menu.player.shape_index, self.player_name, None)]

        if self.server is not None:
            while len(real_player_info)-1 != len(self.server.clients):
                for client in self.server.clients:
                    for message in client.data_stream:
                        for dtype, query in message.items():
                            if dtype != "answer" or "send_starting_info" not in query:
                                continue
                            
                            real_player_info.append((query["send_starting_info"]["shape_index"], query["send_starting_info"]["name"], client))

        self.clock = pg.time.Clock()

        self.bullet_img = pg.transform.smoothscale(pg.image.load("../ShapeRoyale/Data/assets/Bullet_Sprite.png").convert_alpha(), (10, 10))

        self.generate_safezone_phases(self.NUM_PHASES)
        self.safezone = Safezone(self.screen.width, self.screen.height, self.MAP_SIZE_X, self.MAP_SIZE_Y, self.phase_config)

        self.shape_names = ["Square", "Triangle", "Circle"]
        self.shape_images = {
            "SquareFriendly": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Square_Sprite_Player.png"), 0.1).convert_alpha(),
            "SquareEnemy": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Square_Sprite_Enemy.png"), 0.1).convert_alpha(),
            "TriangleFriendly": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Triangle_Sprite_Player.png"), 0.1).convert_alpha(),
            "TriangleEnemy": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Triangle_Sprite_Enemy.png"), 0.1).convert_alpha(),
            "CircleFriendly": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Circle_Sprite_Player.png"), 0.1).convert_alpha(),
            "CircleEnemy": pg.transform.smoothscale_by(pg.image.load("../ShapeRoyale/Data/assets/Circle_Sprite_Enemy.png"), 0.1).convert_alpha()
        }
        
        with open("../ShapeRoyale/Data/shapes.json", "r") as f:
            self.shape_info = loads(f.read())

        with open("../ShapeRoyale/Data/powerups.json", "r") as f:
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
            self.powerups = self.generate_powerups(self.powerup_stage_1_seed)

        self.sounds = {
            "hitHurt": pg.Sound("../ShapeRoyale/Data/assets/Sounds/hitHurt.wav"),
            "laserShoot": pg.Sound("../ShapeRoyale/Data/assets/Sounds/laserShoot.wav"),
            "powerUp": pg.Sound("../ShapeRoyale/Data/assets/Sounds/powerUp.wav"),
        }
        self.sounds["hitHurt"].set_volume(0.70)
        self.sounds["laserShoot"].set_volume(0.70)
        self.sounds["powerUp"].set_volume(0.70)

        self.powerup_sections = [(i*self.POWERUP_SECTION_SIZE, (i+1)*self.POWERUP_SECTION_SIZE) for i in range(self.NUM_POWERUP_SECTIONS)]
        self.powerup_section_index = 0

        self.fps_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 15)
        self.spectating_lbl = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 60).render("You are spectating!", True, (255, 255, 255))

        self.spectator_index = 0
        self.spectating = False
        
        if len(self.players) > 0:
            self.player.is_player = not self.spectating
            self.starting_player = self.players[0]

        self.minimap_surf = pg.Surface((200, 200), pg.SRCALPHA)

        self.end_screen = None
        self.has_done_bonus_powerups = False

        self.main()
    
    @property
    def player(self) -> Player:
        try:
            return self.players[self.spectator_index]
        except:
            return self.players[0]

    def host_server(self) -> None:
        self.server = Server(sys.argv[2], int(sys.argv[3]))

    def join_server(self) -> None:
        self.screen.fill((0, 0, 0))
        loading_lbl = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 60).render("Connecting to server...", True, (255, 255, 255))
        self.screen.blit(loading_lbl, (self.WIDTH // 2 - loading_lbl.width // 2, self.HEIGHT // 2 - loading_lbl.height // 2))

        self.client = Client(sys.argv[2], int(sys.argv[3]))
        connected = False
        while not connected:
            pg.display.flip()

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit(0)

            connected = self.client.connect(max_retries=1)

        self.player_name = sys.argv[4]

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

        for i, (shape_index, name, client) in enumerate(real_player_info):
            print(shape_index, name, client)
            shape_type = self.shape_names[shape_index]
            new_shape = Shape(
                self.MAP_SIZE, randint(3000, self.MAP_SIZE_X-3000), randint(3000, self.MAP_SIZE_Y-3000), i, shape_type, self.shape_info, self.shape_images[f"{shape_type}Friendly"],
                self.shape_images[f"{shape_type}Enemy"], self.bullets, self.bullet_img, True, [], client, name
            )
            new_shape.squad.append(new_shape)
            shapes.append(new_shape)

        for i in range(len(shapes), self.NUM_PLAYERS):
            name = choice(self.shape_names)
            new_shape = Shape(
                self.MAP_SIZE, randint(3000, self.MAP_SIZE_X-3000), randint(3000, self.MAP_SIZE_Y-3000), i, name, self.shape_info, self.shape_images[f"{name}Friendly"],
                self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, is_player=False, squad=[], player_name=f"Bot {i+1}"
            )
            new_shape.squad.append(new_shape)
            shapes.append(new_shape)

        return shapes

    def generate_powerups(self, seed: int, starting_index: int = 0, spawn_min_x: float = 0, spawn_max_x: float = MAP_SIZE-1, spawn_min_y: float = 0, spawn_max_y: float = MAP_SIZE-1) -> List[Powerup]:
        powerups = []

        common_rarity_max = self.powerup_info["Common"]["spawn_chance"]
        uncommon_rarity_max = self.powerup_info["Uncommon"]["spawn_chance"]
        rare_rarity_max = self.powerup_info["Rare"]["spawn_chance"]
        legendary_rarity_max = self.powerup_info["Legendary"]["spawn_chance"]

        rng = Random(seed)

        for i in range(self.NUM_POWERUPS):
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

    def main(self) -> None:
        dt_mut = 1
        dt_sum = 0

        if self.server is not None:
            player_data = [player.to_dict() for player in self.players]
            for i, client in enumerate(self.server.clients):
                client.send({"answer": {"powerup_set": {"seed": self.powerup_stage_1_seed, "stage": 1}}})
                client.send({"answer": {"player_set": player_data}})
                    #client.send({"answer": {"player_set": True}})
                client.send({"answer": {"player_index": i+1}})

        if self.client is not None:
            done = False
            while not done:
                for message in self.client.base_client.data_stream:
                    for dtype, query in message.items():
                        if dtype != "answer":
                            continue

                        if "powerup_set" in query:
                            if query["powerup_set"]["stage"] == 1:
                                self.powerups = self.generate_powerups(query["powerup_set"]["seed"])
                            else:
                                self.powerups.extend(self.generate_powerups(query["powerup_set"]["seed"], self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))

                        elif "player_set" in query:
                            self.players = [Shape(self.MAP_SIZE, player_desc["x"], player_desc["y"], player_desc["index"], player_desc["shape_name"], self.shape_info, self.shape_images[f"{player_desc["shape_name"]}Friendly"], self.shape_images[f"{player_desc["shape_name"]}Enemy"], self.bullets, self.bullet_img, player_desc["is_player"], player_desc["squad"], None, player_desc["player_name"]) for player_desc in query["player_set"]]
                            for player in self.players:
                                player.last_update = time()

                        elif "player_index" in query:
                            self.spectator_index = query["player_index"]
                            #self.spectating = True

                        if self.players == []:
                            self.client.send({"question": "player_set"})

                        if self.powerups != [] and self.players != [] and self.spectator_index != 0: done = True
                
            self.player.squad.append(self.player)
            self.starting_player = self.players[self.spectator_index]

        while 1:
            if len(self.players) <= 1:
                if len(self.players) == 0:
                    print(f"Tie")
                    return
                else:
                    print(f"Winner: {self.players[0]}")
                    dt_mut *= 0.99
                    self.end_screen = EndScreen(self.screen, self.starting_player, self.players[0])

                    if self.server is not None:
                        for client in self.server.clients:
                            client.send({"answer": {"winner": self.player.to_winner_dict()}})

            dt = (self.clock.tick(60) / 1000.0) * dt_mut
            dt_sum += dt

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

                        if "player_remove" in query:
                            target_player = None
                            for player in self.players:
                                if player.index == query["player_remove"]:
                                    target_player = player
                                    break
                            
                            if target_player is not None:
                                if target_player.index < self.spectator_index:
                                    self.spectator_index -= 1

                                self.players.remove(target_player)

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
                                self.powerups = self.generate_powerups(query["powerup_set"]["seed"])
                            else:
                                self.NUM_POWERUPS = self.NUM_POWERUP_SECTIONS * 10
                                self.powerups.extend(self.generate_powerups(query["powerup_set"]["seed"], self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))

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
                                            setattr(target_player, key, value)

                                elif "player_shoot" in query:
                                    target_player = None
                                    for player in self.players:
                                        if player.index == query["player_shoot"]["index"]:
                                            target_player = player
                                            break
                                    
                                    if target_player is not None:
                                        target_player.shoot()

                            else:
                                if "player_set" in query:
                                    player_data = [player.to_dict() for player in self.players]
                                    client.send({"answer": {"player_set": player_data}})

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit(0)

                if self.spectating:
                    if event.type == pg.MOUSEBUTTONDOWN:
                        if event.button == 3:
                            self.spectator_index -= 1
                            if self.spectator_index < 0:
                                self.spectator_index = len(self.players) - 1

                        elif event.button == 1:
                            self.spectator_index = (self.spectator_index + 1) % len(self.players)

                if event.type == pg.KEYDOWN:
                    #if event.key in [pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN, pg.K_a, pg.K_d, pg.K_w, pg.K_s, pg.K_SPACE]:
                    #    if self.player.showing_powerup_popup:
                    #        self.player.showing_powerup_popup = False
                    if event.key == pg.K_RETURN:
                        if self.end_screen is not None:
                            self.__init__(self.screen)

            num_powerups = len(self.powerups)
            num_powerups_in_sec = 0
            for y in self.powerup_grid:
                num_powerups_in_sec += len(y)

            #print(num_powerups, num_powerups_in_sec)

            self.anim_manager.update(dt)
            self.safezone.update(dt)

            self.screen.fill((0, 0, 0))
            self.safezone.blit(self.screen, self.player)

            x_walls_dist = self.safezone.right_wall - self.safezone.left_wall
            y_walls_dist = self.safezone.bottom_wall - self.safezone.top_wall

            if x_walls_dist < self.MAP_SIZE / 1.66 and y_walls_dist < self.MAP_SIZE / 1.66 and not self.has_done_bonus_powerups and self.client is None:
                self.NUM_POWERUPS = self.NUM_POWERUP_SECTIONS * 10 # half
                self.powerups.extend(self.generate_powerups(self.powerup_stage_2_seed, self.NUM_POWERUPS, int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))
                self.has_done_bonus_powerups = True

                if self.server is not None:
                    for client in self.server.clients:
                        client.send({"answer": {"powerup_set": {"seed": self.powerup_stage_2_seed, "stage": 2}}})

            keys = pg.key.get_pressed()

            if not self.spectating:
                if keys[pg.K_UP] or keys[pg.K_w]: self.player.move_up(dt)
                elif keys[pg.K_RIGHT] or keys[pg.K_d]: self.player.move_right(dt)
                elif keys[pg.K_DOWN] or keys[pg.K_s]: self.player.move_down(dt)
                elif keys[pg.K_LEFT] or keys[pg.K_a]: self.player.move_left(dt)

                if self.client is not None:
                    if not self.spectating:
                        self.client.send({"answer": {"player_pos_update": {"x": self.player.x, "y": self.player.y, "rotation": self.player.rotation, "index": self.player.index}}})

                if keys[pg.K_SPACE]:
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
                    if bullet_dist < 2000:
                        close_bullets.append(bullet)
                    
                    if bullet.parent == player: continue

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
                        self.server.clients[player.index-1].send({"answer": {"set_bullets": [bullet.to_dict() for bullet in close_bullets]}})

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
                                            client.send({"answer": {"powerup_remove": {"powerup_index": powerup.index}}})

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
                player.draw(self.screen, self.player)

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

                if self.server is not None:
                    if player.index != 0 and player.index <= len(self.server.clients):
                        self.server.clients[player.index-1].send({"answer": {"player_update": [player.to_full_dict() for player in self.players]}})

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

                if self.client is not None:
                    if time() - player.last_update > 3:
                        player.x = -1000

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
                            client.send({"answer": {"powerup_add": new_powerup.to_dict()}})

                if self.server is not None:
                    for client in self.server.clients:
                        client.send({"answer": {"player_remove": dead_player.index}})

                self.players.remove(dead_player)
                
                if self.spectating and dead_player.index < self.player.index:
                    self.spectator_index -= 1

                self.dead_players.append(dead_player)

            if self.starting_player.index != self.player.index:
                self.spectating = True

            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, 0, (self.safezone.left_wall - self.WIDTH / 2) / self.MAP_SIZE * 200, 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), ((self.safezone.right_wall) / self.MAP_SIZE * 200, 0, 200, 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, 0, 200, (self.safezone.top_wall - self.HEIGHT / 2) / self.MAP_SIZE * 200))
            pg.draw.rect(self.minimap_surf, (255, 0, 0), (0, (self.safezone.bottom_wall + self.HEIGHT / 2) / self.MAP_SIZE * 200, 200, 200))

            pg.draw.rect(self.minimap_surf, (0, 0, 255), (self.player.x / self.MAP_SIZE * 200 - 1, self.player.y / self.MAP_SIZE * 200 - 1, 2, 2))

            pg.draw.rect(self.screen, (255, 255, 255), (self.WIDTH - 252, 48, 204, 204), width=2)
            self.screen.blit(self.minimap_surf, (self.WIDTH - 250, 50))

            if self.spectating:
                self.screen.blit(self.spectating_lbl, (self.WIDTH / 2 - self.spectating_lbl.width / 2, 50))

            self.screen.blit(self.fps_font.render(f"{self.clock.get_fps():.2f}", True, (255, 255, 255)), (20, 20))
            self.screen.blit(self.fps_font.render(f"{self.spectator_index+1}/{len(self.players)}", True, (255, 255, 255)), (20, 40))

            self.powerup_section_index += 1
            if self.powerup_section_index >= self.NUM_POWERUP_SECTIONS: self.powerup_section_index = 0

            self.spectator_index = min(self.spectator_index, max(0, len(self.players)-1))
            if self.spectator_index < 0:
                self.spectator_index = 0

            if self.end_screen is not None and dt_mut < 0.10:
                self.end_screen.draw()

            pg.display.flip()

if __name__ == "__main__":
    ShapeRoyale()