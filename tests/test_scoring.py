"""金币碰撞、计分和分数 UI 的回归检查。"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from collections import defaultdict
import unittest
from unittest.mock import patch

import pygame

import settings
from coin import Coin
from game_manager import GameManager


class ScoringTests(unittest.TestCase):
    """验证收集行为，并检查它与更新和绘制的集成。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.game = GameManager()
        pygame.event.clear()

    def overlapping_coin(self, value: int = settings.COIN_VALUE) -> Coin:
        """创建一枚位于玩家中心的测试金币。"""
        coin = Coin(*self.game.player.get_rect().center)
        coin.value = value
        return coin

    def update_with_focus(self, dt: float, focused: bool = True) -> None:
        with (
            patch("pygame.key.get_focused", return_value=focused),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool)),
        ):
            self.game.update(dt)

    def test_new_game_starts_at_zero(self) -> None:
        self.assertEqual(self.game.score, 0)
        self.game.score = 50
        self.assertEqual(GameManager().score, 0)

    def test_collects_coin_once(self) -> None:
        self.game.coins = [self.overlapping_coin()]
        self.game.collect_coins()
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.assertEqual(self.game.coins, [])
        self.game.collect_coins()
        self.assertEqual(self.game.score, settings.COIN_VALUE)

    def test_collects_multiple_values_and_preserves_other_coins(self) -> None:
        first_miss = Coin(100, 100)
        second_miss = Coin(200, 200)
        self.game.coins = [
            first_miss, self.overlapping_coin(10),
            self.overlapping_coin(25), second_miss,
        ]
        self.game.collect_coins()
        self.assertEqual(self.game.score, 35)
        self.assertEqual(self.game.coins, [first_miss, second_miss])

    def test_touching_edges_do_not_count_as_overlap(self) -> None:
        player_rect = self.game.player.get_rect()
        coin = Coin(player_rect.right + settings.COIN_RADIUS, player_rect.centery)
        self.game.coins = [coin]
        self.game.collect_coins()
        self.assertEqual(self.game.score, 0)
        self.assertEqual(self.game.coins, [coin])
        coin.x -= 1
        self.game.collect_coins()
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.assertEqual(self.game.coins, [])

    def test_update_collects_a_falling_coin(self) -> None:
        coin = Coin(
            self.game.player.get_rect().centerx,
            self.game.player.y - settings.COIN_RADIUS - 1,
        )
        self.game.coins = [coin]
        self.assertFalse(self.game.player.get_rect().colliderect(coin.get_rect()))
        self.update_with_focus(0.1)
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.assertEqual(self.game.coins, [])

    def test_missed_coin_is_removed_without_changing_score(self) -> None:
        self.game.score = 20
        self.game.coins = [Coin(100, settings.SCREEN_HEIGHT + settings.COIN_RADIUS)]
        self.update_with_focus(0.0)
        self.assertEqual(self.game.score, 20)
        self.assertEqual(self.game.coins, [])

    def test_focus_loss_pauses_collection(self) -> None:
        coin = self.overlapping_coin()
        self.game.coins = [coin]
        self.update_with_focus(0.1, focused=False)
        self.assertEqual(self.game.score, 0)
        self.assertEqual(self.game.coins, [coin])
        self.update_with_focus(0.0)
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.assertEqual(self.game.coins, [])

    def test_draw_renders_current_score(self) -> None:
        self.game.coins = [self.overlapping_coin(25)]
        self.game.collect_coins()
        with patch.object(self.game, "body_font", wraps=self.game.body_font) as font:
            self.game.draw()
        font.render.assert_any_call("Score: 25", True, settings.TEXT_COLOR)
        # 验证文字实际写入左上角画面，而不只是调用 render。
        region = self.game.screen.subsurface(pygame.Rect(20, 20, 140, 30))
        background = pygame.Surface(region.get_size())
        background.fill(settings.PANEL_COLOR)
        self.assertNotEqual(
            pygame.image.tobytes(region, "RGB"),
            pygame.image.tobytes(background, "RGB"),
        )


if __name__ == "__main__":
    unittest.main()
