"""动态难度曲线、时间语义和对象同步的回归检查。"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from collections import defaultdict
import math
import unittest
from unittest.mock import patch

import pygame

import settings
from coin import Coin
from difficulty import Difficulty
from game_manager import GameManager, GameState
from obstacle import Obstacle


class DifficultyCurveTests(unittest.TestCase):
    """检查独立难度计算，无需启动 Pygame。"""

    def test_warmup_keeps_original_parameters(self) -> None:
        for seconds in (0.0, 5.0, 10.0):
            with self.subTest(seconds=seconds):
                difficulty = Difficulty.from_game_time(seconds)
                self.assertEqual(difficulty.speed_multiplier, 1.0)
                self.assertEqual(difficulty.coin_speed, 180.0)
                self.assertEqual(difficulty.obstacle_speed, 220.0)
                self.assertEqual(difficulty.obstacle_spawn_interval, 1.8)

    def test_midpoint_reaches_half_of_ramp(self) -> None:
        difficulty = Difficulty.from_game_time(65.0)
        self.assertEqual(difficulty.progress, 0.5)
        self.assertEqual(difficulty.coin_speed, 270.0)
        self.assertEqual(difficulty.obstacle_speed, 330.0)
        self.assertAlmostEqual(difficulty.obstacle_spawn_interval, 1.2)

    def test_challenge_increases_smoothly_until_cap(self) -> None:
        earlier = Difficulty.from_game_time(30.0)
        later = Difficulty.from_game_time(60.0)
        self.assertGreater(earlier.coin_speed, 180.0)
        self.assertGreater(later.coin_speed, earlier.coin_speed)
        self.assertGreater(later.obstacle_speed, earlier.obstacle_speed)
        self.assertLess(later.obstacle_spawn_interval, earlier.obstacle_spawn_interval)
        before = Difficulty.from_game_time(50.0)
        after = Difficulty.from_game_time(50.01)
        self.assertLess(after.coin_speed - before.coin_speed, 0.1)

    def test_maximum_parameters_stay_bounded(self) -> None:
        for seconds in (120.0, 600.0, 3600.0):
            with self.subTest(seconds=seconds):
                difficulty = Difficulty.from_game_time(seconds)
                self.assertEqual(difficulty.speed_multiplier, 2.0)
                self.assertEqual(difficulty.coin_speed, 360.0)
                self.assertEqual(difficulty.obstacle_speed, 440.0)
                self.assertAlmostEqual(difficulty.obstacle_spawn_interval, 0.6)


class DifficultyIntegrationTests(unittest.TestCase):
    """检查难度与生成、对象、暂停、结束和重开的集成。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.game = GameManager()
        pygame.event.clear()

    def update_with_focus(self, dt: float, focused: bool = True) -> None:
        with (
            patch("pygame.key.get_focused", return_value=focused),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool)),
        ):
            self.game.update(dt)

    def set_time(self, seconds: float) -> None:
        self.game.game_time = seconds
        self.game.update_difficulty()

    def test_time_only_advances_during_focused_gameplay(self) -> None:
        self.update_with_focus(0.5)
        self.assertEqual(self.game.game_time, 0.5)
        self.update_with_focus(5.0, focused=False)
        self.assertEqual(self.game.game_time, 0.5)
        self.game.state = GameState.GAME_OVER
        difficulty = self.game.difficulty
        self.update_with_focus(5.0)
        self.assertEqual(self.game.game_time, 0.5)
        self.assertEqual(self.game.difficulty, difficulty)

    def test_existing_and_new_objects_share_current_speed(self) -> None:
        coin = self.game.spawn_coin()
        obstacle = self.game.spawn_obstacle()
        self.set_time(65.0)
        self.assertEqual(coin.speed, 270.0)
        self.assertEqual(obstacle.speed, 330.0)
        self.assertEqual(self.game.spawn_coin().speed, coin.speed)
        self.assertEqual(self.game.spawn_obstacle().speed, obstacle.speed)

    def test_interval_change_preserves_spawn_progress(self) -> None:
        self.game.obstacle_spawn_timer = 0.9
        self.set_time(65.0)
        self.assertAlmostEqual(self.game.obstacle_spawn_timer, 0.6)
        self.assertAlmostEqual(
            self.game.obstacle_spawn_timer / self.game.difficulty.obstacle_spawn_interval,
            0.5,
        )
        self.game.update_obstacles(0.3)
        self.assertEqual(len(self.game.obstacles), 0)
        self.game.update_obstacles(0.31)
        self.assertEqual(len(self.game.obstacles), 1)

    def test_high_difficulty_spawns_more_obstacles_in_equal_time(self) -> None:
        baseline = GameManager()
        self.set_time(120.0)
        with (
            patch.object(baseline, "spawn_obstacle", wraps=baseline.spawn_obstacle) as slow,
            patch.object(self.game, "spawn_obstacle", wraps=self.game.spawn_obstacle) as fast,
        ):
            for _ in range(100):
                baseline.update_obstacles(0.05)
                self.game.update_obstacles(0.05)
        self.assertEqual(slow.call_count, 2)
        self.assertEqual(fast.call_count, 8)

    def test_restart_resets_time_difficulty_and_timers(self) -> None:
        self.set_time(120.0)
        self.game.coin_spawn_timer = 0.3
        self.game.obstacle_spawn_timer = 0.4
        self.game.score = 50
        self.game.player.take_damage(3)
        self.game.handle_obstacle_collisions()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.game.handle_events()
        self.assertEqual(self.game.game_time, 0.0)
        self.assertEqual(self.game.difficulty, Difficulty.from_game_time(0.0))
        self.assertEqual(self.game.coin_spawn_timer, 0.0)
        self.assertEqual(self.game.obstacle_spawn_timer, 0.0)
        self.assertEqual(self.game.score, 0)
        self.assertEqual(self.game.player.hp, 3)
        self.assertEqual(self.game.spawn_coin().speed, 180.0)
        self.assertEqual(self.game.spawn_obstacle().speed, 220.0)

    def test_dead_player_does_not_advance_time(self) -> None:
        self.game.player.take_damage(3)
        self.update_with_focus(5.0)
        self.assertEqual(self.game.state, GameState.GAME_OVER)
        self.assertEqual(self.game.game_time, 0.0)

    def test_difficulty_hud_displays_time_and_multiplier(self) -> None:
        self.set_time(65.0)
        with patch.object(self.game, "detail_font", wraps=self.game.detail_font) as font:
            self.game.draw_hud()
        font.render.assert_any_call(
            "Time: 65s | Speed: x1.50", True, settings.MUTED_TEXT_COLOR
        )

    def test_fast_objects_still_score_and_damage(self) -> None:
        self.set_time(120.0)
        coin = Coin(self.game.player.get_rect().centerx, self.game.player.y - 13)
        obstacle = Obstacle(self.game.player.x, self.game.player.y - 37)
        self.game.coins = [coin]
        self.game.obstacles = [obstacle]
        self.update_with_focus(0.1)
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.assertEqual(self.game.player.hp, 2)
        self.assertEqual(self.game.coins, [])
        self.assertEqual(self.game.obstacles, [])

    def test_high_difficulty_does_not_accumulate_off_screen_objects(self) -> None:
        self.set_time(120.0)
        coin_limit = math.ceil(
            (settings.SCREEN_HEIGHT + 2 * settings.COIN_RADIUS)
            / self.game.difficulty.coin_speed / settings.COIN_SPAWN_INTERVAL
        ) + 1
        obstacle_limit = math.ceil(
            (settings.SCREEN_HEIGHT + settings.OBSTACLE_HEIGHT)
            / self.game.difficulty.obstacle_speed
            / self.game.difficulty.obstacle_spawn_interval
        ) + 1
        for _ in range(1200):
            self.game.update_coins(0.1)
            self.game.update_obstacles(0.1)
            self.assertLessEqual(len(self.game.coins), coin_limit)
            self.assertLessEqual(len(self.game.obstacles), obstacle_limit)

    def test_difficulty_is_consistent_across_frame_rates(self) -> None:
        other = GameManager()
        with (
            patch("pygame.key.get_focused", return_value=True),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool)),
            patch("game_manager.random.uniform", return_value=50.0),
        ):
            for _ in range(489):
                self.game.update(1 / 30)
            for _ in range(1956):
                other.update(1 / 120)
        self.assertAlmostEqual(self.game.game_time, 16.3)
        self.assertAlmostEqual(self.game.game_time, other.game_time)
        self.assertAlmostEqual(
            self.game.difficulty.coin_speed, other.difficulty.coin_speed
        )
        self.assertAlmostEqual(
            self.game.difficulty.obstacle_spawn_interval,
            other.difficulty.obstacle_spawn_interval,
        )
        self.assertEqual(len(self.game.coins), len(other.coins))
        self.assertEqual(len(self.game.obstacles), len(other.obstacles))
        for first, second in zip(self.game.coins, other.coins):
            self.assertAlmostEqual(first.y, second.y, delta=1.0)


if __name__ == "__main__":
    unittest.main()
