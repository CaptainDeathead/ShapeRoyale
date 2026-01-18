import pygame as pg

from bullet import Bullet
from powerups import Powerup, Poison

from networking import Client, BaseClient

from utils import FONTS_PATH, obj_dist

from math import dist
from random import randint
from time import time
from typing import List, Tuple, Dict

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

class Shape:
    POISON_DURATION = 10

    MAX_ABILITY_SETTINGS = {
        "max_hp": float('inf'),
        "max_shield": float('inf'),
        "max_speed": 80.0,
        "damage": float('inf'),
        "firerate": float('inf'),
        "bullet_speed": 40.0,
        "penetration": float('inf'),
        "shield_regen_rate": float('inf'),
        "lifesteal": float('inf'),
        "poison_damage": float('inf'),
        "zone_resistance": 100.0,
        "health_regen_rate": float('inf'),
        "damage_growth": float('inf')
    }

    def __init__(self, map_size: int, x: float, y: float, index: int, shape_name: str, shape_info: Dict[str, Dict], shape_image: pg.Surface, enemy_shape_image: pg.Surface, bullets: List[Bullet],
                 bullet_img: pg.Surface, is_player: bool, squad: List[any] = [], client: Client | None = None, player_name: str = "bot") -> None:

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
        self.client = client
        self.player_name = player_name

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
        self.damage_growth = 0.0 # percent

        self.hp = self.max_hp
        self.shield = self.max_shield

        self.last_shoot_time = 0

        self.bullets = bullets
        self.poisons = []
        self.collected_powerups = []

        self.showing_powerup_popup = False
        self.powerup_popup = None
        self.powerup_popup_create_time = time()

        self.rect = pg.Rect(0, 0, self.shape_image.width, self.shape_image.height)

        self.close_powerups = []
        self.target = (randint(0, self.map_size), randint(0, self.map_size))

        self.name_font = pg.Font(f"{FONTS_PATH}/PressStart2P.ttf", 16)
        self.name_surf = self.name_font.render(f"{self.player_name}", True, (255, 255, 255), 15)
        self.info_surf = pg.Surface((100, 40), pg.SRCALPHA)

        self.num_inputs = 0
        self.prioritises_x = bool(randint(0, 1))

        self.kills = 0
        self.shots_hit = 0
        self.shots_fired = 0
        self.total_damage = 0

        self.num_common_picked = 0
        self.num_uncommon_picked = 0
        self.num_rare_picked = 0
        self.num_legendary_picked = 0

        self.last_update = 0

    @property
    def global_rect(self) -> pg.Rect: return pg.Rect(self.x - self.rotated_shape_image.width * 0.5, self.y - self.rotated_shape_image.height * 0.5, self.rotated_shape_image.width, self.rotated_shape_image.height)

    def to_dict(self) -> dict[str, any]:
        return {
            "x": self.x, "y": self.y, "index": self.index, "shape_name": self.shape_name, "is_player": self.is_player, "squad": [], "player_name": self.player_name
        }

    def to_full_dict(self) -> dict[str, any]:
        return {
            "x": self.x, "y": self.y, "index": self.index, "rotation": self.rotation,
            "max_hp": self.max_hp, "max_shield": self.max_shield, "max_speed": self.max_speed, "damage": self.damage, "firerate": self.firerate, "bullet_speed": self.bullet_speed, "penetration": self.penetration,
            "shield_regen_rate": self.shield_regen_rate, "lifesteal": self.lifesteal, "poison_damage": self.poison_damage, "zone_resistance": self.zone_resistance, "health_regen_rate": self.health_regen_rate,
            "damage_growth": self.damage_growth, "hp": self.hp, "shield": self.shield
        }

    def to_winner_dict(self) -> dict[str, any]:
        return {
            "index": self.index, "kills": self.kills, "shots_hit": self.shots_hit, "shots_fired": self.shots_fired, "total_damage": self.total_damage,
            "num_common_picked": self.num_common_picked, "num_uncommon_picked": self.num_uncommon_picked, "num_rare_picked": self.num_rare_picked, "num_legendary_picked": self.num_legendary_picked
        }

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
        self.powerup_popup_create_time = time()

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

    def add_poison(self, parent: any, poison_damage: int, poison_lifesteal: float, duration: float = POISON_DURATION) -> None:
        self.poisons.append(Poison(parent, self.take_damage, self.on_poison_end, poison_damage, duration, poison_lifesteal))

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

    def shoot(self) -> bool:
        if time() - self.last_shoot_time >= 1 / self.firerate:
            self.last_shoot_time = time()

            match self.rotation:
                case 0: bullet_vel = [0, -self.max_speed * (self.bullet_speed + 1) / 2.5]
                case 90: bullet_vel = [-self.max_speed * (self.bullet_speed + 1) / 2.5, 0]
                case 180: bullet_vel = [0, self.max_speed * (self.bullet_speed + 1) / 2.5]
                case 270: bullet_vel = [self.max_speed * (self.bullet_speed + 1) / 2.5, 0]

            self.bullets.append(Bullet(self, self.x, self.y, bullet_vel, self.damage, self.damage_growth, self.poison_damage, self.penetration, self.lifesteal, self.bullet_img))
            self.shots_fired += 1
            return True
        return False

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

    def ai_move(self, dt: float, wall_positions: tuple[float], wall_distances: tuple[float], closest_powerup: Powerup | None, closest_player: Player | None, closest_bullet: Bullet | None) -> None:
        player_dist = 10000

        if closest_powerup is not None:
            powerup_dist = obj_dist(closest_powerup, self)
        if closest_player is not None:
            player_dist = obj_dist(closest_player, self)
        if closest_bullet is not None:
            bullet_dist = obj_dist(closest_bullet, self)

        for i, wall_distance in enumerate(wall_distances):
            if abs(wall_distance) > 0.005: continue

            match i:
                case 0:
                    self.move_left(dt)
                    self.target = (randint(wall_positions[0], wall_positions[1]), self.y)
                case 1:
                    self.move_right(dt)
                    self.target = (randint(wall_positions[0], wall_positions[1]), self.y)
                case 2:
                    self.move_up(dt)
                    self.target = (self.x, randint(wall_positions[2], wall_positions[3]))
                case 3:
                    self.move_down(dt)
                    self.target = (self.x, randint(wall_positions[2], wall_positions[3]))
            return

        if player_dist < 1000:
            self.fight_player(dt, closest_player)
        elif closest_powerup is not None and sum([int(wall_distance > 0.015) for wall_distance in wall_distances]) == 4:
            self.move_to(closest_powerup.x, closest_powerup.y, dt)
        else:
            self.move_to(self.target[0], self.target[1], dt)

            if dist((self.x, self.y), self.target) < 40:
                self.target = (randint(wall_positions[0], wall_positions[1]), randint(wall_positions[2], wall_positions[3]))

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
        screen.blit(self.name_surf, (self.x - screen_rect.x - 100, self.y - screen_rect.y - 60))

        if self.showing_powerup_popup and draw_parent is self and self.is_player:
            if time() - self.powerup_popup_create_time > 3:
                self.showing_powerup_popup = False
            else:
                screen.blit(self.powerup_popup, (screen.width // 2 - self.powerup_popup.width // 2, screen.height - self.powerup_popup.height))