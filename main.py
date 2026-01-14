import pygame as pg
import os

from sound import generate_sine_wave

from time import time
from json import loads
from math import dist, sin, cos, atan2, pi, sqrt, floor, ceil
from ast import literal_eval
from random import randint, choice, uniform
#from shapely import box, Polygon

from typing import List, Sequence, Dict

FONTS_PATH = "./UI/Fonts"

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

def obj_dist(obj1: object, obj2: object) -> float:
    """Returns the distance between 2 objects with x and y position properties"""
    return dist((obj1.x, obj1.y), (obj2.x, obj2.y))

class Poison:
    def __init__(self, parent: any, deal_damage_func: object, on_poison_end: object, damage: int, duration: int, lifesteal: float) -> None:
        self.parent = parent
        self.deal_damage_func = deal_damage_func
        self.on_poison_end = on_poison_end

        self.damage = damage
        self.duration = duration
        self.lifesteal = lifesteal

        self.last_tick_time = time()

    def update(self) -> None:
        if time() - self.last_tick_time >= 1:
            self.duration -= time() - self.last_tick_time
            self.last_tick_time = time()

            self.deal_damage_func(self.damage)
            self.parent.give_lifesteal(self.damage * self.lifesteal)

            if self.duration <= 0: self.on_poison_end(self)

class Bullet:
    def __init__(self, parent: any, x: float, y: float, velocity: List[float], base_damage: int, damage_growth: float,
                 poison_damage: int, penetration: float, lifesteal: float, bullet_img: pg.Surface) -> None:

        self.parent = parent
        
        self.start_x = x
        self.start_y = y

        self.x = x
        self.y = y
        self.velocity = velocity

        self.base_damage = base_damage
        self.damage_growth = damage_growth
        self.poison_damage = poison_damage
        self.penetration = penetration
        self.lifesteal = lifesteal

        self.image = bullet_img

    @property
    def distance_travelled(self) -> float:
        return dist((self.x, self.y), (self.start_x, self.start_y))

    @property
    def rect(self) -> pg.Rect:
        return pg.Rect(self.x - self.image.width // 2, self.y - self.image.height // 2, self.image.width, self.image.height)

    def move(self, dt: float) -> None:
        self.x += self.velocity[0] * dt
        self.y += self.velocity[1] * dt

    def draw(self, screen: pg.Surface, draw_parent: any) -> None:
        screen_rect = pg.Rect(draw_parent.x - screen.width // 2 + self.image.width // 2, draw_parent.y - screen.height // 2 + self.image.height // 2, screen.width, screen.height)

        if not pg.Rect(self.x - self.image.width // 2, self.y - self.image.height // 2, self.image.width, self.image.height).colliderect(screen_rect): return

        screen.blit(self.image, (self.x - self.image.width // 2 - screen_rect.x, self.y - self.image.height // 2 - screen_rect.y))

    def hit(self, target: any) -> None:
        if self.damage_growth == 1.0: # Default
            # No bullet growth
            health_damage = self.base_damage
        else:
            health_damage = self.base_damage * (self.damage_growth * self.distance_travelled / 400.0)

        shield_damage = health_damage * self.penetration

        target.take_damage(health_damage)
        target.take_shield_damage(shield_damage)

        if self.poison_damage > 0:
            target.add_poison(self.parent, self.poison_damage, (self.lifesteal - 1))

        self.parent.give_lifesteal(health_damage * (self.lifesteal - 1))

class Powerup:
    WIDTH = 50
    HEIGHT = 50

    def __init__(self, x: int, y: int, rarity: str, powerup_info: Dict[str, Dict], on_pickup: object) -> None:
        self.x = x
        self.y = y

        self.rarity = rarity
        self.name = choice(list(powerup_info[rarity]["types"]))
        self.powerup_info = powerup_info
        self.info = self.powerup_info[rarity]["types"][self.name]

        self.on_pickup = on_pickup

        self.color = literal_eval(self.powerup_info[rarity]["color"])

        self.blurb = self.info["blurb"]
        self.description = self.info["description"]
        self.effect = self.info["effect"]
        self.value = self.info["value"]

        self.image = pg.Surface((self.WIDTH, self.HEIGHT), pg.SRCALPHA)
        pg.draw.aacircle(self.image, self.color, (self.WIDTH // 2, self.HEIGHT // 2), self.WIDTH // 2)

    def render_popup(self) -> pg.Surface:
        title_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=40)
        blurb_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=25)
        description_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=20)

        rect_w, rect_h = 700, 400
        surface = pg.Surface((rect_w, rect_h), pg.SRCALPHA)

        pg.draw.rect(surface, self.color, (0, 0, rect_w, rect_h), border_radius=20)

        curr_y = 20
        title_lbl = title_font.render(self.name, True, (255, 255, 255), wraplength=rect_w - 20)
        surface.blit(title_lbl, (rect_w // 2 - title_lbl.width // 2, curr_y))
        curr_y += title_lbl.height + 20

        blurb_lbl = blurb_font.render(f'"{self.blurb}"', True, (255, 255, 255), wraplength=rect_w - 20)
        surface.blit(blurb_lbl, (rect_w // 2 - blurb_lbl.width // 2, curr_y))
        curr_y += blurb_lbl.height

        description_lbl = description_font.render(self.description, True, (255, 255, 255), wraplength=rect_w - 20)
        rarity_lbl = blurb_font.render(self.rarity, True, (255, 255, 255))

        rarity_y = rect_h - rarity_lbl.height - 20
        surface.blit(rarity_lbl, (rect_w // 2 - rarity_lbl.width // 2, rarity_y))

        description_y = curr_y + (rarity_y - curr_y) // 2 - description_lbl.height // 2
        surface.blit(description_lbl, (rect_w // 2 - description_lbl.width // 2, description_y))

        return surface

    def draw(self, screen: pg.Surface, draw_parent: any) -> None:
        screen_rect = pg.Rect(draw_parent.x - screen.width // 2 + self.image.width // 2, draw_parent.y - screen.height // 2 + self.image.height // 2, screen.width, screen.height)

        if not pg.Rect(self.x - self.image.width // 2, self.y - self.image.height // 2, self.image.width, self.image.height).colliderect(screen_rect): return

        screen.blit(self.image, (self.x - self.image.width // 2 - screen_rect.x, self.y - self.image.height // 2 - screen_rect.y))

    def pickup(self, player: any) -> None:
        player.parse_effect(self.effect, self.value)
        player.collected_powerups.append((self.rarity, self.powerup_info, self.on_pickup))
        player.show_powerup_popup(self.render_popup())

        self.on_pickup(self)

class Shape:
    POISON_DURATION = 10

    MAX_ABILITY_SETTINGS = {
        "max_hp": float('inf'),
        "max_shield": float('inf'),
        "max_speed": 80.0,
        "damage": float('inf'),
        "firerate": float('inf'),
        "bullet_speed": 10.0,
        "penetration": float('inf'),
        "shield_regen_rate": float('inf'),
        "lifesteal": float('inf'),
        "poison_damage": float('inf'),
        "zone_resistance": 0.9,
        "health_regen_rate": float('inf'),
        "damage_growth": float('inf')
    }

    def __init__(self, map_size: int, x: float, y: float, index: int, shape_name: str, shape_info: Dict[str, Dict], shape_image: pg.Surface, enemy_shape_image: pg.Surface, bullets: List[Bullet],
                 bullet_img: pg.Surface, is_player: bool, squad: List[any] = []) -> None:

        self.map_size = map_size

        self.x = x
        self.y = y
        self.index = index
        self.rotation = 0

        self.shape_name = shape_name
        self.shape_info = shape_info
        self.info = self.shape_info[self.shape_name]

        self.shape_image = shape_image
        self.enemy_shape_image = enemy_shape_image
        self.rotated_shape_image = shape_image.copy()
        self.rotated_enemy_shape_image = enemy_shape_image.copy()

        self.bullet_img = bullet_img

        self.is_player = is_player
        self.squad = squad

        self.dead = False

        self.max_hp = self.info['hp'] # literal
        self.max_shield = self.info['shield'] # literal
        self.max_speed = self.info['speed'] # literal
        self.damage = self.info['damage'] # literal
        self.firerate = self.info['firerate'] # literal 
        self.bullet_speed = self.info['bullet_speed'] # literal
        self.penetration = self.info['penetration'] # percent
        self.shield_regen_rate = self.info['shield_regen'] # literal
        self.lifesteal = 1.0 # percent
        self.poison_damage = 0 # literal
        self.zone_resistance = 1.0 # percent
        self.health_regen_rate = self.info["health_regen"] # literal
        self.damage_growth = 1.0 # percent

        self.hp = self.max_hp
        self.shield = self.max_shield

        self.last_shoot_time = 0

        self.bullets = bullets
        self.poisons = []
        self.collected_powerups = []

        self.showing_powerup_popup = False
        self.powerup_popup = None

        self.rect = pg.Rect(0, 0, self.shape_image.width, self.shape_image.height)

        self.close_powerups = []
        self.target = (randint(0, self.map_size), randint(0, self.map_size))

        self.info_surf = pg.Surface((100, 40), pg.SRCALPHA)

        self.num_inputs = 0
        self.prioritises_x = bool(randint(0, 1))

    @property
    def global_rect(self) -> pg.Rect: return pg.Rect(self.x - self.rotated_shape_image.width * 0.5, self.y - self.rotated_shape_image.height * 0.5, self.rotated_shape_image.width, self.rotated_shape_image.height)

    def change_var_value(self, var_name: str, value_type: str, value: any) -> None:
        var = getattr(self, var_name)
        if value_type == 'percentage_increase':
            var *= value

        elif value_type == 'increase':
            var += value

        value = min(var, self.MAX_ABILITY_SETTINGS[var_name])

        setattr(self, var_name, value)

    def parse_effect(self, effect: str, value: any) -> None:
        """Target.Effect.Valuetype, value"""

        args = effect.split('.')

        if len(args) < 3:
            raise Exception("Provided args is not valid! 'arg1.arg2.arg3' is required!")

        if args[0] == 'player':
            var = None

            match args[1]:
                case 'maxhp': var = "max_hp"
                case 'shield': var = "max_shield"
                case 'speed': var = "max_speed"
                case 'damage': var = "damage"
                case 'firerate': var = "firerate"
                case 'bulletspeed': var = "bullet_speed"
                case 'penetration': var = "penetration"
                case 'shieldregenrate': var = "shield_regen_rate"
                case 'lifesteal': var = "lifesteal"
                case 'poisondamage': var = "poison_damage"
                case 'zoneresistance': var = "zone_resistance"
                case 'healthregenrate': var = "health_regen_rate"
                case 'damagegrowth': var = "damage_growth"

            self.change_var_value(var, args[2], value)

    def show_powerup_popup(self, powerup_popup: pg.Surface) -> None:
        self.powerup_popup = powerup_popup
        self.showing_powerup_popup = True

    def set_close_powerups(self, close_powerups: List[Powerup]) -> None:
        self.close_powerups = close_powerups

    def die(self) -> None:
        #print("Your dead now, if you didn't know.")
        self.dead = True

    def take_damage(self, damage: float) -> None:
        self.hp -= damage

        if self.hp <= 0:
            self.die()

    def take_shield_damage(self, shield_damage: float) -> None:
        leftover_shield_damage = shield_damage - self.shield

        if leftover_shield_damage > 0:
            self.take_damage(leftover_shield_damage)
            self.shield = 0
        else:
            self.shield -= shield_damage

    def on_poison_end(self, poison: Poison) -> None:
        self.poisons.remove(poison)

    def add_poison(self, parent: any, poison_damage: int, poison_lifesteal: float) -> None:
        self.poisons.append(Poison(parent, self.take_damage, self.on_poison_end, poison_damage, self.POISON_DURATION, poison_lifesteal))

    def give_lifesteal(self, lifesteal_health: float) -> None:
        self.give_hp(lifesteal_health)

    def give_hp(self, hp: int) -> None:
        self.hp = min(self.max_hp, self.hp + hp)

    def give_shield_hp(self, hp: int) -> None:
        self.shield = min(self.max_shield, self.shield + hp)

    def move_up(self, dt: float) -> None:
        self.y -= self.max_speed * dt * 30
        self.rotation = 0

    def move_right(self, dt: float) -> None:
        self.x += self.max_speed * dt * 30
        self.rotation = 270

    def move_down(self, dt: float) -> None:
        self.y += self.max_speed * dt * 30
        self.rotation = 180

    def move_left(self, dt: float) -> None:
        self.x -= self.max_speed * dt * 30
        self.rotation = 90

    def move_to(self, x: float, y: float, dt: float) -> None:
        rx, ry = x - self.x, y - self.y

        abs_x = abs(rx)
        abs_y = abs(ry)

        def position_x() -> bool:
            """Returns if it took an action"""
            if abs_x > 20:
                if rx < 0: self.move_left(dt)
                else: self.move_right(dt)

                return True
            return False

        def position_y() -> bool:
            if abs_y > 20:
                if ry < 0: self.move_up(dt)
                else: self.move_down(dt)

                return True
            return False

        action_taken = False
        if self.prioritises_x:
            action_taken = action_taken or position_x()
            if not action_taken:
                position_y()
        else:
            action_taken = action_taken or position_y()
            if not action_taken:
                position_x()

    def shoot(self) -> None:
        if time() - self.last_shoot_time >= 1 / self.firerate:
            self.last_shoot_time = time()

            match self.rotation:
                case 0: bullet_vel = [0, -self.max_speed * (self.bullet_speed + 1) / 2.5]
                case 90: bullet_vel = [-self.max_speed * (self.bullet_speed + 1) / 2.5, 0]
                case 180: bullet_vel = [0, self.max_speed * (self.bullet_speed + 1) / 2.5]
                case 270: bullet_vel = [self.max_speed * (self.bullet_speed + 1) / 2.5, 0]

            self.bullets.append(Bullet(self, self.x, self.y, bullet_vel, self.damage, self.damage_growth, self.poison_damage, self.penetration, self.lifesteal, self.bullet_img))

    def fight_player(self, dt: float, closest_player: Player) -> None:
        dx = closest_player.x - self.x
        dy = closest_player.y - self.y

        def position_x() -> bool:
            """Returns if it took an action"""
            if abs(dx) < 40:
                # We are inline with the enemy but we just need to face them and then shoot them
                if dy < 0:
                    self.move_down(dt)
                    self.move_up(dt)
                else:
                    self.move_up(dt)
                    self.move_down(dt)
                self.shoot()
                return True
            return False

        def position_y() -> bool:
            """Returns if it took an action"""
            if abs(dy) < 40:
                # We are inline with the enemy but we just need to face them and then shoot them
                if dx < 0:
                    self.move_right(dt)
                    self.move_left(dt)
                else:
                    self.move_left(dt)
                    self.move_right(dt)
                self.shoot()
                return True
            return False

        action_taken = False
        if self.prioritises_x:
            action_taken = action_taken or position_x()
            if not action_taken:
                position_y()
        else:
            action_taken = action_taken or position_y()
            if not action_taken:
                position_x()
        
        if not action_taken:
            self.move_to(closest_player.x, closest_player.y, dt)

    def ai_move(self, dt: float, wall_distances: tuple[float], closest_powerup: Powerup | None, closest_player: Player | None, closest_bullet: Bullet | None) -> None:
        if closest_powerup is not None:
            powerup_dist = obj_dist(closest_powerup, self)
        if closest_player is not None:
            player_dist = obj_dist(closest_player, self)
        if closest_bullet is not None:
            bullet_dist = obj_dist(closest_bullet, self)

        for i, wall_distance in enumerate(wall_distances):
            if abs(wall_distance) > 0.005: continue

            match i:
                case 0: self.move_left(dt)
                case 1: self.move_right(dt)
                case 2: self.move_up(dt)
                case 3: self.move_down(dt)

            self.target = (randint(0, self.map_size), randint(0, self.map_size))
            return

        if player_dist < 1000:
            self.fight_player(dt, closest_player)
        elif closest_powerup is not None:
            self.move_to(closest_powerup.x, closest_powerup.y, dt)
        else:
            self.move_to(self.target[0], self.target[1], dt)

            if dist((self.x, self.y), self.target) < 40:
                self.target = (randint(0, self.map_size), randint(0, self.map_size))

    def render_info_surf(self) -> None:
        self.info_surf.fill((90, 90, 90))

        hp_percent = self.hp / self.max_hp
        shield_percent = self.shield / self.max_shield

        pg.draw.rect(self.info_surf, (0, 255, 0), (0, 0, self.info_surf.width * hp_percent, self.info_surf.height // 2))
        pg.draw.rect(self.info_surf, (0, 0, 255), (0, self.info_surf.height // 2, self.info_surf.width * shield_percent, self.info_surf.height // 2))

    def update(self, dt: float) -> None:
        for poison in self.poisons:
            poison.update()

        self.give_hp(self.health_regen_rate * dt)
        self.give_shield_hp(self.shield_regen_rate * dt)

        self.rotated_shape_image = pg.transform.rotate(self.shape_image, self.rotation)
        self.rotated_enemy_shape_image = pg.transform.rotate(self.enemy_shape_image, self.rotation)

        self.render_info_surf()

    def draw(self, screen: pg.Surface, draw_parent: any) -> None:
        if draw_parent in self.squad:
            image = self.rotated_shape_image
        else:
            image = self.rotated_enemy_shape_image

        screen_rect = pg.Rect(draw_parent.x - screen.width // 2 + image.width // 2, draw_parent.y - screen.height // 2 + image.height // 2, screen.width, screen.height)

        if not pg.Rect(self.x, self.y, image.width, image.height).colliderect(screen_rect): return

        screen.blit(image, (self.x - screen_rect.x, self.y - screen_rect.y))
        screen.blit(self.info_surf, (self.x - screen_rect.x - 100, self.y - screen_rect.y - 30))

        if self.showing_powerup_popup and draw_parent is self and self.is_player:
            screen.blit(self.powerup_popup, (screen.width // 2 - self.powerup_popup.width // 2, screen.height // 2 - self.powerup_popup.height // 2))

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

class Player:
    def __init__(self) -> None:
        self.ready = False
        self.shape_index = 0

    @property
    def ready_text(self) -> str:
        if self.ready: return "Ready"
        else: return "Not ready"

    @property
    def ready_color(self) -> str:
        if self.ready: return pg.Color(0, 255, 0)
        else: return pg.Color(255, 0, 0)

class Anim:
    def __init__(self, obj: object, property: str, target: float, step: float, max_finish_dist: float) -> None:
        self.object = obj
        self.property = property
        self.target = target
        self.step = step
        self.max_finish_dist = max_finish_dist

        self.finished = False

        if not hasattr(self.object, self.property):
            raise Exception(f"Error while creating animation for {self.object}: {self.object} has no property \"{self.property}\"!")

    @property
    def gprop(self) -> float:
        return getattr(self.object, self.property)
    
    def sprop(self, value: float) -> None:
        setattr(self.object, self.property, value)

    def update(self, dt: float) -> bool:
        if abs(self.target - self.gprop) < max(self.step * dt, self.max_finish_dist):
            self.sprop(self.target)
            self.finished = True
            return True
        
        self.sprop(self.gprop + self.step * dt)
        return False

class AnimManager:
    def __init__(self) -> None:
        if not hasattr(self.__class__, "anims"):
            self.__class__.anims = []

    def new(self, obj: object, property: str, target: float, step: float, max_finish_dist: float = 0.5) -> Anim:
        anim = Anim(obj, property, target, step, max_finish_dist)
        self.anims.append(anim)

        return anim

    def update(self, dt: float) -> None:
        complete_anims = []

        for anim in self.anims:
            done = anim.update(dt)

            if done:
                complete_anims.append(anim)

        for anim in complete_anims:
            self.anims.remove(anim)

class Safezone:
    NUM_POINTS = 100
    DISTANCE_TO_MOVE_REDUCTION = 1000
    TARGET_RADIUS_ALLOWANCE = 1.05
    SCALING = 80
    SPEED = 10

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

        self.anims.append(AnimManager().new(self, "left_wall", self.target[0] - self.target_radius, self.zone_speed))
        self.anims.append(AnimManager().new(self, "right_wall", self.target[0] + self.target_radius, -self.zone_speed))
        self.anims.append(AnimManager().new(self, "top_wall", self.target[1] - self.target_radius, self.zone_speed))
        self.anims.append(AnimManager().new(self, "bottom_wall", self.target[1] + self.target_radius, -self.zone_speed))

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

        #self.players[0].controller.plugged_in = True
        #self.players[1].controller.plugged_in = True
        #self.players[1].ready = True
        #self.players[2].controller.plugged_in = True
        #self.players[2].ready = True
        #self.players[3].controller.plugged_in = True
        #self.players[3].ready = True

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

        cards_w = card_w * 4 + pad_w * 3
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
        shape_firerate = self.shape_info[selected_shape]["firerate"]
        shape_dmg = self.shape_info[selected_shape]["damage"]
        shape_speed = self.shape_info[selected_shape]["speed"]

        shape_info_lbls = [
            self.fonts["small"].render(f"Health: {shape_hp}HP", True, (255, 255, 255)),
            self.fonts["small"].render(f"Rate of fire: {shape_firerate}/s", True, (255, 255, 255)),
            self.fonts["small"].render(f"Damage: {shape_dmg}HP", True, (255, 255, 255)),
            self.fonts["small"].render(f"Speed: {shape_speed}u/s", True, (255, 255, 255)),
        ]

        largest_width = shape_info_lbls[1].width

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
    NUM_POWERUPS = 24 * 15 # this must be divisible by the NUM_POWERUP_SECTIONS below
    NUM_POWERUP_SECTIONS = 24 
    POWERUP_SECTION_SIZE = MAP_SIZE / NUM_POWERUP_SECTIONS

    MAX_BULLET_TRAVEL_DIST = 2000

    def __init__(self) -> None:
        if not (self.NUM_POWERUPS / self.NUM_POWERUP_SECTIONS).is_integer() or self.NUM_POWERUPS % self.NUM_POWERUP_SECTIONS != 0:
            raise Exception("NUM_POWERUPS must be divisible by NUM_POWERUP_SECTIONS such that the resualt is a valid integer!")

        info = pg.display.get_desktop_sizes()[0]
        self.WIDTH = info[0]
        self.HEIGHT = info[1]
        self.screen = pg.display.set_mode((self.WIDTH, self.HEIGHT), pg.SRCALPHA | pg.FULLSCREEN, display=1)

        self.anim_manager = AnimManager()

        #self.main_menu = MainMenu(self.screen)

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
        self.players = self.generate_players()
        self.powerups = self.generate_powerups()

        #self.players[0].max_speed = 100

        self.powerup_sections = [(i*self.POWERUP_SECTION_SIZE, (i+1)*self.POWERUP_SECTION_SIZE) for i in range(self.NUM_POWERUP_SECTIONS)]
        self.powerup_section_index = 0

        self.fps_font = pg.font.SysFont(f"{FONTS_PATH}/PressStart2P.ttf", 30)

        self.spectator_index = 0
        self.spectating = False
        self.player.is_player = not self.spectating

        self.main()
    
    @property
    def player(self) -> Player:
        return self.players[self.spectator_index]

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

        #name = self.shape_names[self.main_menu.player.shape_index]
        name = choice(self.shape_names) 
        new_shape = Shape(
            self.MAP_SIZE, randint(0, self.MAP_SIZE_X), randint(0, self.MAP_SIZE_Y), 0, choice(self.shape_names), self.shape_info, self.shape_images[f"{name}Friendly"],
            self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, True, []
        )
        new_shape.squad.append(new_shape)
        shapes.append(new_shape)

        for i in range(self.NUM_PLAYERS - 1):
            name = choice(self.shape_names)
            new_shape = Shape(
                self.MAP_SIZE, randint(0, self.MAP_SIZE_X), randint(0, self.MAP_SIZE_Y), i+1, choice(self.shape_names), self.shape_info, self.shape_images[f"{name}Friendly"],
                self.shape_images[f"{name}Enemy"], self.bullets, self.bullet_img, is_player=False, squad=[]
            )
            new_shape.squad.append(new_shape)
            shapes.append(new_shape)

        return shapes

    def generate_powerups(self) -> List[Powerup]:
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

            powerup = Powerup(randint(0, self.MAP_SIZE_X), randint(0, self.MAP_SIZE_Y), rarity, self.powerup_info, self.on_powerup_pickup)
            powerups.append(powerup)
            self.powerup_grid[floor(powerup.y // self.POWERUP_SECTION_SIZE)][floor(powerup.x // self.POWERUP_SECTION_SIZE)].append(powerup)

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
                else:
                    print(f"Winner: {self.players[0]}")

                return

            dt = (self.clock.tick(999) / 1000.0) * dt_mut
            dt_mut = 1
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

            self.anim_manager.update(dt)
            self.safezone.update(dt)

            self.screen.fill((0, 0, 0))
            self.safezone.blit(self.screen, self.player)

            keys = pg.key.get_pressed()

            if not self.spectating:
                if keys[pg.K_UP]: self.player.move_up(dt)
                elif keys[pg.K_RIGHT]: self.player.move_right(dt)
                elif keys[pg.K_DOWN]: self.player.move_down(dt)
                elif keys[pg.K_LEFT]: self.player.move_left(dt)

                if keys[pg.K_SPACE]:
                    self.player.shoot()

                elif keys[pg.K_LSHIFT]:
                    if self.player.showing_powerup_popup:
                        self.player.showing_powerup_popup = False

            for powerup in self.powerups:
                powerup.draw(self.screen, self.player)

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
                    
                    #if i == 0:
                    #    bullet.move(dt)

                    if bullet.parent == player: continue

                    if player.global_rect.colliderect(bullet.rect):
                        bullet.hit(player)
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
                #for powerup in self.powerups[self.powerup_sections[self.powerup_section_index][0]:self.powerup_sections[self.powerup_section_index][1]]:
                for y_offset in range(-1, 2):
                    y_tile = min(self.NUM_POWERUP_SECTIONS - 1, max(0, floor(player.y / self.POWERUP_SECTION_SIZE) + y_offset))
                    for x_offset in range(-1, 2):
                        x_tile = min(self.NUM_POWERUP_SECTIONS - 1, max(0, floor(player.x / self.POWERUP_SECTION_SIZE) + x_offset))
                        for powerup in self.powerup_grid[y_tile][x_tile]:
                            powerup_dist_x = abs(powerup.x - player.x)
                            powerup_dist_y = abs(powerup.y - player.y)
            
                            #powerup_dist = dist((powerup.x, powerup.y), (player.x, player.y))
                            powerup_dist = sqrt(powerup_dist_x ** 2 + powerup_dist_y ** 2)

                            if powerup_dist <= player.rect.w:
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

                    #x_walls_dist = max(-1, min(1, (player.x - self.safezone.left_wall + self.WIDTH / 2) / (self.safezone.right_wall - self.safezone.left_wall + 0.00000000000000000001) * 2 - 1))
                    #y_walls_dist = max(-1, min(1, (player.y - self.safezone.top_wall + self.HEIGHT / 2) / (self.safezone.bottom_wall - self.safezone.top_wall + 0.00000000000000000001) * 2 - 1))

                    right_wall_dist = max(0, min(1, (player.x - self.safezone.left_wall + self.WIDTH / 2) / (self.safezone.right_wall - self.safezone.left_wall + 0.00000000000000000001)))
                    left_wall_dist = 1 - right_wall_dist
                    bottom_wall_dist = max(0, min(1, (player.y - self.safezone.top_wall + self.HEIGHT / 2) / (self.safezone.bottom_wall - self.safezone.top_wall + 0.00000000000000000001)))
                    top_wall_dist = 1 - bottom_wall_dist

                    #if i == self.spectator_index:
                    #    print(round(top_wall_dist, 2), round(bottom_wall_dist, 6))

                    danger = max(left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist)

                    player.ai_move(dt, (left_wall_dist, right_wall_dist, top_wall_dist, bottom_wall_dist), closest_powerup, closest_player, closest_bullet)

                if player.dead:
                    dead_players.append(player)

            for dead_player in dead_players:
                if dead_player == self.player:
                    self.spectating = True

                for rarity, powerup_info, on_pickup in dead_player.collected_powerups:
                    new_powerup = Powerup(dead_player.x + randint(-50, 50), dead_player.y + randint(-50, 50), rarity, powerup_info, on_pickup)
                    self.powerups.append(new_powerup)
                    self.powerup_grid[floor(new_powerup.y / self.POWERUP_SECTION_SIZE)][floor(new_powerup.x / self.POWERUP_SECTION_SIZE)].append(new_powerup)

                self.players.remove(dead_player)
                self.spectator_index = min(self.spectator_index, max(0, len(self.players)-1))

            self.screen.blit(self.fps_font.render(f"{self.clock.get_fps():.2f}", True, (255, 255, 255)), (20, 20))
            self.screen.blit(self.fps_font.render(f"{self.spectator_index+1}/{len(self.players)}", True, (255, 255, 255)), (20, 40))

            self.powerup_section_index += 1
            if self.powerup_section_index >= self.NUM_POWERUP_SECTIONS: self.powerup_section_index = 0

            pg.display.flip()

if __name__ == "__main__":
    ShapeRoyale()