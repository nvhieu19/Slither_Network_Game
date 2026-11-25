"""Procedural art: neon food, smooth snakes, arena camera, radar and particles."""
from collections import deque
from functools import lru_cache
import math
import random
import time
import pygame
from common.config import RADIUS, WORLD_SIZE
from client.widgets import text, panel, TEXT, MUTED, ACCENT


@lru_cache(maxsize=64)
def rgb(value):
    return tuple(pygame.Color(value))[:3]


@lru_cache(maxsize=256)
def glow(color, radius):
    """Vòng sáng neon nhiều lớp - mỗi layer mỏng hơn, alpha tăng dần vào giữa."""
    size = radius * 2 + 4
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = radius + 2
    for r in range(radius, 0, -1):
        t = 1.0 - r / radius          # 0 ở viền ngoài → 1 ở tâm
        alpha = int(90 * t * t * t)   # cubic fall-off → ánh sáng tập trung ở giữa
        pygame.draw.circle(surface, (*color, alpha), (cx, cy), r)
    return surface


def halo(surface, point, color, radius):
    surface.blit(glow(color, radius), (int(point[0] - radius - 1), int(point[1] - radius - 1)))


def _lerp_angle(start, end, alpha):
    delta = (end - start + math.pi) % math.tau - math.pi
    return start + delta * alpha


def _draw_snake_eyes(surface, head, angle, radius):
    """Mắt rắn neon: viền trắng + tròng đen + điểm sáng specular."""
    forward = (math.cos(angle), math.sin(angle))
    side = (-forward[1], forward[0])
    eye_r = max(3, int(radius * 0.34))
    pupil_r = max(2, int(radius * 0.19))
    for sign in (-1, 1):
        px = head[0] + forward[0] * radius * 0.46 + side[0] * radius * 0.47 * sign
        py = head[1] + forward[1] * radius * 0.46 + side[1] * radius * 0.47 * sign
        p = (int(px), int(py))
        # Viền ngoài mắt
        pygame.draw.circle(surface, (200, 240, 230), p, eye_r + 1)
        # Lòng trắng
        pygame.draw.circle(surface, (244, 255, 253), p, eye_r)
        # Con ngươi (tròng đen)
        pupil = (int(px + forward[0] * 2.5), int(py + forward[1] * 2.5))
        pygame.draw.circle(surface, (8, 18, 26), pupil, pupil_r)
        # Điểm sáng specular nhỏ trên con ngươi
        spec = (pupil[0] - max(1, pupil_r // 2), pupil[1] - max(1, pupil_r // 2))
        pygame.draw.circle(surface, (200, 255, 240), spec, max(1, pupil_r // 3))


def snake_art(surface, points, color, angle, radius=RADIUS, boosting=False, shield=False, now=0.0):
    if not points:
        return
    c = rgb(color) if isinstance(color, str) else color
    dark  = tuple(int(v * 0.55) for v in c)
    mid   = tuple(int(v * 0.80) for v in c)
    highlight = tuple(min(255, int(v * 0.55 + 110)) for v in c)
    rim       = tuple(min(255, int(v * 0.40 + 60))  for v in c)
    w, h = surface.get_size()
    n = len(points)

    # ── 1. Bóng đổ (shadow) toàn thân ──────────────────────────────────────
    for i in range(n - 1, -1, -1):
        px, py = points[i]
        if -80 < px < w + 80 and -80 < py < h + 80:
            taper = min(1.0, 0.42 + (n - i) / 9)
            r = max(4, round(radius * taper))
            pygame.draw.circle(surface, (1, 5, 10), (round(px + 2), round(py + 5)), r + 3)

    # ── 2. Đường nối mượt giữa các segment (anti-aliased line) ─────────────
    if len(points) >= 2:
        int_pts = [(round(p[0]), round(p[1])) for p in points]
        # Vẽ đường nền dày (body outline) trước
        for i in range(len(int_pts) - 1):
            taper = min(1.0, 0.42 + (n - i) / 9)
            lw = max(2, round(radius * taper * 1.9))
            pygame.draw.line(surface, dark, int_pts[i], int_pts[i + 1], lw)
        # Vẽ đường màu chính mỏng hơn ở trên
        for i in range(len(int_pts) - 1):
            taper = min(1.0, 0.42 + (n - i) / 9)
            lw = max(2, round(radius * taper * 1.45))
            seg_c = c if (i // 3) % 2 == 0 else mid
            pygame.draw.line(surface, seg_c, int_pts[i], int_pts[i + 1], lw)

    # ── 3. Vẽ từng đốt tròn (circles) chồng lên đường nối ──────────────────
    for i in range(n - 1, -1, -1):
        px, py = points[i]
        if not (-80 < px < w + 80 and -80 < py < h + 80):
            continue
        taper = min(1.0, 0.42 + (n - i) / 9)
        r = max(4, round(radius * taper))

        # Halo neon — dày hơn khi boost
        if i % 2 == 0 or i == 0:
            halo_r = int(r * 3.8) if boosting else int(r * 2.3)
            halo(surface, (px, py), c, halo_r)

        # Thân đốt: lớp rim tối → lớp màu chính → highlight
        pygame.draw.circle(surface, rim, (round(px), round(py)), r + 1)
        pygame.draw.circle(surface, c if (i // 3) % 2 == 0 else dark, (round(px), round(py)), r)

        # Highlight phản chiếu ánh sáng (góc trên-trái)
        hx = round(px - r * 0.26)
        hy = round(py - r * 0.30)
        pygame.draw.circle(surface, highlight, (hx, hy), max(2, int(r * 0.36)))
        # Specular nhỏ hơn ở trên highlight
        pygame.draw.circle(surface, (255, 255, 255), (hx, hy), max(1, int(r * 0.14)))

    # ── 4. Đầu rắn: shield + mắt ────────────────────────────────────────────
    head = points[0]
    if shield:
        pulse = round(3.0 * math.sin(now * 9)) if now else 0
        shield_r = radius + 11 + pulse
        # Hai vòng shield lồng nhau
        pygame.draw.circle(surface, (*c, 60), (int(head[0]), int(head[1])), shield_r + 4)
        pygame.draw.circle(surface, c, (int(head[0]), int(head[1])), shield_r + 4, 2)
        pygame.draw.circle(surface, c, (int(head[0]), int(head[1])), shield_r, 1)
    _draw_snake_eyes(surface, head, angle, radius)


class Backdrop:
    def __init__(self):
        self.surface = pygame.Surface((1280, 800))
        for y in range(800):
            t = y / 800
            pygame.draw.line(self.surface, (int(10 + 3 * t), int(18 + 7 * t), int(29 + 9 * t)), (0, y), (1280, y))
        for x in range(0, 1280, 48):
            pygame.draw.line(self.surface, (20, 32, 44), (x, 0), (x, 800))
        for y in range(0, 800, 48):
            pygame.draw.line(self.surface, (20, 32, 44), (0, y), (1280, y))
        rng = random.Random(33)
        self.stars = [(rng.randrange(1280), rng.randrange(800), rng.random() * math.tau) for _ in range(60)]

    def draw(self, surface, now):
        surface.blit(self.surface, (0, 0))
        for x, y, phase in self.stars:
            c = int(58 + 25 * math.sin(now * 0.7 + phase))
            pygame.draw.circle(surface, (c // 2, c, c + 15), (x, y), 1)


class WorldRenderer:
    def __init__(self):
        self.states = deque(maxlen=8)
        self.camera = None
        self.particles = []
        self.last_alive = {}
        self.rng = random.Random(42)
        self.me_screen = (640, 400)

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
        surface.fill((8, 17, 27))
        if not world:
            text(surface, "Đang đồng bộ đấu trường…", (640, 400), 24, anchor="center")
            return None

        me = next((s for s in world["snakes"] if s["id"] == pid), None)
        if me and me["body"]:
            # Camera nhìn trước (Look-ahead) theo hướng di chuyển và trạng thái boost (T1.3)
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
        screen = self.world_to_screen

        for x in range(int((cx - 640) // 60) * 60, int(cx + 700), 60):
            xx = round(x - cx + 640)
            pygame.draw.line(surface, (18, 33, 46), (xx, 0), (xx, 800))
        for y in range(int((cy - 400) // 60) * 60, int(cy + 460), 60):
            yy = round(y - cy + 400)
            pygame.draw.line(surface, (18, 33, 46), (0, yy), (1280, yy))

        # World border and shaded outside area.
        arena_rect = pygame.Rect(round(640 - cx), round(400 - cy), WORLD_SIZE, WORLD_SIZE)
        for rect in [
            pygame.Rect(0, 0, max(0, arena_rect.left), 800),
            pygame.Rect(0, 0, 1280, max(0, arena_rect.top)),
            pygame.Rect(max(0, arena_rect.right), 0, max(0, 1280 - arena_rect.right), 800),
            pygame.Rect(0, max(0, arena_rect.bottom), 1280, max(0, 800 - arena_rect.bottom)),
        ]:
            pygame.draw.rect(surface, (39, 16, 34), rect)
        pygame.draw.rect(surface, (186, 61, 107), arena_rect, 4)

        for _, x, y, value, color in world["food"]:
            px, py = screen((x, y))
            if -25 < px < 1305 and -25 < py < 825:
                c = rgb(color)
                r = 3 if value == 1 else 6
                # Nhịp thở — mồi thường nhịp nhẹ, mồi lớn nhịp rõ hơn
                pulse = math.sin(now * 4.5 + (x + y) * 0.05)
                halo_r = int((16 if value == 1 else 26) + pulse * (2 if value == 1 else 4))
                # Halo neon bên ngoài
                halo(surface, (px, py), c, halo_r)
                # Vòng sáng mỏng viền ngoài
                bright = tuple(min(255, v + 60) for v in c)
                pygame.draw.circle(surface, bright, (round(px), round(py)), r + 1)
                # Lõi mồi màu chính
                pygame.draw.circle(surface, c, (round(px), round(py)), r)
                # Lớp sáng bên trong (gradient thủ công)
                inner = tuple(min(255, int(v * 0.5 + 130)) for v in c)
                pygame.draw.circle(surface, inner, (round(px), round(py)), max(1, r - 1))
                # Điểm specular nhỏ
                pygame.draw.circle(surface, (240, 255, 252), (round(px - 1), round(py - 1)), max(1, r // 3))

        for s in sorted(world["snakes"], key=lambda s: s["id"] == pid):
            if not s["alive"]:
                continue
            # Sinh hạt hiệu ứng bứt tốc thuần phía client (T1.6)
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
        panel(surface, rect, (11, 23, 34), 16)
        x, y, w, h = rect
        text(surface, "BẢN ĐỒ", (x + 16, y + 13), 11, MUTED, True)
        inner = pygame.Rect(x + 18, y + 39, w - 36, h - 55)
        pygame.draw.rect(surface, (29, 48, 61), inner, 1, border_radius=4)
        for i in (1, 2):
            pygame.draw.line(surface, (23, 40, 53), (inner.x + i * inner.w / 3, inner.y), (inner.x + i * inner.w / 3, inner.bottom))
            pygame.draw.line(surface, (23, 40, 53), (inner.x, inner.y + i * inner.h / 3), (inner.right, inner.y + i * inner.h / 3))
        for s in world["snakes"]:
            if s["alive"]:
                p = s["body"][0]
                pt = (round(inner.x + p[0] / WORLD_SIZE * inner.w), round(inner.y + p[1] / WORLD_SIZE * inner.h))
                pygame.draw.circle(surface, ACCENT if s["id"] == pid else (255, 130, 156), pt, 4 if s["id"] == pid else 2)