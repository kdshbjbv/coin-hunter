"""生命值 UI、游戏结束和重新开始的回归检查。"""

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
from game_manager import GameManager, GameState
from obstacle import Obstacle
from utils import draw_heart


class GameStateTests(unittest.TestCase):
    """验证状态转换、结束后冻结和一局数据的完整重置。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.game = GameManager()
        pygame.event.clear()

    def hit_player(self, damage: int = 1) -> None:
        obstacle = Obstacle(self.game.player.x, self.game.player.y)
        obstacle.damage = damage
        self.game.obstacles = [obstacle]
        self.game.handle_obstacle_collisions()

    def post_key(self, key: int) -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        self.game.handle_events()

    def assert_fresh_round(self) -> None:
        self.assertEqual(self.game.state, GameState.PLAYING)
        self.assertEqual(self.game.player.hp, 3)
        self.assertEqual(self.game.player.hit_flash_timer, 0.0)
        self.assertEqual(self.game.player.x, 368.0)
        self.assertEqual(self.game.player.y, 544.0)
        self.assertEqual(self.game.score, 0)
        self.assertEqual(self.game.coins, [])
        self.assertEqual(self.game.obstacles, [])
        self.assertEqual(self.game.coin_spawn_timer, 0.0)
        self.assertEqual(self.game.obstacle_spawn_timer, 0.0)
        self.assertEqual(self.game.game_time, 0.0)
        self.assertEqual(self.game.difficulty.speed_multiplier, 1.0)
        self.assertTrue(self.game.running)

    def test_starts_in_playing_state(self) -> None:
        self.assert_fresh_round()

    def test_three_hits_end_round_but_keep_window_running(self) -> None:
        for expected_hp in (2, 1, 0):
            self.hit_player()
            self.assertEqual(self.game.player.hp, expected_hp)
            expected_state = GameState.PLAYING if expected_hp else GameState.GAME_OVER
            self.assertEqual(self.game.state, expected_state)
        self.assertTrue(self.game.running)

    def test_fatal_damage_clamps_hp_and_preserves_final_score(self) -> None:
        self.game.score = 70
        self.hit_player(10)
        self.assertEqual(self.game.player.hp, 0)
        self.assertEqual(self.game.state, GameState.GAME_OVER)
        self.assertEqual(self.game.score, 70)

    def test_game_over_freezes_all_gameplay(self) -> None:
        self.hit_player(3)
        coin = Coin(100, 100)
        obstacle = Obstacle(200, 200)
        self.game.coins = [coin]
        self.game.obstacles = [obstacle]
        self.game.score = 40
        self.game.coin_spawn_timer = 0.3
        self.game.obstacle_spawn_timer = 0.7
        player_position = (self.game.player.x, self.game.player.y)
        flash = self.game.player.hit_flash_timer
        with (
            patch("pygame.key.get_focused", return_value=True),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool, {pygame.K_d: True})),
        ):
            self.game.update(10.0)
        self.assertEqual((self.game.player.x, self.game.player.y), player_position)
        self.assertEqual((coin.y, obstacle.y), (100.0, 200.0))
        self.assertEqual(self.game.coins, [coin])
        self.assertEqual(self.game.obstacles, [obstacle])
        self.assertEqual(self.game.score, 40)
        self.assertEqual(self.game.player.hp, 0)
        self.assertEqual(self.game.player.hit_flash_timer, flash)
        self.assertEqual(self.game.coin_spawn_timer, 0.3)
        self.assertEqual(self.game.obstacle_spawn_timer, 0.7)

    def test_reset_clears_round_data_and_reuses_resources(self) -> None:
        self.game.player.x = 10.0
        self.hit_player(3)
        self.game.score = 90
        self.game.coins = [Coin(50, 100)]
        self.game.obstacles = [Obstacle(200, 100)]
        self.game.coin_spawn_timer = 0.3
        self.game.obstacle_spawn_timer = 0.7
        old_player = self.game.player
        resources = (self.game.screen, self.game.clock, self.game.body_font)
        with patch("pygame.key.stop_text_input", wraps=pygame.key.stop_text_input) as stop:
            self.game.reset_game()
        stop.assert_called_once_with()
        self.assert_fresh_round()
        self.assertIsNot(self.game.player, old_player)
        for current, previous in zip(
            (self.game.screen, self.game.clock, self.game.body_font), resources
        ):
            self.assertIs(current, previous)

    def test_restart_keys_work_from_game_over(self) -> None:
        for key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER):
            with self.subTest(key=key):
                self.hit_player(3)
                self.game.score = 50
                self.post_key(key)
                self.assert_fresh_round()

    def test_restart_keys_do_not_reset_active_round(self) -> None:
        self.game.score = 30
        self.hit_player()
        for key in (pygame.K_r, pygame.K_RETURN):
            self.post_key(key)
            self.assertEqual(self.game.score, 30)
            self.assertEqual(self.game.player.hp, 2)
            self.assertEqual(self.game.state, GameState.PLAYING)

    def test_restarted_round_can_move_collect_and_spawn_again(self) -> None:
        self.hit_player(3)
        self.post_key(pygame.K_r)
        center_x, center_y = self.game.player.get_rect().center
        self.game.coins = [Coin(center_x + 36, center_y)]
        with (
            patch("pygame.key.get_focused", return_value=True),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool, {pygame.K_d: True})),
        ):
            self.game.update(0.1)
        self.assertAlmostEqual(self.game.player.x, 404.0)
        self.assertEqual(self.game.score, settings.COIN_VALUE)
        self.game.update_coins(settings.COIN_SPAWN_INTERVAL)
        self.game.update_obstacles(settings.OBSTACLE_SPAWN_INTERVAL)
        self.assertGreater(len(self.game.coins), 0)
        self.assertGreater(len(self.game.obstacles), 0)

    def test_quit_and_escape_still_work_from_game_over(self) -> None:
        for event in (
            pygame.event.Event(pygame.QUIT),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
        ):
            with self.subTest(event=event.type):
                self.game.running = True
                self.hit_player(3)
                pygame.event.post(event)
                self.game.handle_events()
                self.assertFalse(self.game.running)

    def test_hud_draws_active_and_empty_hearts(self) -> None:
        for hp in (3, 2, 0):
            with self.subTest(hp=hp):
                self.game.player.hp = hp
                with patch("game_manager.draw_heart", wraps=draw_heart) as hearts:
                    self.game.draw_hud()
                colors = [call.args[1] for call in hearts.call_args_list]
                self.assertEqual(colors.count(settings.HEART_COLOR), hp)
                self.assertEqual(colors.count(settings.HEART_EMPTY_COLOR), 3 - hp)

    def test_heart_primitive_draws_without_font_glyph(self) -> None:
        surface = pygame.Surface((60, 60))
        surface.fill(settings.BACKGROUND_COLOR)
        draw_heart(surface, settings.HEART_COLOR, pygame.Rect(20, 20, 22, 22))
        self.assertEqual(tuple(surface.get_at((31, 31)))[:3], settings.HEART_COLOR)
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], settings.BACKGROUND_COLOR)

    def test_game_over_renders_final_score_and_restart_prompt(self) -> None:
        self.game.score = 35
        self.hit_player(3)
        with (
            patch.object(self.game, "title_font", wraps=self.game.title_font) as title,
            patch.object(self.game, "body_font", wraps=self.game.body_font) as body,
        ):
            self.game.draw()
        title.render.assert_any_call("GAME OVER", True, settings.TEXT_COLOR)
        body.render.assert_any_call("Final Score: 35", True, settings.TEXT_COLOR)
        body.render.assert_any_call(
            "Press R or Enter to restart", True, settings.MUTED_TEXT_COLOR
        )


if __name__ == "__main__":
    unittest.main()
