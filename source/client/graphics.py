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
