"""Small immediate-mode UI kit with cached type, clipped text and UTF-8 inputs."""
from functools import lru_cache
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parents[1]
BG = (9, 16, 25)
PANEL = (16, 27, 39)
EDGE = (39, 56, 70)
TEXT = (233, 244, 248)
MUTED = (133, 158, 178)
ACCENT = (84, 232, 176)
RED = (255, 121, 157)


@lru_cache(maxsize=32)
def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return pygame.font.Font(str(ROOT/"assets"/"fonts"/name), size)


def text(surface, value, pos, size=18, color=TEXT, bold=False, anchor="topleft", max_width=None):
    value = str(value)
    f = font(size, bold)
    if max_width and f.size(value)[0] > max_width:
        while value and f.size(value+"…")[0] > max_width:
            value = value[:-1]
        value += "…"
    image = f.render(value, True, color)
    rect = image.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(image, rect)
    return rect


def panel(surface, rect, fill=PANEL, radius=20, border=EDGE):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)
    return rect


def pill(surface, label, pos, color=ACCENT):
    width = font(12, True).size(label)[0]+22
    rect = pygame.Rect(pos[0], pos[1], width, 28)
    panel(surface, rect, tuple(int(c*.15) for c in color), 14, tuple(int(c*.32) for c in color))
    text(surface, label, rect.center, 12, color, True, "center")


class Input:
    def __init__(self, label, value="", password=False, limit=32):
        self.label, self.value, self.password, self.limit = label, value, password, limit
        self.active = False
        self.rect = pygame.Rect(0,0,0,0)

    def event(self, e, point):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(point)
        if not self.active:
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]
        elif e.type == pygame.TEXTINPUT:
            self.value = (self.value+"".join(c for c in e.text if c.isprintable()))[:self.limit]

    def draw(self, surface, rect):
        self.rect = pygame.Rect(rect)
        text(surface, self.label, (rect[0], rect[1]-23), 13, MUTED)
        panel(surface, rect, (10,20,30), 10, ACCENT if self.active else EDGE)
        value = "•"*len(self.value) if self.password else self.value
        while value and font(16).size(value)[0] > rect[2]-34:
            value = value[1:]
        text(surface, value, (rect[0]+14, rect[1]+rect[3]/2), 16, TEXT, anchor="midleft")
        if self.active and pygame.time.get_ticks()%1000 < 520:
            x = rect[0]+16+font(16).size(value)[0]
            pygame.draw.line(surface, ACCENT, (x,rect[1]+13),(x,rect[1]+rect[3]-13),2)


class Buttons:
    def __init__(self):
        self.items = []
        self.mouse = (0,0)

    def begin(self, mouse):
        self.items = []
        self.mouse = mouse

    def draw(self, surface, label, rect, callback, primary=False, enabled=True, danger=False):
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(self.mouse)
        color = RED if danger else ACCENT
        fill = color if primary else ((31,51,65) if hover else (23,37,51))
        if not enabled:
            fill = (25,34,43)
        panel(surface, rect, fill, 11, None if primary else (color if hover else EDGE))
        text(surface, label, rect.center, 15, BG if primary else (TEXT if enabled else MUTED), True, "center", rect.w-18 if rect.w>=42 else None)
        self.items.append((rect, callback, enabled))

    def click(self, point):
        for rect, callback, enabled in reversed(self.items):
            if enabled and rect.collidepoint(point):
                callback()
                return True
        return False
