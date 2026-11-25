"""Procedural art: neon food, smooth snakes, arena camera, radar and particles."""
from collections import deque
from functools import lru_cache
import math
import random
import time
import pygame
from common.config import RADIUS, WORLD_SIZE
from client.widgets import text, panel, TEXT, MUTED, ACCENT

# ── Premium Color Palette ──────────────────────────
DEEP_SPACE    = (4,  8,  18)
SPACE_BLUE    = (8,  17, 32)
GRID_MAJOR    = (16, 30, 46)
GRID_MINOR    = (11, 21, 33)
BORDER_GLOW   = (100, 28, 58)
BORDER_MAIN   = (205, 58, 108)
BORDER_BRIGHT = (238, 128, 162)
ARENA_OUTSIDE = (24, 8,  22)


@lru_cache(maxsize=64)
def rgb(value):
    return tuple(pygame.Color(value))[:3]


@lru_cache(maxsize=512)
def glow(color, radius):
    s = pygame.Surface((radius*2+4, radius*2+4), pygame.SRCALPHA)
    cx = cy = radius+2
    for r in range(radius, 0, -1):
        t = 1.0 - r/radius
        a = int(105 * t**2.5)
        pygame.draw.circle(s, (*color, a), (cx,cy), r)
    return s


def halo(surface, point, color, radius):
    surface.blit(glow(color, radius), (int(point[0] - radius - 1), int(point[1] - radius - 1)))


def _lerp_angle(start, end, alpha):
    delta = (end - start + math.pi) % math.tau - math.pi
    return start + delta * alpha


def _draw_snake_eyes(surface, head, angle, radius):
    """Mắt rắn neon: viền trắng + tròng đen + điểm sáng specular."""
    forward = (math.cos(angle), math.sin(angle))
    side = (-forward[1], forward[0])
    eye_r   = max(3, int(radius * 0.37))
    pupil_r = max(2, int(radius * 0.21))
    hx, hy = head
    for sign in (-1, 1):
        px = hx + forward[0]*radius*0.44 + side[0]*radius*0.48*sign
        py = hy + forward[1]*radius*0.44 + side[1]*radius*0.48*sign
        ep = (int(px), int(py))
        pygame.draw.circle(surface, (180,230,215), ep, eye_r+1)   # rim
        pygame.draw.circle(surface, (244,255,253), ep, eye_r)      # white
        pp = (int(px+forward[0]*2.5), int(py+forward[1]*2.5))
        pygame.draw.circle(surface, (6,15,24), pp, pupil_r)        # pupil
        sp = (pp[0]-max(1,pupil_r//2), pp[1]-max(1,pupil_r//2))
        pygame.draw.circle(surface, (200,255,235), sp, max(1,pupil_r//3))  # specular


def snake_art(surface, points, color, angle, radius=RADIUS, boosting=False, shield=False, now=0.0):
    if not points:
        return
    c   = rgb(color) if isinstance(color, str) else color
    dark      = tuple(int(v*0.55) for v in c)
    mid       = tuple(int(v*0.78) for v in c)
    highlight = tuple(min(255, int(v*0.52+112)) for v in c)
    rim       = tuple(min(255, int(v*0.38+55))  for v in c)
    w, h = surface.get_size()
    n = len(points)

    # ── 1. Shadow pass ────────────────────────────────────────
    for i in range(n-1, -1, -1):
        px, py = points[i]
        if -80 < px < w+80 and -80 < py < h+80:
            taper = min(1.0, 0.44+(n-i)/9)
            r = max(4, round(radius*taper))
            pygame.draw.circle(surface, (1,4,10), (round(px+2),round(py+5)), r+3)

    # ── 2. Connector lines (smooth body) ─────────────────────
    if n >= 2:
        int_pts = [(round(x),round(y)) for x,y in points]
        for i in range(n-1):
            taper = min(1.0, 0.44+(n-i)/9)
            r = max(4, round(radius*taper))
            pygame.draw.line(surface, dark, int_pts[i], int_pts[i+1], max(2,round(r*1.9)))
        for i in range(n-1):
            taper = min(1.0, 0.44+(n-i)/9)
            r = max(4, round(radius*taper))
            sc = c if (i//3)%2==0 else mid
            pygame.draw.line(surface, sc, int_pts[i], int_pts[i+1], max(2,round(r*1.42)))

    # ── 3. Body circles ───────────────────────────────────────
    for i in range(n-1, -1, -1):
        px, py = points[i]
        if not (-80 < px < w+80 and -80 < py < h+80):
            continue
        taper = min(1.0, 0.44+(n-i)/9)
        r = max(4, round(radius*taper))
        p = (round(px), round(py))
        # Halo
        if i%2==0 or i==0:
            halo(surface, p, c, int(r*3.7) if boosting else int(r*2.2))
        # Layers
        pygame.draw.circle(surface, rim,                                 p, r+1)
        pygame.draw.circle(surface, c if (i//3)%2==0 else dark,        p, r)
        hx2 = p[0]-int(r*0.26); hy2 = p[1]-int(r*0.30)
        pygame.draw.circle(surface, highlight, (hx2,hy2), max(2,int(r*0.37)))
        pygame.draw.circle(surface, (255,255,255), (hx2,hy2), max(1,int(r*0.14)))

    # ── 4. Head glow ──────────────────────────────────────────
    halo(surface, (round(points[0][0]),round(points[0][1])), c,
         int(radius*4.2) if boosting else int(radius*2.9))

    # ── 5. Shield ─────────────────────────────────────────────
    hx, hy = int(points[0][0]), int(points[0][1])
    if shield:
        pulse = 3.5*math.sin(now*10) if now else 0
        for d, lw in ((12+pulse,2),(7+pulse*0.5,2),(2,1)):
            pygame.draw.circle(surface, c, (hx,hy), max(1,int(radius+d)), lw)

    # ── 6. Eyes ───────────────────────────────────────────────
    _draw_snake_eyes(surface, points[0], angle, radius)


class Backdrop:
    def __init__(self):
        # Cache toàn bộ nền tĩnh — chỉ tính 1 lần
        self.surface = pygame.Surface((1280, 800))
        # Gradient từng dòng
        for y in range(800):
            t = y / 800
            r = int(DEEP_SPACE[0] + (SPACE_BLUE[0]-DEEP_SPACE[0])*t)
            g = int(DEEP_SPACE[1] + (SPACE_BLUE[1]-DEEP_SPACE[1])*t)
            b = int(DEEP_SPACE[2] + (SPACE_BLUE[2]-DEEP_SPACE[2])*t + 15*t*(1-t))
            pygame.draw.line(self.surface, (r,g,b), (0,y),(1280,y))
        # Grid minor 20px
        for x in range(0,1280,20):
            c = GRID_MAJOR if x%60==0 else GRID_MINOR
            pygame.draw.line(self.surface, c, (x,0),(x,800))
        for y in range(0,800,20):
            c = GRID_MAJOR if y%60==0 else GRID_MINOR
            pygame.draw.line(self.surface, c, (0,y),(1280,y))
        # Floating stars
        rng = random.Random(77)
        self.stars = [(rng.randrange(1280), rng.randrange(800),
                       rng.random()*math.tau, rng.uniform(0.4,1.1),
                       rng.randint(40,90)) for _ in range(55)]
        # Vignette
        self.vignette = pygame.Surface((1280,800), pygame.SRCALPHA)
        depth = 90
        for i in range(depth):
            a = int(160*(1-i/depth)**2)
            self.vignette.fill((0,0,0,a), pygame.Rect(0,i,1280,1))             # top
            self.vignette.fill((0,0,0,a), pygame.Rect(0,799-i,1280,1))         # bottom
            self.vignette.fill((0,0,0,a), pygame.Rect(i,0,1,800))              # left
            self.vignette.fill((0,0,0,a), pygame.Rect(1279-i,0,1,800))         # right

    def draw(self, surface, now):
        surface.blit(self.surface, (0,0))
        for x, y, phase, speed, bmax in self.stars:
            a = int(bmax*(0.55 + 0.45*math.sin(now*speed+phase)))
            c = min(255,a+40)
            pygame.draw.circle(surface, (a//2, a, c), (x,y), 1)
        surface.blit(self.vignette, (0,0))


class WorldRenderer:
    def __init__(self):
        self.states = deque(maxlen=8)
        self.camera = None
        self.particles = []
        self.last_alive = {}
        self.rng = random.Random(42)
        self.me_screen = (640, 400)
        self.shake = [0.0, 0.0]
        self.shake_timer = 0.0

    def push(self, state):
        for s in state["snakes"]:
            if not s["alive"] and self.last_alive.get(s["id"], False):
                color = rgb(s["color"])
                for p in s["body"][::2]:
                    for _ in range(2):
                        self.particles.append([
                            p[0], p[1],
                            self.rng.uniform(-100, 100), self.rng.uniform(-100, 100),
                            0.8, color,
                        ])
                self.shake = [random.uniform(-1,1)*5, random.uniform(-1,1)*5]
                self.shake_timer = 0.15
            self.last_alive[s["id"]] = s["alive"]
        if len(self.particles) > 250:
            self.particles = self.particles[-250:]
        self.states.append((state.get("_received", time.monotonic()), state))

    def interpolated(self, now):
        if not self.states:
            return None
        target = now - 0.10
        before = self.states[0]
        after = self.states[-1]
        for item in self.states:
            if item[0] <= target:
                before = item
            if item[0] >= target:
                after = item
                break
        a, b = before[1], after[1]
        alpha = max(0, min(1, (target - before[0]) / max(0.001, after[0] - before[0])))
        old = {s["id"]: s for s in a["snakes"]}
        snakes = []
        for s in b["snakes"]:
            p = old.get(s["id"])
            if (
                p and p["alive"] and s["alive"] and p["body"] and s["body"]
                and abs(p["body"][0][0] - s["body"][0][0]) < 150
                and abs(p["body"][0][1] - s["body"][0][1]) < 150
            ):
                body = [
                    (
                        p["body"][min(i, len(p["body"]) - 1)][0] * (1 - alpha) + xy[0] * alpha,
                        p["body"][min(i, len(p["body"]) - 1)][1] * (1 - alpha) + xy[1] * alpha,
                    )
                    for i, xy in enumerate(s["body"])
                ]
                snakes.append({**s, "body": body, "angle": _lerp_angle(p["angle"], s["angle"], alpha)})
            else:
                snakes.append(s)
        return {**b, "snakes": snakes}

    def world_to_screen(self, point):
        cx, cy = self.camera
        return (point[0] - cx + 640, point[1] - cy + 400)

    def draw(self, surface, now, dt, pid):
        world = self.interpolated(now)
        surface.fill(SPACE_BLUE)
        if not world:
            text(surface, "Đang đồng bộ đấu trường…", (640, 400), 24, anchor="center")
            return None

        me = next((s for s in world["snakes"] if s["id"] == pid), None)
        if me and me["body"]:
            # Camera nhìn trước (Look-ahead) theo hướng di chuyển và trạng thái boost
            lead = 65 if me["boost"] else 35
            hx, hy = me["body"][0]
            target = (hx + math.cos(me["angle"]) * lead, hy + math.sin(me["angle"]) * lead)
        else:
            target = self.camera if self.camera is not None else (WORLD_SIZE / 2, WORLD_SIZE / 2)

        if self.camera is None or (me and me["shield"] > 1.8):
            self.camera = list(me["body"][0] if (me and me["body"]) else target)

        safe_dt = min(max(dt, 0.0), 0.1)
        factor = 1 - math.exp(-7 * safe_dt)
        self.camera = [a + (b - a) * factor for a, b in zip(self.camera, target)]
        cx, cy = self.camera

        # Camera shake
        if self.shake_timer > 0:
            safe_dt_shake = min(dt if dt > 0 else 0.016, 0.1)
            self.shake_timer -= safe_dt_shake
            cx += self.shake[0]
            cy += self.shake[1]

        screen = self.world_to_screen

        # Grid — major and minor lines
        for x in range(int((cx - 640) // 60) * 60, int(cx + 700), 60):
            xx = round(x - cx + 640)
            pygame.draw.line(surface, (22,40,56), (xx, 0), (xx, 800))
        for x in range(int((cx - 640) // 20) * 20, int(cx + 700), 20):
            if x % 60 != 0:
                xx = round(x - cx + 640)
                pygame.draw.line(surface, (13,24,35), (xx, 0), (xx, 800))
        for y in range(int((cy - 400) // 60) * 60, int(cy + 460), 60):
            yy = round(y - cy + 400)
            pygame.draw.line(surface, (22,40,56), (0, yy), (1280, yy))
        for y in range(int((cy - 400) // 20) * 20, int(cy + 460), 20):
            if y % 60 != 0:
                yy = round(y - cy + 400)
                pygame.draw.line(surface, (13,24,35), (0, yy), (1280, yy))

        # World border and shaded outside area
        arena_rect = pygame.Rect(round(640 - cx), round(400 - cy), WORLD_SIZE, WORLD_SIZE)
        for rect in [
            pygame.Rect(0, 0, max(0, arena_rect.left), 800),
            pygame.Rect(0, 0, 1280, max(0, arena_rect.top)),
            pygame.Rect(max(0, arena_rect.right), 0, max(0, 1280 - arena_rect.right), 800),
            pygame.Rect(0, max(0, arena_rect.bottom), 1280, max(0, 800 - arena_rect.bottom)),
        ]:
            pygame.draw.rect(surface, ARENA_OUTSIDE, rect)
        pygame.draw.rect(surface, BORDER_GLOW,   arena_rect, 10, border_radius=6)
        pygame.draw.rect(surface, BORDER_MAIN,   arena_rect,  3, border_radius=5)
        pygame.draw.rect(surface, BORDER_BRIGHT, arena_rect,  1, border_radius=4)

        for _, x, y, value, color in world["food"]:
            px, py = screen((x, y))
            if -25 < px < 1305 and -25 < py < 825:
                c = rgb(color)
                r = 3 if value == 1 else 6
                pulse_f = math.sin(now*4.5+(x+y)*0.05)
                halo_r  = int((18 if value==1 else 28) + pulse_f*(2 if value==1 else 4))
                halo(surface, (px,py), c, halo_r)
                bright = tuple(min(255,v+65) for v in c)
                pygame.draw.circle(surface, bright, (round(px),round(py)), r+1)
                pygame.draw.circle(surface, c, (round(px),round(py)), r)
                inner = tuple(min(255,int(v*0.5+132)) for v in c)
                pygame.draw.circle(surface, inner, (round(px),round(py)), max(1,r-1))
                pygame.draw.circle(surface, (238,255,250), (round(px)-1,round(py)-1), max(1,r//3))

        for s in sorted(world["snakes"], key=lambda s: s["id"] == pid):
            if not s["alive"]:
                continue
            # Sinh hạt hiệu ứng bứt tốc thuần phía client
            if s["boost"] and len(s["body"]) > 1 and self.rng.random() < 0.45:
                tail = s["body"][-1]
                self.particles.append([
                    tail[0], tail[1],
                    self.rng.uniform(-35, 35), self.rng.uniform(-35, 35),
                    0.35, rgb(s["color"]),
                ])
            points = [screen(p) for p in s["body"]]
            snake_art(surface, points, s["color"], s["angle"], boosting=s["boost"], shield=s["shield"] > 0, now=now)
            x, y = points[0]
            if -60 < x < 1340 and -60 < y < 860:
                text(
                    surface,
                    s["name"] + (" · BOT" if s["bot"] else ""),
                    (x, y - 31),
                    12,
                    ACCENT if s["id"] == pid else TEXT,
                    True,
                    "midbottom",
                )
            if s["id"] == pid:
                self.me_screen = points[0]

        if len(self.particles) > 300:
            self.particles = self.particles[-300:]

        keep = []
        for p in self.particles:
            p[0] += p[2] * safe_dt
            p[1] += p[3] * safe_dt
            p[4] -= safe_dt
            if p[4] > 0:
                keep.append(p)
                pt = screen(p)
                if -10 < pt[0] < 1290 and -10 < pt[1] < 810:
                    pygame.draw.circle(surface, p[5], (round(pt[0]), round(pt[1])), max(1, int(p[4] * 4)))
        self.particles = keep
        return world

    def radar(self, surface, world, pid, rect):
        x, y, w, h = rect
        # SRCALPHA radar surface with rounded fill
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (10,20,32,210), (0,0,w,h), border_radius=16)
        # Grid lines (2 horizontal, 2 vertical)
        for i in (1, 2):
            lx = int(i * w / 3)
            ly = int(i * h / 3)
            pygame.draw.line(surf, (20,38,55,180), (lx,0), (lx,h))
            pygame.draw.line(surf, (20,38,55,180), (0,ly), (w,ly))
        # Player markers
        for s in world["snakes"]:
            if s["alive"]:
                p = s["body"][0]
                pt = (round(p[0] / WORLD_SIZE * w), round(p[1] / WORLD_SIZE * h))
                if s["id"] == pid:
                    # Player: halo + circle
                    for ra in range(8, 0, -1):
                        ta = int(60 * (1 - ra/8) ** 2)
                        pygame.draw.circle(surf, (*ACCENT, ta), pt, ra)
                    pygame.draw.circle(surf, ACCENT, pt, 5)
                else:
                    pygame.draw.circle(surf, (255,110,150), pt, 3)
        surface.blit(surf, (x, y))
        # Label
        text(surface, "BẢN ĐỒ", (x + 16, y + 13), 11, MUTED, True)
