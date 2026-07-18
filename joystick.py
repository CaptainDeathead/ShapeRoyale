import pygame as pg

class TouchJoystick:
    OUTER_JOY_COLOR = pg.Color(255, 255, 255, 64)
    INNER_JOY_COLOR = pg.Color(255, 255, 255, 128)

    def __init__(self, screen: pg.Surface, pos: tuple[int, int]) -> None:
        self.screen = screen

        self.outer_joy_rad = 150
        self.inner_joy_rad = 50

        self.surface_pos = pos

        self.surface = pg.Surface((self.outer_joy_rad * 2 + self.inner_joy_rad * 6, self.outer_joy_rad * 2 + self.inner_joy_rad * 6), pg.SRCALPHA)

        self.joy_pos = (self.surface.width // 2, self.surface.height // 2)
        self.inner_joy_offset = pg.Vector2(0, 0)

        self.bounding_rect = pg.Rect(self.surface_pos[0] - self.surface.width // 2, self.surface_pos[1] - self.surface.height // 2, self.surface.width, self.surface.height)

    @property
    def joy_x(self) -> float:
        # Percent of joy_x (-1.0 to 1.0)
        return self.inner_joy_offset[0] / self.outer_joy_rad

    @property
    def joy_y(self) -> float:
        # Percent of joy_y (-1.0 to 1.0)
        return self.inner_joy_offset[1] / self.outer_joy_rad

    @property
    def joy_angle(self) -> float:
        # Angle in degrees of joystick rotation
        return self.inner_joy_offset.angle

    def draw(self, fingermotion_events: list[tuple[int, int, int]]) -> None:
        self.inner_joy_offset = (0, 0)
        alpha = 64

        for finger_x, finger_y, finger_id in fingermotion_events:
            finger_pos = (finger_x, finger_y)

            if self.bounding_rect.collidepoint(finger_pos):
                raw_inner_joy_offset = pg.Vector2(finger_pos[0] - self.bounding_rect.centerx, finger_pos[1] - self.bounding_rect.centery)

                if raw_inner_joy_offset.length() > self.surface.width // 2: continue

                self.inner_joy_offset = raw_inner_joy_offset
                alpha = 256

                if self.inner_joy_offset.length() > self.outer_joy_rad:
                    self.inner_joy_offset.scale_to_length(self.outer_joy_rad)

        self.surface.fill(0)
        self.surface.set_alpha(alpha)

        pg.draw.circle(self.surface, self.OUTER_JOY_COLOR, self.joy_pos, self.outer_joy_rad)
        pg.draw.circle(self.surface, self.INNER_JOY_COLOR, (self.joy_pos[0] + self.inner_joy_offset[0], self.joy_pos[1] + self.inner_joy_offset[1]), self.inner_joy_rad)

        self.screen.blit(self.surface, self.bounding_rect)