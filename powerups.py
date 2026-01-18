import pygame as pg

from utils import FONTS_PATH

from ast import literal_eval
from random import choice
from time import time
from typing import List, Tuple, Dict

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
            if self.parent is not None:
                self.parent.give_lifesteal(self.damage * self.lifesteal)

            if self.duration <= 0: self.on_poison_end(self)

class Powerup:
    WIDTH = 50
    HEIGHT = 50

    def __init__(self, x: int, y: int, rarity: str, powerup_info: Dict[str, Dict], on_pickup: object, index: int, name: str = "") -> None:
        self.x = x
        self.y = y
        self.index = index

        self.rarity = rarity
        self.name = choice(list(powerup_info[rarity]["types"])) if name == "" else name
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

    def to_dict(self) -> dict[str, any]:
        return {
            "x": self.x, "y": self.y,
            "rarity": self.rarity, "index": self.index, "name": self.name 
        }

    def render_popup(self) -> pg.Surface:
        title_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=40)
        blurb_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=25)
        description_font = pg.font.Font(f"{FONTS_PATH}/PressStart2P.ttf", size=20)

        rect_w, rect_h = 700, 400
        surface = pg.Surface((rect_w, rect_h), pg.SRCALPHA)
        surface.set_alpha(200)

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

        match self.rarity:
            case "Common": player.num_common_picked += 1
            case "Uncommon": player.num_uncommon_picked += 1
            case "Rare": player.num_rare_picked += 1
            case "Legendary": player.num_legendary_picked += 1

        player.show_powerup_popup(self.render_popup())
        self.on_pickup(self)