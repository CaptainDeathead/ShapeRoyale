import pygame as pg
import sys

#from sound import generate_sine_wave

from networking import Server, Client, BaseClient

from utils import FONTS_PATH
from shape import Player, Shape

from json import loads
from time import time

class MainMenu:
    TIMER_LENGTH = 1

    def __init__(self, display_surf: pg.Surface, server: Server | None, client: Client | None, player_name: str | None = None) -> None:
        self.display_surf = display_surf
        self.server = server
        self.client = client
        self.player_name = player_name

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


        if self.server is not None:
            self.player_info = {}
            for i in range(len(self.server.clients)):
                self.player_info[i] = {"ready": False, "name": "player"}


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
            if self.server is not None:
                self.server.sendall({"question": "send_starting_info"})

            if self.client is not None:
                server_ready = False
                while not server_ready:
                    self.clock.tick(60)

                    pg.display.flip()
                    for event in pg.event.get():
                        if event.type == pg.QUIT:
                            pg.quit()
                            sys.exit(0)

                        elif event.type == pg.KEYDOWN:
                            if event.key == pg.K_RETURN:
                                self.player.ready = not self.player.ready
                                return

                    self.client.send({"answer": {"ready": self.player.ready, "name": self.player_name}})

                    #print("waiting for data stream")
                    for message in self.client.base_client.data_stream:
                        for dtype, query in message.items():
                            if dtype == "question" and query == "send_starting_info":
                                self.client.send({"answer": {"send_starting_info": {"shape_index": self.player.shape_index, "name": self.player_name}}})
                                server_ready = True

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

        name_lbl = self.fonts["medium"].render(self.player_name, True, (255, 255, 255))
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
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit(0)
                
                elif event.type == pg.KEYDOWN:
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
                        #generate_sine_wave(800, 0.2, volume=0.15).play()
                        ...

                    self.last_timer_time = int(round(timer_time, 0))

                curr_time_int = max(0, min(int(round(timer_time, 0)), len(self.timer_end_lbls) - 1))
                self.display_surf.blit(self.timer_start_lbl, (self.width // 2 - self.timer_start_lbl.width // 2, self.height - 150))
                self.display_surf.blit(self.timer_end_lbls[curr_time_int-1], (self.width // 2 - self.timer_start_lbl.width // 2, self.height - 150))
            else:
                self.display_surf.blit(self.info_lbl, (self.width // 2 - self.info_lbl.width // 2, self.height - 150))

            if self.server is not None:
                for i, player_info in self.player_info.items():
                    player_ready, player_name = player_info.values()
                    self.display_surf.blit(self.fonts["small"].render(f"{player_name} - Ready: {player_ready}", True, (255, 255, 255)), (self.width // 2 + 300, self.height // 2 - 200 + (30 * i)))

                for i, client in enumerate(self.server.clients):
                    for message in client.data_stream:
                        for dtype, query in message.items():
                            if dtype != "answer":
                                continue

                            if "ready" in query:
                                self.player_info[i] = {"ready": query["ready"], "name": query["name"]}

            if self.client is not None:
                self.client.send({"answer": {"ready": self.player.ready, "name": self.player_name}})

            self.check_game_start()

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
                             self.small_font.render(f"{(winner.shots_hit / (winner.shots_fired + 0.00000000000000000001) * 100):.2f}% accuracy", True, (255, 255, 255))]

        self.info_lbl = self.medium_font.render   ("Press Enter to continue...", True, (255, 255, 255))
        self.info_lbl.blit(self.medium_font.render("      Enter", True, (0, 255, 0)))

    def draw(self) -> None:
        self.screen.fill(0)

        self.screen.blit(self.winner_lbl, (self.screen.width // 2 - self.winner_lbl.width // 2, 50))
        self.screen.blit(self.winner_sprite, (self.screen.width // 2 - self.winner_sprite.width // 2, 300))

        x = self.screen.width // 2 - self.powerup_stat_width // 2 + self.powerup_stat_spacing
        for i, stat in enumerate(self.powerup_stats):
            self.screen.blit(stat, (x, 800-25))
            pg.draw.circle(self.screen, [(0, 200, 0), (0, 0, 255), (150, 0, 255), (255, 215, 0)][i], (x - 30, 815-25), 20)
            x += stat.width + self.powerup_stat_spacing

        for i, stat in enumerate(self.winner_stats):
            self.screen.blit(stat, (self.screen.width // 2 + 200, 300 + 40 * i))

        self.screen.blit(self.info_lbl, (self.screen.width // 2 - self.info_lbl.width // 2, self.screen.height - 150))