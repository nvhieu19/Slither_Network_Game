# ==============================================================================
# Neon Slither - Bộ Widget & Form Controls
# Phụ trách: Trần Minh Hải (Thành viên 2 - Nhiệm vụ T2.2, T2.3)
# 
# Chi tiết công việc:
# - T2.2: Thiết kế nút bấm Neon, ô nhập liệu hỗ trợ gõ có dấu, kiểm tra độ dài
#         và định dạng hợp lệ của tài khoản/mật khẩu, điều hướng bằng phím Tab.
# - T2.3: Thành phần danh sách cuộn (ScrollableList) hỗ trợ hiển thị danh sách
#         phòng chơi, thanh cuộn mượt và chọn phòng nhanh.
# ==============================================================================
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
GLASS      = (12, 24, 38)
GLASS_EDGE = (38, 68, 92)
GOLD       = (255, 200, 80)

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


def glass_panel(surface, rect, alpha=200, radius=16, border=None):
    r = pygame.Rect(rect)
    s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*GLASS, alpha), (0,0,r.w,r.h), border_radius=radius)
    pygame.draw.line(s, (*GLASS_EDGE, 90), (radius,1), (r.w-radius,1))
    bc = border if border is not None else GLASS_EDGE
    pygame.draw.rect(s, (*bc, 155), (0,0,r.w,r.h), 1, border_radius=radius)
    surface.blit(s, r.topleft)
    return r


def progress_bar(surface, rect, value, max_val=1.0, color=None, label=None):
    if color is None: color = ACCENT
    r = pygame.Rect(rect)
    ratio = max(0.0, min(1.0, value/max_val if max_val > 0 else 0.0))
    pygame.draw.rect(surface, (20,35,52), r, border_radius=6)
    fw = max(0, int((r.w-2)*ratio))
    if fw > 0:
        fr = pygame.Rect(r.x+1, r.y+1, fw, r.h-2)
        pygame.draw.rect(surface, color, fr, border_radius=5)
        # highlight cạnh trên
        pygame.draw.line(surface, tuple(min(255,v+60) for v in color),
                         (fr.x+2,fr.y+1),(fr.right-2,fr.y+1))
    pygame.draw.rect(surface, (40,65,88), r, 1, border_radius=6)
    if label:
        text(surface, label, r.center, 11, MUTED, anchor="center")


def badge(surface, label, pos, color=ACCENT, size=11):
    f = font(size, True)
    w = f.size(label)[0]+14
    r = pygame.Rect(pos[0]-w//2, pos[1]-10, w, 20)
    pygame.draw.rect(surface, tuple(int(c*0.15) for c in color), r, border_radius=10)
    pygame.draw.rect(surface, tuple(int(c*0.35) for c in color), r, 1, border_radius=10)
    text(surface, label, r.center, size, color, True, "center")
    return r


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
        # Focus glow
        if self.active:
            gr = pygame.Rect(rect[0]-3, rect[1]-3, rect[2]+6, rect[3]+6)
            gs = pygame.Surface((gr.w, gr.h), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*ACCENT, 28), (0,0,gr.w,gr.h), border_radius=13)
            surface.blit(gs, gr.topleft)
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
        # Hover glow
        if hover and enabled:
            gs = pygame.Surface((rect.w+4, rect.h+4), pygame.SRCALPHA)
            pygame.draw.rect(gs, (255,255,255,14), (0,0,rect.w+4,rect.h+4), border_radius=13)
            surface.blit(gs, (rect.x-2, rect.y-2))
        # Primary highlight cạnh trên
        if primary and enabled:
            hl = tuple(min(255,v+55) for v in (ACCENT if not danger else RED))
            pygame.draw.line(surface, hl, (rect.x+12,rect.y+2),(rect.right-12,rect.y+2))
        self.items.append((rect, callback, enabled))

    def click(self, point):
        for rect, callback, enabled in reversed(self.items):
            if enabled and rect.collidepoint(point):
                callback()
                return True
        return False
