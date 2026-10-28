"""Procedural art: neon food, smooth snakes, arena camera, radar and particles."""
from collections import deque
from functools import lru_cache
import math
import random
import time
import pygame
from common.config import RADIUS, WORLD_SIZE
from client.widgets import text, panel, BG, TEXT, MUTED, ACCENT, EDGE


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
        alpha = max(0,min(1,(target-before[0])/max(.001,after[0]-before[0])))
        old = {s["id"]:s for s in a["snakes"]}
        snakes = []
        for s in b["snakes"]:
            p = old.get(s["id"])
            if p and p["alive"] and s["alive"] and abs(p["body"][0][0]-s["body"][0][0]) < 150 and abs(p["body"][0][1]-s["body"][0][1]) < 150:
                body = [(p["body"][min(i,len(p["body"])-1)][0]*(1-alpha)+xy[0]*alpha,
                         p["body"][min(i,len(p["body"])-1)][1]*(1-alpha)+xy[1]*alpha) for i,xy in enumerate(s["body"])]
                delta = (s["angle"]-p["angle"]+math.pi)%math.tau-math.pi
                snakes.append({**s,"body":body,"angle":p["angle"]+delta*alpha})
            else:
                snakes.append(s)
        return {**b,"snakes":snakes}

    def draw(self, surface, now, dt, pid):
        world = self.interpolated(now)
        surface.fill((8,17,27))
        if not world:
            text(surface,"Đang đồng bộ đấu trường…",(640,400),24,anchor="center")
            return None
        me = next((s for s in world["snakes"] if s["id"]==pid),None)
        target = me["body"][0] if me else (1500,1500)
        if self.camera is None or (me and me["shield"]>1.8):
            self.camera = list(target)
        factor = 1-math.exp(-7*dt)
        self.camera = [a+(b-a)*factor for a,b in zip(self.camera,target)]
        cx,cy = self.camera
        def screen(p): return (p[0]-cx+640,p[1]-cy+400)
        for x in range(int((cx-640)//60)*60,int(cx+700),60):
            xx = round(x-cx+640)
            pygame.draw.line(surface,(18,33,46),(xx,0),(xx,800))
        for y in range(int((cy-400)//60)*60,int(cy+460),60):
            yy = round(y-cy+400)
            pygame.draw.line(surface,(18,33,46),(0,yy),(1280,yy))
        # World border and shaded outside area.
        arena_rect = pygame.Rect(round(640-cx),round(400-cy),WORLD_SIZE,WORLD_SIZE)
        for rect in [pygame.Rect(0,0,max(0,arena_rect.left),800),pygame.Rect(0,0,1280,max(0,arena_rect.top)),
                     pygame.Rect(max(0,arena_rect.right),0,max(0,1280-arena_rect.right),800),
                     pygame.Rect(0,max(0,arena_rect.bottom),1280,max(0,800-arena_rect.bottom))]:
            pygame.draw.rect(surface,(39,16,34),rect)
        pygame.draw.rect(surface,(186,61,107),arena_rect,4)
        for fid,x,y,value,color in world["food"]:
            px,py = screen((x,y))
            if -25<px<1305 and -25<py<825:
                c = rgb(color)
                r = 3 if value==1 else 5
                halo(surface,(px,py),c,15 if value==1 else 23)
                pygame.draw.circle(surface,c,(round(px),round(py)),r)
                pygame.draw.circle(surface,(233,255,252),(round(px-1),round(py-1)),1)
        for s in sorted(world["snakes"],key=lambda s:s["id"]==pid):
            if not s["alive"]:
                continue
            points = [screen(p) for p in s["body"]]
            snake_art(surface,points,s["color"],s["angle"],boosting=s["boost"],shield=s["shield"]>0)
            x,y = points[0]
            if -60<x<1340 and -60<y<860:
                text(surface,s["name"]+(" · BOT" if s["bot"] else ""),(x,y-31),12,ACCENT if s["id"]==pid else TEXT,True,"midbottom")
            if s["id"]==pid:
                self.me_screen = points[0]
        keep=[]
        for p in self.particles:
            p[0]+=p[2]*dt; p[1]+=p[3]*dt; p[4]-=dt
            if p[4]>0:
                keep.append(p)
                pt=screen(p)
                pygame.draw.circle(surface,p[5],(round(pt[0]),round(pt[1])),max(1,int(p[4]*4)))
        self.particles=keep
        return world

    def radar(self,surface,world,pid,rect):
        panel(surface,rect,(11,23,34),16)
        x,y,w,h=rect
        text(surface,"BẢN ĐỒ",(x+16,y+13),11,MUTED,True)
        inner=pygame.Rect(x+18,y+39,w-36,h-55)
        pygame.draw.rect(surface,(29,48,61),inner,1,border_radius=4)
        for i in (1,2):
            pygame.draw.line(surface,(23,40,53),(inner.x+i*inner.w/3,inner.y),(inner.x+i*inner.w/3,inner.bottom))
            pygame.draw.line(surface,(23,40,53),(inner.x,inner.y+i*inner.h/3),(inner.right,inner.y+i*inner.h/3))
        for s in world["snakes"]:
            if s["alive"]:
                p=s["body"][0]
                pt=(round(inner.x+p[0]/WORLD_SIZE*inner.w),round(inner.y+p[1]/WORLD_SIZE*inner.h))
                pygame.draw.circle(surface,ACCENT if s["id"]==pid else (255,130,156),pt,4 if s["id"]==pid else 2)
