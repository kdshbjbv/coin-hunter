"""金币对象与生成生命周期的回归检查。"""

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
from game_manager import GameManager


class CoinTests(unittest.TestCase):
    """验证金币行为及其与主循环的集成。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.game = GameManager()
        pygame.event.clear()

    def test_attributes_movement_and_collision_area(self) -> None:
        coin = Coin(100, 50)
        self.assertEqual(
            (coin.radius, coin.speed, coin.value),
            (settings.COIN_RADIUS, settings.COIN_SPEED, settings.COIN_VALUE),
        )
        coin.update(0.5)
        self.assertEqual(coin.x, 100.0)
        self.assertAlmostEqual(coin.y, 50 + settings.COIN_SPEED * 0.5)
        rect = coin.get_rect()
        self.assertEqual(rect.center, (round(coin.x), round(coin.y)))
        self.assertEqual(rect.size, (coin.radius * 2, coin.radius * 2))

    def test_spawn_positions_include_radius_margin(self) -> None:
        radius = settings.COIN_RADIUS
        right_edge = settings.SCREEN_WIDTH - radius
        with patch("game_manager.random.uniform", side_effect=[radius, right_edge]):
            left = self.game.spawn_coin()
            right = self.game.spawn_coin()
        self.assertEqual(left.get_rect().left, 0)
        self.assertEqual(right.get_rect().right, settings.SCREEN_WIDTH)
        self.assertEqual(left.y, -radius)
        self.assertEqual(right.y, -radius)
        self.assertEqual(len(self.game.coins), 2)

    def test_spawn_interval_and_remaining_time(self) -> None:
        interval = settings.COIN_SPAWN_INTERVAL
        self.game.update_coins(interval * 0.75)
        self.assertEqual(len(self.game.coins), 0)
        self.game.update_coins(interval * 0.5)
        self.assertEqual(len(self.game.coins), 1)
        self.assertAlmostEqual(self.game.coin_spawn_timer, interval * 0.25)
        self.assertAlmostEqual(
            self.game.coins[0].y,
            -settings.COIN_RADIUS + settings.COIN_SPEED * interval * 0.25,
        )

    def test_frame_steps_preserve_spawn_count_and_positions(self) -> None:
        other = GameManager()
        with patch("game_manager.random.uniform", return_value=400.0):
            self.game.update_coins(2.5)
            for _ in range(25):
                other.update_coins(0.1)
        self.assertEqual(len(self.game.coins), 3)
        self.assertEqual(len(self.game.coins), len(other.coins))
        for first, second in zip(self.game.coins, other.coins):
            self.assertAlmostEqual(first.y, second.y)

    def test_cleanup_waits_for_entire_coin_to_leave(self) -> None:
        height = settings.SCREEN_HEIGHT
        visible = Coin(100, height + settings.COIN_RADIUS - 1)
        gone = Coin(200, height + settings.COIN_RADIUS)
        also_gone = Coin(300, height + settings.COIN_RADIUS + 20)
        self.game.coins = [gone, also_gone, visible]
        self.game.update_coins(0.0)
        self.assertEqual(self.game.coins, [visible])
        self.game.update_coins(1 / settings.COIN_SPEED)
        self.assertEqual(self.game.coins, [])

    def test_long_run_does_not_accumulate_off_screen_coins(self) -> None:
        lifetime = (settings.SCREEN_HEIGHT + 2 * settings.COIN_RADIUS) / settings.COIN_SPEED
        max_visible = math.ceil(lifetime / settings.COIN_SPAWN_INTERVAL) + 1
        for _ in range(1200):
            self.game.update_coins(0.1)
            self.assertLessEqual(len(self.game.coins), max_visible)
            self.assertTrue(all(
                not coin.is_off_screen(settings.SCREEN_HEIGHT)
                for coin in self.game.coins
            ))
        self.assertGreater(len(self.game.coins), 0)

    def test_focus_pauses_spawn_and_falling(self) -> None:
        coin = self.game.spawn_coin()
        keys = defaultdict(bool)
        with (
            patch("pygame.key.get_focused", return_value=False),
            patch("pygame.key.get_pressed", return_value=keys),
        ):
            self.game.update(1.0)
        self.assertEqual(coin.y, -settings.COIN_RADIUS)
        self.assertEqual(self.game.coin_spawn_timer, 0.0)
        with (
            patch("pygame.key.get_focused", return_value=True),
            patch("pygame.key.get_pressed", return_value=keys),
        ):
            self.game.update(0.1)
        self.assertAlmostEqual(coin.y, -settings.COIN_RADIUS + settings.COIN_SPEED * 0.1)

    def test_coin_draws_on_surface(self) -> None:
        surface = pygame.Surface((200, 200))
        surface.fill(settings.BACKGROUND_COLOR)
        Coin(100, 100).draw(surface)
        self.assertEqual(tuple(surface.get_at((100, 100)))[:3], settings.COIN_COLOR)
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], settings.BACKGROUND_COLOR)


if __name__ == "__main__":
    unittest.main()
