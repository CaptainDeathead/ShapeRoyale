import pygame as pg
import pygame_gui


class Leaderboard:
    def __init__(self, display_surf: pg.Surface, manager: pygame_gui.UIManager, players: list[dict[str, any]]) -> None:
        self.display_surf = display_surf
        self.manager = manager
        self.players = players

        self.window = pygame_gui.elements.UIWindow(pg.Rect(display_surf.width // 2 - 300, display_surf.height // 2 - 250, 600, 500), self.manager, "Leaderboard")
    
        for i, player in enumerate(self.players):
            name_panel = pygame_gui.elements.UIPanel(pg.Rect(0, i*40, 600/3, 40), manager=self.manager, container=self.window, parent_element=self.window)
            name_lbl = pygame_gui.elements.UILabel(pg.Rect(0, 0, -1, -1), player.get("name", player.get("player_name", "N/A")), self.manager, name_panel, name_panel, anchors={"centery": "centery"})

            kills_panel = pygame_gui.elements.UIPanel(pg.Rect(600/3, i*40, 600/3, 40), manager=self.manager, container=self.window, parent_element=self.window)
            kills_lbl = pygame_gui.elements.UILabel(pg.Rect(0, 0, -1, -1), f"Kills: {player.get("kills", 0)}", self.manager, kills_panel, kills_panel, anchors={"centery": "centery"})
            acc_lbl = pygame_gui.elements.UILabel(pg.Rect(0, 0, -1, -1), f"ORB: {player.get("num_common_picked", 0) + player.get("num_uncommon_picked", 0)*1.257 + player.get("num_rare_picked", 0)*1.257*1.75 + player.get("num_legendary_picked", 0)*1.257*1.75*20:.0f}", self.manager, kills_panel, kills_panel, anchors={'center': 'center'})
            shots_lbl = pygame_gui.elements.UILabel(pg.Rect(0, 0, -1, -1), f"DMG: {player.get("damage", 0)}", self.manager, kills_panel, kills_panel, anchors={"left": "right", "centery": "centery"})

            squad_list = pygame_gui.elements.UIDropDownMenu(player.get("squad", [player.get("name", player.get("player_name", "N/A"))]), player.get("name", player.get("player_name", "N/A")), pg.Rect(600/3*2, i*40, 600/3, 40), self.manager, self.window, self.window)