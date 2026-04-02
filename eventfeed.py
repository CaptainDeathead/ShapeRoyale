import pygame as pg
from time import time

class GameEvent:
    LIFETIME = 5

    def __init__(self, text: str, color: pg.Color) -> None:
        self.text = text
        self.color = color
        self.creation_time = time()

class EventFeed:
    DEFAULT_SHIFT_SPEED = 100
    EVENT_HEIGHT = 20

    def __init__(self, screen: pg.Surface, font: pg.Font) -> None:
        self.screen = screen
        self.font = font

        self.event_queue = []
        self.x_shift = 0
        self.shift_speed = self.DEFAULT_SHIFT_SPEED

    def add(self, event: GameEvent) -> None:
        self.event_queue.append(event)

    def update(self, dt: float) -> None:
        self.x_shift = max(0, self.x_shift - self.shift_speed * dt)

        events_to_remove = []
        for i, event in enumerate(self.event_queue):
            if time() - event.creation_time > event.LIFETIME:
                events_to_remove.append(event)

            self.screen.blit(self.font.render(event.text, True, event.color), (5, 5 + i * self.EVENT_HEIGHT + self.x_shift))

        for event in events_to_remove:
            self.event_queue.remove(event)
            self.x_shift += self.EVENT_HEIGHT

            if self.x_shift > self.EVENT_HEIGHT:
                self.shift_speed += self.DEFAULT_SHIFT_SPEED
            else:
                self.shift_speed = self.DEFAULT_SHIFT_SPEED