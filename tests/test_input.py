"""输入法模式、焦点与玩家移动的回归检查（标准库 unittest）。"""

import os

# 测试在无界面环境中运行，不抢占用户当前窗口。
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from collections import defaultdict
import unittest
from unittest.mock import patch

import pygame

from game_manager import GameManager


class InputTests(unittest.TestCase):
    """模拟系统状态验证游戏行为；真实输入法另外手动验收。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        stop_patch = patch(
            "pygame.key.stop_text_input", wraps=pygame.key.stop_text_input
        )
        self.stop_text_input = stop_patch.start()
        self.addCleanup(stop_patch.stop)
        self.game = GameManager()
        pygame.event.clear()

    def update_with_keys(self, pressed: tuple[int, ...], focused: bool = True) -> None:
        """模拟一帧按键与焦点；移动距离应由玩家速度和 dt 决定。"""
        keys = defaultdict(bool, {key: True for key in pressed})
        with (
            patch("pygame.key.get_pressed", return_value=keys),
            patch("pygame.key.get_focused", return_value=focused),
        ):
            self.game.update(0.1)

    def test_window_starts_without_text_input(self) -> None:
        self.stop_text_input.assert_called_once_with()

    def test_focus_gain_disables_text_input_again(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
        self.game.handle_events()
        self.assertEqual(self.stop_text_input.call_count, 2)

    def test_each_movement_key_and_release(self) -> None:
        for key, direction in (
            (pygame.K_LEFT, -1), (pygame.K_RIGHT, 1),
            (pygame.K_a, -1), (pygame.K_d, 1),
        ):
            with self.subTest(key=key):
                self.game.player.x = 368.0
                self.update_with_keys((key,))
                expected = 368.0 + direction * 36.0
                self.assertAlmostEqual(self.game.player.x, expected)
                self.update_with_keys(())
                self.assertAlmostEqual(self.game.player.x, expected)

    def test_combined_keys(self) -> None:
        for pressed, direction in (
            ((pygame.K_LEFT, pygame.K_RIGHT), 0),
            ((pygame.K_a, pygame.K_d), 0),
            ((pygame.K_LEFT, pygame.K_d), 0),
            ((pygame.K_RIGHT, pygame.K_d), 1),
            ((pygame.K_LEFT, pygame.K_a), -1),
        ):
            with self.subTest(pressed=pressed):
                self.game.player.x = 368.0
                self.update_with_keys(pressed)
                self.assertAlmostEqual(self.game.player.x, 368.0 + direction * 36.0)

    def test_focus_loss_stops_and_focus_gain_allows_movement(self) -> None:
        self.update_with_keys((pygame.K_d,), focused=False)
        self.assertEqual(self.game.player.x, 368.0)
        self.update_with_keys((pygame.K_d,), focused=True)
        self.assertAlmostEqual(self.game.player.x, 404.0)

    def test_screen_boundaries(self) -> None:
        self.game.player.update(10.0, -1, 800)
        self.assertEqual(self.game.player.get_rect().left, 0)
        self.game.player.update(10.0, 1, 800)
        self.assertEqual(self.game.player.get_rect().right, 800)

    def test_quit_and_escape(self) -> None:
        for event in (
            pygame.event.Event(pygame.QUIT),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
        ):
            with self.subTest(event=event.type):
                self.game.running = True
                pygame.event.post(event)
                self.game.handle_events()
                self.assertFalse(self.game.running)


if __name__ == "__main__":
    unittest.main()
