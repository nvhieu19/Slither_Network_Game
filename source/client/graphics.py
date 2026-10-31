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
