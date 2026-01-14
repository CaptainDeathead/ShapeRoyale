import pygame as pg

from math import dist
from typing import List

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

    @property
    def health_damage(self) -> float:
        if self.damage_growth == 1.0: # Default
            # No bullet growth
            health_damage = self.base_damage
        else:
            health_damage = self.base_damage * (self.damage_growth * self.distance_travelled / 400.0)

        return health_damage

    def move(self, dt: float) -> None:
        self.x += self.velocity[0] * dt * 10
        self.y += self.velocity[1] * dt * 10

    def draw(self, screen: pg.Surface, draw_parent: any) -> None:
        screen_rect = pg.Rect(draw_parent.x - screen.width // 2 + self.image.width // 2, draw_parent.y - screen.height // 2 + self.image.height // 2, screen.width, screen.height)

        if not pg.Rect(self.x - self.image.width // 2, self.y - self.image.height // 2, self.image.width, self.image.height).colliderect(screen_rect): return

        #screen.blit(self.image, (self.x - self.image.width // 2 - screen_rect.x, self.y - self.image.height // 2 - screen_rect.y))
        pg.draw.circle(screen, (255, 255, 0), (self.x - screen_rect.x, self.y - screen_rect.y), self.health_damage / 1.75)

    def hit(self, target: any) -> None:
        health_damage = self.health_damage
        shield_damage = health_damage * self.penetration

        target.take_damage(health_damage)
        target.take_shield_damage(shield_damage)

        if self.poison_damage > 0:
            target.add_poison(self.parent, self.poison_damage, (self.lifesteal - 1))

        self.parent.give_lifesteal(health_damage * (self.lifesteal - 1))