"""Deterministic fixed-step simulation. No sockets, GUI or database in this module.

All mutations run under the server state lock. World coordinates are pixels.
Self-collision is deliberately disabled, following the Slither-style rules.
"""
from dataclasses import dataclass, field
import math
import random
import uuid
from common.config import (WORLD_SIZE, BASE_SPEED, BOOST_SPEED, TURN_RATE, RADIUS,
                           SEGMENT_SPACING, BASE_SEGMENTS, MAX_SEGMENTS,
                           FOOD_COUNT, MAX_FOOD, SKINS)


def distance2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def turn_toward(current, desired, max_change):
    delta = (desired - current + math.pi) % math.tau - math.pi
    return current + max(-max_change, min(max_change, delta))


class SpatialGrid:
    """Uniform grid broad phase; exact squared-distance tests are the narrow phase."""
    def __init__(self, size=64):
        self.size, self.cells = size, {}

    def put(self, x, y, item):
        self.cells.setdefault((int(x // self.size), int(y // self.size)), []).append(item)

    def nearby(self, x, y, radius):
        for gx in range(int((x-radius)//self.size), int((x+radius)//self.size)+1):
            for gy in range(int((y-radius)//self.size), int((y+radius)//self.size)+1):
                yield from self.cells.get((gx, gy), ())


@dataclass
class Snake:
    id: str
    name: str
    color: str
    body: list
    angle: float
    target: float
    bot: bool = False
    score: int = 0
    peak_score: int = 0
    peak_length: int = BASE_SEGMENTS
    alive: bool = True
    boost: bool = False
    boosting: bool = False
    age: float = 0.0
    shield: float = 2.0
    boost_clock: float = 0.0
    think_clock: float = 0.0
    dead_clock: float = 0.0
    reason: str = ""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def head(self):
        return self.body[0]


class Arena:
    def __init__(self, seed=None, food_count=FOOD_COUNT):
        self.rng = random.Random(seed)
        self.snakes = {}
        self.food = {}
        self.food_serial = 0
        self.food_count = food_count
        self.tick = 0
        self.events = []
        self.refill()

    def add_food(self, x=None, y=None, value=1, color=None):
        if len(self.food) >= MAX_FOOD:
            return
        self.food_serial += 1
        self.food[self.food_serial] = [
            round(x if x is not None else self.rng.uniform(40, WORLD_SIZE-40), 1),
            round(y if y is not None else self.rng.uniform(40, WORLD_SIZE-40), 1),
            value, color or self.rng.choice(SKINS)]

    def refill(self):
        while len(self.food) < self.food_count:
            self.add_food()

    def spawn(self, pid, name, color, bot=False):
        # Sample safe positions. Shield also prevents unfair immediate contact.
        point = (WORLD_SIZE/2, WORLD_SIZE/2)
        for _ in range(80):
            point = (self.rng.uniform(240, WORLD_SIZE-240), self.rng.uniform(240, WORLD_SIZE-240))
            if all(distance2(point, p) > 200**2 for s in self.snakes.values()
                   if s.alive for p in s.body[::4]):
                break
        angle = self.rng.uniform(-math.pi, math.pi)
        body = [(point[0]-i*SEGMENT_SPACING*math.cos(angle),
                 point[1]-i*SEGMENT_SPACING*math.sin(angle)) for i in range(BASE_SEGMENTS)]
        snake = Snake(str(pid), name, color, body, angle, angle, bot=bot)
        self.snakes[str(pid)] = snake
        return snake

    def add_bots(self, count):
        for i in range(count):
            self.spawn(f"bot{i}", ["Orbit", "Nova", "Comet", "Luna"][i], SKINS[(i+1)%6], True)

    def set_input(self, pid, angle, boost):
        s = self.snakes.get(str(pid))
        if s and s.alive:
            s.target, s.boost = angle, bool(boost)

    def kill(self, pid, reason="collision", drop=True):
        s = self.snakes.get(str(pid))
        if not s or not s.alive:
            return
        s.alive, s.boosting, s.reason = False, False, reason
        if drop:
            # One food object per body segment, capped by the room food budget.
            for x, y in s.body:
                self.add_food(max(20, min(WORLD_SIZE-20, x)),
                              max(20, min(WORLD_SIZE-20, y)), 2, s.color)
        self.events.append({"id": s.id, "run_id": s.run_id, "reason": reason,
                            "score": s.peak_score, "final_score": s.score,
                            "max_length": s.peak_length, "duration": round(s.age, 2),
                            "bot": s.bot})

    def remove(self, pid, reason="disconnect"):
        self.kill(pid, reason)
        self.snakes.pop(str(pid), None)

    def _bot_input(self, s, dt):
        s.think_clock -= dt
        if s.think_clock > 0:
            return
        s.think_clock = .20
        x, y = s.head
        if min(x, y, WORLD_SIZE-x, WORLD_SIZE-y) < 220:
            s.target = math.atan2(WORLD_SIZE/2-y, WORLD_SIZE/2-x)
            s.boost = False
            return
        threat = next((p for other in self.snakes.values() if other.id != s.id and other.alive
                       for p in other.body[::3] if distance2(s.head, p) < 100**2), None)
        if threat:
            s.target = math.atan2(y-threat[1], x-threat[0])
        elif self.food:
            closest = min(self.food.values(), key=lambda f: distance2(s.head, f))
            s.target = math.atan2(closest[1]-y, closest[0]-x)
        s.boost = s.score > 20 and self.rng.random() < .07

    def update(self, dt):
        self.tick += 1
        # Phase 1: all snakes move before collision decisions are made.
        for s in list(self.snakes.values()):
            if not s.alive:
                if s.bot:
                    s.dead_clock += dt
                    if s.dead_clock > 3:
                        self.spawn(s.id, s.name, s.color, True)
                continue
            s.age += dt
            s.shield = max(0, s.shield-dt)
            if s.bot:
                self._bot_input(s, dt)
            s.angle = turn_toward(s.angle, s.target, TURN_RATE*dt)
            s.boosting = s.boost and s.score >= 5
            speed = BOOST_SPEED if s.boosting else BASE_SPEED
            x, y = s.head
            s.body[0] = (x+math.cos(s.angle)*speed*dt, y+math.sin(s.angle)*speed*dt)
            for i in range(1, len(s.body)):
                prev, point = s.body[i-1], s.body[i]
                dx, dy = point[0]-prev[0], point[1]-prev[1]
                dist = math.hypot(dx, dy)
                if dist > SEGMENT_SPACING:
                    s.body[i] = (prev[0]+dx/dist*SEGMENT_SPACING, prev[1]+dy/dist*SEGMENT_SPACING)
            if s.boosting:
                s.boost_clock += dt
                while s.boost_clock >= .18:
                    s.boost_clock -= .18
                    s.score = max(0, s.score-1)
                    self.add_food(*s.body[-1], value=1, color=s.color)
            else:
                s.boost_clock = 0
        # Phase 2: immutable broad phase; resolve mutual head collisions fairly.
        body_grid = SpatialGrid()
        living = [s for s in self.snakes.values() if s.alive]
        for s in living:
            if s.shield <= 0:
                for i, p in enumerate(s.body):
                    body_grid.put(*p, (s.id, i, p))
        deaths = {}
        for s in living:
            x, y = s.head
            if x < RADIUS or y < RADIUS or x > WORLD_SIZE-RADIUS or y > WORLD_SIZE-RADIUS:
                deaths[s.id] = "wall"
            elif s.shield <= 0:
                for other, index, p in body_grid.nearby(x, y, RADIUS*2):
                    if other != s.id and distance2(s.head, p) < (RADIUS*1.7)**2:
                        deaths[s.id] = "head" if index == 0 else "body"
                        break
        for pid, reason in deaths.items():
            self.kill(pid, reason)
        food_grid = SpatialGrid()
        for fid, f in self.food.items():
            food_grid.put(f[0], f[1], fid)
        # Rotate eating priority so ties do not permanently favour one player.
        if living:
            shift = self.tick % len(living)
            living = living[shift:] + living[:shift]
        for s in living:
            if not s.alive:
                continue
            for fid in food_grid.nearby(*s.head, RADIUS+9):
                f = self.food.get(fid)
                if f and distance2(s.head, f) < (RADIUS+5)**2:
                    s.score += f[2]
                    del self.food[fid]
            s.peak_score = max(s.peak_score, s.score)
            length = min(MAX_SEGMENTS, BASE_SEGMENTS+s.score//2)
            if length > len(s.body):
                s.body.extend([s.body[-1]]*(length-len(s.body)))
            elif length < len(s.body):
                del s.body[length:]
            s.peak_length = max(s.peak_length, len(s.body))
        self.refill()

    def drain_events(self):
        events, self.events = self.events, []
        return events

    def snapshot(self):
        snakes = [{"id": s.id, "name": s.name, "color": s.color, "score": s.score,
                   "peak": s.peak_score, "alive": s.alive, "boost": s.boosting,
                   "shield": round(s.shield, 2), "angle": round(s.angle, 3), "bot": s.bot,
                   "reason": s.reason, "age": round(s.age, 1),
                   "body": [[round(x, 1), round(y, 1)] for x,y in s.body]}
                  for s in self.snakes.values()]
        top = sorted((s for s in snakes if s["alive"]), key=lambda s: (-s["score"], s["name"]))[:10]
        return {"type": "WORLD_STATE", "tick": self.tick, "size": WORLD_SIZE,
                "snakes": snakes, "food": [[fid]+f for fid,f in self.food.items()],
                "top": [{"id": s["id"], "name": s["name"], "score": s["score"], "color": s["color"]} for s in top]}
