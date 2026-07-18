import pygame as pg

from joystick import TouchJoystick

# Initialize Pygame
pg.init()

# Set up the display
screen = pg.display.set_mode((400, 400))
pg.display.set_caption('Joystick test')

clock = pg.time.Clock()

joystick = TouchJoystick(screen)

running = True
while running:
    clock.tick(60)

    fingermotion_events = []
    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False
        elif event.type == pg.FINGERMOTION:
            finger_x = event.x
            finger_y = event.y
            finger_id = event.finger_id
            fingermotion_events.append((finger_x, finger_y, finger_id))

    finger_x, finger_y = pg.mouse.get_pos()
    fingermotion_events.append((finger_x, finger_y, 0))

    screen.fill(0)

    joystick.draw(fingermotion_events)

    pg.display.flip()

# Quit pg
pg.quit()
