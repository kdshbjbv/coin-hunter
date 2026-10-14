"""障碍生命周期、碰撞伤害和玩家反馈的回归检查。"""

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
from game_manager import GameManager, GameState
from obstacle import Obstacle
from player import Player


class ObstacleTests(unittest.TestCase):
    """验证障碍下落、生成清理与玩家碰撞行为。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        self.game = GameManager()
        pygame.event.clear()

    def overlapping_obstacle(self, damage: int = 1) -> Obstacle:
        obstacle = Obstacle(self.game.player.x, self.game.player.y)
        obstacle.damage = damage
        return obstacle

    def update_with_focus(self, dt: float, focused: bool = True) -> None:
        with (
            patch("pygame.key.get_focused", return_value=focused),
            patch("pygame.key.get_pressed", return_value=defaultdict(bool)),
        ):
            self.game.update(dt)

    def test_attributes_movement_and_collision_area(self) -> None:
        obstacle = Obstacle(100, 50)
        self.assertEqual(
            (obstacle.width, obstacle.height, obstacle.speed, obstacle.damage),
            (48, 36, 220.0, 1),
        )
        obstacle.update(0.001)
        self.assertAlmostEqual(obstacle.y, 50.22)
        self.assertEqual(obstacle.x, 100.0)
        self.assertEqual(obstacle.get_rect(), pygame.Rect(100, 50, 48, 36))

    def test_spawn_keeps_full_width_inside_window(self) -> None:
        right_edge = settings.SCREEN_WIDTH - settings.OBSTACLE_WIDTH
        with patch("game_manager.random.uniform", side_effect=[0, right_edge]):
            left = self.game.spawn_obstacle()
            right = self.game.spawn_obstacle()
        self.assertEqual(left.get_rect().left, 0)
        self.assertEqual(right.get_rect().right, settings.SCREEN_WIDTH)
        self.assertEqual(left.get_rect().bottom, 0)
        self.assertEqual(len(self.game.obstacles), 2)

    def test_spawn_interval_preserves_remaining_time(self) -> None:
        interval = settings.OBSTACLE_SPAWN_INTERVAL
        self.game.update_obstacles(interval * 0.75)
        self.assertEqual(self.game.obstacles, [])
        self.game.update_obstacles(interval * 0.5)
        self.assertEqual(len(self.game.obstacles), 1)
        self.assertAlmostEqual(self.game.obstacle_spawn_timer, interval * 0.25)
        self.assertAlmostEqual(
            self.game.obstacles[0].y,
            -settings.OBSTACLE_HEIGHT + settings.OBSTACLE_SPEED * interval * 0.25,
        )

    def test_frame_steps_preserve_spawn_count_and_positions(self) -> None:
        other = GameManager()
        with patch("game_manager.random.uniform", return_value=100.0):
            self.game.update_obstacles(4.0)
            for _ in range(40):
                other.update_obstacles(0.1)
        self.assertEqual(len(self.game.obstacles), 2)
        self.assertEqual(len(other.obstacles), 2)
        for first, second in zip(self.game.obstacles, other.obstacles):
            self.assertAlmostEqual(first.y, second.y)

    def test_cleanup_waits_until_whole_obstacle_leaves(self) -> None:
        height = settings.SCREEN_HEIGHT
        visible = Obstacle(100, height - 1)
        gone = Obstacle(200, height)
        also_gone = Obstacle(300, height + 20)
        self.game.obstacles = [gone, also_gone, visible]
        self.game.update_obstacles(0.0)
        self.assertEqual(self.game.obstacles, [visible])
        self.game.update_obstacles(1 / settings.OBSTACLE_SPEED)
        self.assertEqual(self.game.obstacles, [])

    def test_hit_causes_damage_once_and_keeps_score(self) -> None:
        self.game.score = 20
        self.game.obstacles = [self.overlapping_obstacle()]
        self.game.handle_obstacle_collisions()
        self.assertEqual(self.game.player.hp, 2)
        self.assertEqual(self.game.score, 20)
        self.assertEqual(self.game.obstacles, [])
        self.assertGreater(self.game.player.hit_flash_timer, 0.0)
        self.game.handle_obstacle_collisions()
        self.assertEqual(self.game.player.hp, 2)

    def test_multiple_hits_use_damage_and_clamp_hp_at_zero(self) -> None:
        missed = Obstacle(100, 100)
        self.game.obstacles = [
            self.overlapping_obstacle(1), self.overlapping_obstacle(5), missed
        ]
        self.game.handle_obstacle_collisions()
        self.assertEqual(self.game.player.hp, 0)
        self.assertEqual(self.game.obstacles, [missed])
        self.assertTrue(self.game.running)
        self.assertEqual(self.game.state, GameState.GAME_OVER)

    def test_edge_touch_does_not_cause_damage(self) -> None:
        obstacle = Obstacle(self.game.player.get_rect().right, self.game.player.y)
        self.game.obstacles = [obstacle]
        self.game.handle_obstacle_collisions()
        self.assertEqual(self.game.player.hp, 3)
        obstacle.x -= 1
        self.game.handle_obstacle_collisions()
        self.assertEqual(self.game.player.hp, 2)

    def test_update_handles_falling_obstacle_collision(self) -> None:
        obstacle = Obstacle(
            self.game.player.x, self.game.player.y - settings.OBSTACLE_HEIGHT - 1
        )
        self.game.obstacles = [obstacle]
        self.update_with_focus(0.1)
        self.assertEqual(self.game.player.hp, 2)
        self.assertEqual(self.game.obstacles, [])

    def test_focus_loss_pauses_movement_spawning_and_damage(self) -> None:
        obstacle = self.overlapping_obstacle()
        self.game.obstacles = [obstacle]
        self.update_with_focus(1.0, focused=False)
        self.assertEqual(obstacle.y, self.game.player.y)
        self.assertEqual(self.game.obstacle_spawn_timer, 0.0)
        self.assertEqual(self.game.player.hp, 3)
        self.update_with_focus(0.0)
        self.assertEqual(self.game.player.hp, 2)

    def test_hit_color_expires_and_does_not_prevent_more_damage(self) -> None:
        # 单独检查默认图形，不依赖用户自定义图片的中心像素或透明留白。
        player = Player(self.game.player.x, self.game.player.y)
        surface = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        player.take_damage(1)
        player.draw(surface)
        self.assertEqual(
            tuple(surface.get_at(player.get_rect().center))[:3], settings.PLAYER_HIT_COLOR
        )
        player.take_damage(1)
        self.assertEqual(player.hp, 1)
        player.update(settings.PLAYER_HIT_FLASH_DURATION, 0, settings.SCREEN_WIDTH)
        player.draw(surface)
        self.assertEqual(
            tuple(surface.get_at(player.get_rect().center))[:3], settings.PLAYER_COLOR
        )

    def test_obstacle_draws_on_surface(self) -> None:
        surface = pygame.Surface((200, 200))
        surface.fill(settings.BACKGROUND_COLOR)
        Obstacle(50, 50).draw(surface)
        self.assertEqual(tuple(surface.get_at((70, 65)))[:3], settings.OBSTACLE_COLOR)
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], settings.BACKGROUND_COLOR)

    def test_long_run_does_not_accumulate_off_screen_obstacles(self) -> None:
        lifetime = (settings.SCREEN_HEIGHT + settings.OBSTACLE_HEIGHT) / settings.OBSTACLE_SPEED
        max_visible = math.ceil(lifetime / settings.OBSTACLE_SPAWN_INTERVAL) + 1
        for _ in range(1200):
            self.game.update_obstacles(0.1)
            self.assertLessEqual(len(self.game.obstacles), max_visible)
            self.assertTrue(all(
                not obstacle.is_off_screen(settings.SCREEN_HEIGHT)
                for obstacle in self.game.obstacles
            ))
        self.assertGreater(len(self.game.obstacles), 0)


if __name__ == "__main__":
    unittest.main()
