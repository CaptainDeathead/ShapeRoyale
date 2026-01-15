import pygame as pg
import os

from sound import generate_sine_wave

from shape import Player, Shape
from powerups import Powerup
from utils import AnimManager, FONTS_PATH

from time import time
from json import loads
from math import dist, sqrt, floor, ceil
from random import randint, choice, uniform

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

class MainMenu:
    TIMER_LENGTH = 1

    def __init__(self, display_surf: pg.Surface) -> None:
        self.display_surf = display_surf

        self.clock = pg.time.Clock()

        self.player = Player()

        self.width = display_surf.width
        self.height = display_surf.height

        self.fonts = {
            "small": pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 16),
            "medium": pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 32),
            "large": pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 40)
        }

        self.title_lbl = self.fonts["large"].render("Shape Royale", True, (255, 255, 255))

        self.info_lbl = self.fonts["medium"].render   ("Press Enter to ready / unready...", True, (255, 255, 255))
        self.info_lbl.blit(self.fonts["medium"].render("      Enter", True, (0, 255, 0)))

        self.timer_active = False
        self.timer_start_time = time()
        self.start_game = False
        self.last_timer_time = 0
        self.timer_first_beep = True

        self.timer_start_lbl = self.fonts["medium"].render("Game starting in  ...", True, (255, 255, 255))
        self.timer_end_lbls = [self.fonts["medium"].render(f"                 {i}", True, (0, 0, 255)) for i in range(1, self.TIMER_LENGTH + 1)]

        self.shape_images = [
            pg.image.load("../ShapeRoyale/Data/assets/Square_Sprite_Player.png").convert_alpha(),
            pg.image.load("../ShapeRoyale/Data/assets/Triangle_Sprite_Player.png").convert_alpha(),
            pg.image.load("../ShapeRoyale/Data/assets/Circle_Sprite_Player.png").convert_alpha()
        ]

        self.shape_names = ("Square", "Triangle", "Circle")

        with open("../ShapeRoyale/Data/shapes.json", "r") as f:
            self.shape_info = loads(f.read())

        self.main()

    def reset_timer(self) -> None:
        self.timer_active = False
        self.timer_start_time = time()
        self.timer_first_beep = True

    def check_game_start(self) -> None:
        if not self.player.ready:
            self.reset_timer()
            return
            
        timer_time = self.TIMER_LENGTH - (time() - self.timer_start_time)
        self.timer_active = True

        if timer_time <= 1:
            self.start_game = True

    def draw_player_cards(self) -> None:
        card_w = 350
        card_h = 500
        pad_w = 50

        cards_w = card_w * 3 + pad_w * 2
        start_x = self.width // 2 - cards_w // 2

        card_y = 350

        ready_line_w = 120

        x = start_x + (card_w + pad_w)

        name_lbl = self.fonts["medium"].render(f"Player 1", True, (255, 255, 255))
        self.display_surf.blit(name_lbl, (x + card_w // 2 - name_lbl.width // 2, card_y - 70))

        pg.draw.line(self.display_surf, self.player.ready_color, (x + card_w // 2 - ready_line_w // 2, card_y - 20), (x + card_w // 2 + ready_line_w // 2, card_y - 20), 5)

        player_rect = pg.Rect(x, card_y, card_w, card_h)
        pg.draw.rect(self.display_surf, (150, 150, 150), player_rect, border_radius = 20)

        selected_shape = self.shape_names[self.player.shape_index]
        shape_name_lbl = self.fonts["small"].render(f"Shape: {selected_shape}", True, (255, 255, 255))
        shape_class_lbl = self.fonts["small"].render(f"Class: {self.shape_info[selected_shape]['class']}", True, (255, 255, 255))

        curr_y = card_y + 20

        self.display_surf.blit(shape_name_lbl, (x + card_w // 2 - shape_name_lbl.width // 2, curr_y))
        curr_y += shape_name_lbl.height + 5

        self.display_surf.blit(shape_class_lbl, (x + card_w // 2 - shape_class_lbl.width // 2, curr_y))
        curr_y += shape_class_lbl.height + 20

        shape_image = pg.transform.smoothscale_by(self.shape_images[self.player.shape_index], 0.2)
        self.display_surf.blit(shape_image, (x + card_w // 2 - shape_image.width // 2, curr_y))
        curr_y += shape_image.height + 20

        shape_hp = self.shape_info[selected_shape]["hp"]
        shape_hp_regen = self.shape_info[selected_shape]["health_regen"]
        shape_shield = self.shape_info[selected_shape]["shield"]
        shape_shield_regen = self.shape_info[selected_shape]["shield_regen"]
        shape_firerate = self.shape_info[selected_shape]["firerate"]
        shape_dmg = self.shape_info[selected_shape]["damage"]
        shape_speed = self.shape_info[selected_shape]["speed"]
        shape_penetration = self.shape_info[selected_shape]["penetration"] * 100 - 100

        shape_info_lbls = [
            self.fonts["small"].render(f"Health: {shape_hp}HP", True, (255, 255, 255)),
            self.fonts["small"].render(f"Health regen: {shape_hp_regen}HP/s", True, (255, 255, 255)),
            self.fonts["small"].render(f"Shield: {shape_shield}HP", True, (255, 255, 255)),
            self.fonts["small"].render(f"Shield regen: {shape_shield_regen}HP/s", True, (255, 255, 255)),
            self.fonts["small"].render(f"Rate of fire: {shape_firerate}/s", True, (255, 255, 255)),
            self.fonts["small"].render(f"Damage: {shape_dmg}HP", True, (255, 255, 255)),
            self.fonts["small"].render(f"Speed: {shape_speed}u/s", True, (255, 255, 255)),
            self.fonts["small"].render(f"Penetration: {shape_penetration:.1f}%", True, (255, 255, 255)),
        ]

        largest_width = shape_info_lbls[3].width

        for shape_info_lbl in shape_info_lbls:
            self.display_surf.blit(shape_info_lbl, (x + card_w // 2 - largest_width // 2, curr_y))
            curr_y += shape_info_lbl.height + 5

    def main(self) -> None:
        while not self.start_game:
            self.display_surf.fill((0, 0, 0))
            self.clock.tick(60)

            for event in pg.event.get():
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_RETURN:
                        self.player.ready = not self.player.ready
                    elif event.key == pg.K_LEFT:
                        self.player.shape_index -= 1
                        if self.player.shape_index < 0:
                            self.player.shape_index = 2
                    elif event.key == pg.K_RIGHT:
                        self.player.shape_index += 1
                        if self.player.shape_index > 2:
                            self.player.shape_index = 0

            self.draw_player_cards()

            self.display_surf.blit(self.title_lbl, (self.width // 2 - self.title_lbl.width // 2, 100))

            if self.timer_active:
                timer_time = self.TIMER_LENGTH - (time() - self.timer_start_time)

                if self.last_timer_time != int(round(timer_time, 0)):
                    if self.timer_first_beep:
                        self.timer_first_beep = False
                    else:
                        generate_sine_wave(800, 0.2, volume=0.15).play()

                    self.last_timer_time = int(round(timer_time, 0))

                curr_time_int = max(0, min(int(round(timer_time, 0)), len(self.timer_end_lbls) - 1))
                self.display_surf.blit(self.timer_start_lbl, (self.width // 2 - self.timer_start_lbl.width // 2, self.height - 150))
                self.display_surf.blit(self.timer_end_lbls[curr_time_int-1], (self.width // 2 - self.timer_start_lbl.width // 2, self.height - 150))
            else:
                self.display_surf.blit(self.info_lbl, (self.width // 2 - self.info_lbl.width // 2, self.height - 150))

            self.check_game_start()

            pg.display.flip()

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

    def __init__(self) -> None:
        if not (self.NUM_POWERUPS / self.NUM_POWERUP_SECTIONS).is_integer() or self.NUM_POWERUPS % self.NUM_POWERUP_SECTIONS != 0:
            raise Exception("NUM_POWERUPS must be divisible by NUM_POWERUP_SECTIONS such that the resualt is a valid integer!")

        info = pg.display.get_desktop_sizes()[0]
        self.WIDTH = info[0]
        self.HEIGHT = info[1]
        self.screen = pg.display.set_mode((self.WIDTH, self.HEIGHT), pg.SRCALPHA | pg.FULLSCREEN, display=0)

        self.anim_manager = AnimManager()

        self.main_menu = MainMenu(self.screen)

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
        self.players = self.generate_players()
        self.powerups = self.generate_powerups()

        self.sounds = {
            "hitHurt": pg.Sound("../ShapeRoyale/Data/assets/Sounds/hitHurt.wav"),
            "laserShoot": pg.Sound("../ShapeRoyale/Data/assets/Sounds/laserShoot.wav"),
            "powerUp": pg.Sound("../ShapeRoyale/Data/assets/Sounds/powerUp.wav"),
        }
        self.sounds["hitHurt"].set_volume(0.75)
        self.sounds["laserShoot"].set_volume(0.75)
        self.sounds["powerUp"].set_volume(0.75)

        self.powerup_sections = [(i*self.POWERUP_SECTION_SIZE, (i+1)*self.POWERUP_SECTION_SIZE) for i in range(self.NUM_POWERUP_SECTIONS)]
        self.powerup_section_index = 0

        self.fps_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 15)
        self.spectating_lbl = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 60).render("You are spectating!", True, (255, 255, 255))

        self.spectator_index = 0
        self.spectating = False
        self.player.is_player = not self.spectating

        self.minimap_surf = pg.Surface((200, 200), pg.SRCALPHA)

        self.starting_player = self.players[0]
        self.end_screen = None
        self.has_done_bonus_powerups = False

        self.main()
    
    @property
    def player(self) -> Player:
        try:
            return self.players[self.spectator_index]
        except:
            return self.players[0]

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

    def generate_players(self) -> List[Shape]:
        shapes = []

        name = self.shape_names[self.main_menu.player.shape_index]
        new_shape = Shape(
            self.MAP_SIZE, randint(1000, self.MAP_SIZE_X-1000), randint(1000, self.MAP_SIZE_Y-1000), self.main_menu.player.shape_index, name, self.shape_info, self.shape_images[f"{name}Friendly"],
            self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, True, []
        )
        new_shape.squad.append(new_shape)
        shapes.append(new_shape)

        for i in range(self.NUM_PLAYERS - 1):
            name = choice(self.shape_names)
            new_shape = Shape(
                self.MAP_SIZE, randint(1000, self.MAP_SIZE_X-1000), randint(1000, self.MAP_SIZE_Y-1000), i+1, name, self.shape_info, self.shape_images[f"{name}Friendly"],
                self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, is_player=False, squad=[]
            )
            new_shape.squad.append(new_shape)
            shapes.append(new_shape)

        return shapes

    def generate_powerups(self, spawn_min_x: float = 0, spawn_max_x: float = MAP_SIZE-1, spawn_min_y: float = 0, spawn_max_y: float = MAP_SIZE-1) -> List[Powerup]:
        powerups = []

        common_rarity_max = self.powerup_info["Common"]["spawn_chance"]
        uncommon_rarity_max = self.powerup_info["Uncommon"]["spawn_chance"]
        rare_rarity_max = self.powerup_info["Rare"]["spawn_chance"]
        legendary_rarity_max = self.powerup_info["Legendary"]["spawn_chance"]

        for i in range(self.NUM_POWERUPS):
            rarity_number = uniform(0.0, 1.0)

            if rarity_number <= legendary_rarity_max: rarity = "Legendary"
            elif rarity_number <= legendary_rarity_max + rare_rarity_max: rarity = "Rare"
            elif rarity_number <= legendary_rarity_max + rare_rarity_max + uncommon_rarity_max: rarity = "Uncommon"
            else: rarity = "Common"

            powerup = Powerup(randint(spawn_min_x, spawn_max_x), randint(spawn_min_y, spawn_max_y), rarity, self.powerup_info, self.on_powerup_pickup)
            powerups.append(powerup)
            self.powerup_grid[floor(powerup.y / self.POWERUP_SECTION_SIZE)][floor(powerup.x / self.POWERUP_SECTION_SIZE)].append(powerup)

        return powerups

    def on_powerup_pickup(self, powerup: Powerup) -> None:
        self.powerups.remove(powerup)

    def main(self) -> None:
        dt_mut = 1
        dt_sum = 0

        while 1:
            if len(self.players) <= 1:
                if len(self.players) == 0:
                    print(f"Tie")
                    return
                else:
                    print(f"Winner: {self.players[0]}")
                    dt_mut *= 0.99
                    self.end_screen = EndScreen(self.screen, self.starting_player, self.players[0])

            dt = (self.clock.tick(60) / 1000.0) * dt_mut
            dt_sum += dt

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    exit()

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
                    ...

            self.anim_manager.update(dt)
            self.safezone.update(dt)

            self.screen.fill((0, 0, 0))
            self.safezone.blit(self.screen, self.player)

            x_walls_dist = self.safezone.right_wall - self.safezone.left_wall
            y_walls_dist = self.safezone.bottom_wall - self.safezone.top_wall

            if x_walls_dist < self.MAP_SIZE / 1.66 and y_walls_dist < self.MAP_SIZE / 1.66 and not self.has_done_bonus_powerups:
                self.NUM_POWERUPS = self.NUM_POWERUP_SECTIONS * 10 # half
                self.powerups.extend(self.generate_powerups(int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)))
                self.has_done_bonus_powerups = True

            keys = pg.key.get_pressed()

            if not self.spectating:
                if keys[pg.K_UP] or keys[pg.K_w]: self.player.move_up(dt)
                elif keys[pg.K_RIGHT] or keys[pg.K_d]: self.player.move_right(dt)
                elif keys[pg.K_DOWN] or keys[pg.K_s]: self.player.move_down(dt)
                elif keys[pg.K_LEFT] or keys[pg.K_a]: self.player.move_left(dt)

                if keys[pg.K_SPACE]:
                    if self.player.shoot():
                        self.sounds["laserShoot"].play()

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

                bullets_to_remove = []
                for bullet in self.bullets:
                    if player == self.player:
                        bullet.draw(self.screen, self.player)
                    
                    if bullet.parent == player: continue

                    if player.global_rect.colliderect(bullet.rect):
                        if player == self.player:
                            self.sounds["hitHurt"].play()

                        damage = bullet.hit(player)
                        bullet.parent.shots_hit += 1
                        bullet.parent.total_damage += damage

                        if player.dead:
                            bullet.parent.kills += 1

                        bullets_to_remove.append(bullet)
                        
                    if bullet.distance_travelled > self.MAX_BULLET_TRAVEL_DIST:
                        bullets_to_remove.append(bullet)

                    if bullet not in bullets_to_remove:
                        bullet_dist = dist((bullet.x, bullet.y), (player.x, player.y))

                        if bullet_dist < closest_dist:
                            closest_dist = bullet_dist
                            closest_bullet = bullet

                for bullet in bullets_to_remove:
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)

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

                            if powerup_dist > 2000: continue

                            if powerup_dist <= player.rect.w:
                                if player == self.player:
                                    self.sounds["powerUp"].play()

                                self.powerup_grid[floor(powerup.y / self.POWERUP_SECTION_SIZE)][floor(powerup.x / self.POWERUP_SECTION_SIZE)].remove(powerup)
                                powerup.pickup(player)
                            else:
                                close_powerups.append(powerup)

                            if powerup_dist < closest_dist:
                                closest_dist = powerup_dist
                                closest_powerup = powerup
                    
                if player == self.player and closest_powerup is not None:
                    pg.draw.circle(self.screen, (255, 255, 255), (closest_powerup.x - closest_powerup.image.width // 2 - (player.x - self.WIDTH // 2 + closest_powerup.image.width // 2), closest_powerup.y - closest_powerup.image.height // 2 - (player.y - self.HEIGHT // 2 + closest_powerup.image.height // 2)), 5)

                player.set_close_powerups(close_powerups)
                player.draw(self.screen, self.player)

                closest_player = None
                closest_dist = float('inf')
                for other_player in self.players:
                    if other_player is player: continue

                    player_dist = dist((other_player.x, other_player.y), (player.x, player.y))
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

                    player.ai_move(dt, (int(self.safezone.left_wall), int(self.safezone.right_wall), int(self.safezone.top_wall), int(self.safezone.bottom_wall)), (left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist), closest_powerup, closest_player, closest_bullet)

                if player.dead:
                    dead_players.append(player)

            for dead_player in dead_players:
                if len(self.players) == 1: continue

                if dead_player == self.player:
                    self.spectating = True

                for rarity, powerup_info, on_pickup in dead_player.collected_powerups:
                    new_powerup = Powerup(min(self.MAP_SIZE_X - 1, max(0, dead_player.x + randint(-50, 50))), min(self.MAP_SIZE_Y-1, max(0, dead_player.y + randint(-50, 50))), rarity, powerup_info, on_pickup)
                    self.powerups.append(new_powerup)
                    self.powerup_grid[floor(new_powerup.y / self.POWERUP_SECTION_SIZE)][floor(new_powerup.x / self.POWERUP_SECTION_SIZE)].append(new_powerup)

                self.players.remove(dead_player)
                
                if self.spectating and dead_player.index < self.player.index:
                    self.spectator_index -= 1

                self.dead_players.append(dead_player)

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

            if self.end_screen is not None and dt_mut < 0.20:
                self.end_screen.draw()

            pg.display.flip()

class EndScreen:
    def __init__(self, screen: pg.Surface, my_player: Shape, winner: Shape | None) -> None:
        self.screen = screen
        self.my_player = my_player
        self.winner = winner

        self.won = False
        if self.winner == self.my_player:
            self.won = True

        self.large_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 40)
        self.medium_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 30)
        self.small_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", 20)

        self.winner_lbl = self.large_font.render(f"Winner: {self.winner.shape_name}", True, (255, 255, 255))
        
        self.winner_sprite = pg.transform.smoothscale(self.winner.shape_image, (300, 300))
        if winner != self.my_player:
            self.winner_sprite = pg.transform.smoothscale(self.winner.enemy_shape_image, (300, 300))

        self.powerup_stats = [self.medium_font.render(str(winner.num_common_picked), True, (255, 255, 255)),
                              self.medium_font.render(str(winner.num_uncommon_picked), True, (255, 255, 255)),
                              self.medium_font.render(str(winner.num_rare_picked), True, (255, 255, 255)),
                              self.medium_font.render(str(winner.num_legendary_picked), True, (255, 255, 255))]

        self.powerup_stat_spacing = 100
        self.powerup_stat_width = sum([powerup_stat.width for powerup_stat in self.powerup_stats]) + self.powerup_stat_spacing * 4

        self.winner_stats = [self.small_font.render(f"{winner.kills}x kills", True, (255, 255, 255)),
                             self.small_font.render(f"{winner.total_damage:.2f} total damage", True, (255, 255, 255)),
                             self.small_font.render(f"{winner.shots_hit} shots hit", True, (255, 255, 255)),
                             self.small_font.render(f"{(winner.shots_hit / winner.shots_fired * 100):.2f}% accuracy", True, (255, 255, 255))]

    def draw(self) -> None:
        self.screen.fill(0)

        self.screen.blit(self.winner_lbl, (self.screen.width // 2 - self.winner_lbl.width // 2, 50))
        self.screen.blit(self.winner_sprite, (self.screen.width // 2 - self.winner_sprite.width // 2, 300))

        x = self.screen.width // 2 - self.powerup_stat_width // 2 + self.powerup_stat_spacing
        for stat in self.powerup_stats:
            self.screen.blit(stat, (x, 800))
            x += stat.width + self.powerup_stat_spacing

        for i, stat in enumerate(self.winner_stats):
            self.screen.blit(stat, (self.screen.width // 2 + 200, 300 + 40 * i))

if __name__ == "__main__":
    ShapeRoyale()