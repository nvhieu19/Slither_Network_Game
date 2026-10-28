import math
import unittest
from common.config import BASE_SEGMENTS, WORLD_SIZE, MAX_FOOD
from server.engine import Arena, SpatialGrid, turn_toward


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.a=Arena(42,food_count=0)
        self.s=self.a.spawn("1","Pilot","#54E8B0")
        self.s.body=[(500-i*7,500) for i in range(BASE_SEGMENTS)]
        self.s.angle=self.s.target=0
        self.s.shield=0

    def test_authoritative_movement_speed(self):
        self.a.update(1/30)
        self.assertAlmostEqual(self.s.head[0],500+145/30)
        self.assertEqual(self.s.head[1],500)

    def test_eating_grows_and_removes_food(self):
        self.a.add_food(505,500,8)
        self.a.update(1/30)
        self.assertEqual(self.s.score,8)
        self.assertEqual(len(self.s.body),BASE_SEGMENTS+4)
        self.assertFalse(self.a.food)

    def test_boost_spends_score_drops_food_and_moves_faster(self):
        self.s.score=20; self.s.boost=True
        for _ in range(6): self.a.update(1/30)
        self.assertEqual(self.s.score,19)
        self.assertGreater(self.s.head[0],540)
        self.assertTrue(self.a.food)

    def test_boost_floor(self):
        self.s.score=4; self.s.boost=True
        self.a.update(1/30)
        self.assertFalse(self.s.boosting)
        self.assertEqual(self.s.score,4)

    def test_wall_death_and_single_event(self):
        self.s.body[0]=(WORLD_SIZE-14,500)
        self.a.update(1/30)
        self.assertFalse(self.s.alive)
        self.assertEqual(self.a.events[0]["reason"],"wall")
        self.a.kill("1")
        self.assertEqual(len(self.a.drain_events()),1)
        self.assertEqual(self.a.drain_events(),[])
        self.assertEqual(len(self.a.food),BASE_SEGMENTS)

    def test_head_to_head_is_simultaneous(self):
        other=self.a.spawn("2","Other","#FF799D")
        other.body=[(525+i*7,500) for i in range(BASE_SEGMENTS)]
        other.angle=other.target=math.pi; other.shield=0
        self.a.update(1/30)
        self.assertFalse(self.s.alive)
        self.assertFalse(other.alive)

    def test_enemy_body_collision(self):
        other=self.a.spawn("2","Other","#FF799D")
        other.body=[(510,400+i*7) for i in range(30)]
        other.angle=other.target=-math.pi/2; other.shield=0
        self.a.update(1/30)
        self.assertFalse(self.s.alive)
        self.assertTrue(other.alive)

    def test_self_collision_disabled(self):
        self.s.body=[(500,500)]*BASE_SEGMENTS
        self.a.update(1/30)
        self.assertTrue(self.s.alive)

    def test_spawn_shield(self):
        other=self.a.spawn("2","Other","#FF799D")
        other.body=[(505,500)]*BASE_SEGMENTS
        other.angle=other.target=0
        self.a.update(1/30)
        self.assertTrue(self.s.alive)
        self.assertTrue(other.alive)

    def test_respawn_resets_run_and_score(self):
        run=self.s.run_id; self.a.kill("1")
        s=self.a.spawn("1","Pilot","#54E8B0")
        self.assertNotEqual(run,s.run_id)
        self.assertEqual(s.score,0)
        self.assertTrue(s.alive)

    def test_grid_across_cell_border(self):
        grid=SpatialGrid(); grid.put(63,63,"a"); grid.put(66,66,"b"); grid.put(500,500,"c")
        self.assertEqual(set(grid.nearby(64,64,5)),{"a","b"})

    def test_food_bound(self):
        for _ in range(MAX_FOOD+10): self.a.add_food()
        self.assertEqual(len(self.a.food),MAX_FOOD)

    def test_turn_wrap_and_limit(self):
        result=turn_toward(math.pi-.02,-math.pi+.02,.1)
        self.assertAlmostEqual(result,math.pi+.02)
        self.assertAlmostEqual(turn_toward(0,2,.14),.14)
