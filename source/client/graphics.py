"""Procedural art: neon food, smooth snakes, arena camera, radar and particles."""
from collections import deque
from functools import lru_cache
import math
import random
import time
import pygame
from common.config import RADIUS, WORLD_SIZE
from client.widgets import text, panel, TEXT, MUTED, ACCENT


def rgb(value):
    return tuple(pygame.Color(value))[:3]


@lru_cache(maxsize=100)
def glow(color, radius):
    surface = pygame.Surface((radius*2+2, radius*2+2), pygame.SRCALPHA)
    for r in range(radius,0,-2):
        factor = (1-r/radius)**2
        pygame.draw.circle(surface, (*color, int(65*factor)), (radius+1,radius+1), r)
    return surface


def halo(surface, point, color, radius):
    surface.blit(glow(color,radius), (int(point[0]-radius-1),int(point[1]-radius-1)))


def snake_art(surface, points, color, angle, radius=RADIUS, boosting=False, shield=False):
    if not points:
        return
    c = rgb(color) if isinstance(color,str) else color
    dark = tuple(int(v*.65) for v in c)
    # Render the whole shadow first, so a segment never paints over its neighbour.
    for i in range(len(points)-1,-1,-1):
        p=points[i]
        if -70<p[0]<surface.get_width()+70 and -70<p[1]<surface.get_height()+70:
            r=max(4,round(radius*min(1,.45+(len(points)-i)/8)))
            pygame.draw.circle(surface,(2,7,13),(round(p[0]+2),round(p[1]+4)),r+2)
    for i in range(len(points)-1, -1, -1):
        p = (round(points[i][0]),round(points[i][1]))
        if not (-70 < p[0] < surface.get_width()+70 and -70 < p[1] < surface.get_height()+70):
            continue
        taper = min(1, .45+(len(points)-i)/8)
        r = max(4, round(radius*taper))
        if i%3 == 0 or i == 0:
            halo(surface,p,c,r*3 if boosting else r*2)
        pygame.draw.circle(surface, c if (i//3)%2==0 else dark, p,r)
        pygame.draw.circle(surface, tuple(min(255,int(v*.65+85)) for v in c),
                           (p[0]-int(r*.23),p[1]-int(r*.27)),max(2,int(r*.33)))
    head = points[0]
    if shield:
        pygame.draw.circle(surface, c, (int(head[0]),int(head[1])),radius+9,1)
    forward = (math.cos(angle),math.sin(angle))
    side = (-forward[1],forward[0])
    for sign in (-1,1):
        p = (head[0]+forward[0]*radius*.46+side[0]*radius*.47*sign,
             head[1]+forward[1]*radius*.46+side[1]*radius*.47*sign)
        pygame.draw.circle(surface,(244,255,253),(int(p[0]),int(p[1])),max(3,int(radius*.34)))
        pygame.draw.circle(surface,(11,25,34),(int(p[0]+forward[0]*2),int(p[1]+forward[1]*2)),max(2,int(radius*.17)))


class Backdrop:
    def __init__(self):
        self.surface = pygame.Surface((1280,800))
        for y in range(800):
            t = y/800
            pygame.draw.line(self.surface,(int(10+3*t),int(18+7*t),int(29+9*t)),(0,y),(1280,y))
        for x in range(0,1280,48):
            pygame.draw.line(self.surface,(20,32,44),(x,0),(x,800))
        for y in range(0,800,48):
            pygame.draw.line(self.surface,(20,32,44),(0,y),(1280,y))
        rng = random.Random(33)
        self.stars = [(rng.randrange(1280),rng.randrange(800),rng.random()*math.tau) for _ in range(60)]

    def draw(self, surface, now):
        surface.blit(self.surface,(0,0))
        for x,y,phase in self.stars:
            c = int(58+25*math.sin(now*.7+phase))
            pygame.draw.circle(surface,(c//2,c,c+15),(x,y),1)


class WorldRenderer:
    def __init__(self):
        self.states = deque(maxlen=8)
        self.camera = None
        self.particles = []
        self.last_alive = {}
        self.rng = random.Random(42)
        self.me_screen = (640,400)

    def push(self, state):
        for s in state["snakes"]:
            if not s["alive"] and self.last_alive.get(s["id"],False):
                color = rgb(s["color"])
                for p in s["body"][::2]:
                    for _ in range(2):
                        self.particles.append([p[0],p[1],self.rng.uniform(-100,100),self.rng.uniform(-100,100),.8,color])
            self.last_alive[s["id"]] = s["alive"]
        self.states.append((state.get("_received",time.monotonic()),state))

    def interpolated(self, now):
        if not self.states:
            return None
        target = now-.10
        before = self.states[0]
        after = self.states[-1]
        for item in self.states:
            if item[0] <= target:
                before = item
            if item[0] >= target:
                after = item
                break
        a,b = before[1],after[1]
