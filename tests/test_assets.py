"""可选图片的真实读写、缓存、透明度与图形回退检查。"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import pygame

import settings
from asset_manager import AssetManager
from coin import Coin
from game_manager import GameManager
from obstacle import Obstacle
from player import Player
from utils import create_background


class AssetTests(unittest.TestCase):
    """所有图片都在临时目录中生成，不修改用户资源。"""

    def setUp(self) -> None:
        pygame.init()
        self.addCleanup(pygame.quit)
        pygame.display.set_mode((800, 600))
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.assets = AssetManager(self.directory)

    def save_image(self, name: str, color=(90, 180, 120, 255)) -> None:
        image = pygame.Surface((16, 16), pygame.SRCALPHA)
        image.fill(color)
        pygame.image.save(image, str(self.directory / name))

    def create_game(self) -> GameManager:
        with patch("game_manager.AssetManager", return_value=self.assets):
            return GameManager()

    def test_missing_image_uses_cached_fallback(self) -> None:
        self.assertIsNone(self.assets.load_image("missing.png", (24, 24)))
        self.save_image("missing.png")
        # 与文档一致：当前程序保留缓存，新建管理器才会读取替换图片。
        self.assertIsNone(self.assets.load_image("missing.png", (24, 24)))
        self.assertIsNotNone(AssetManager(self.directory).load_image("missing.png", (24, 24)))

    def test_load_scales_and_preserves_alpha(self) -> None:
        self.save_image("coin.png", (25, 100, 200, 128))
        image = self.assets.load_image("coin.png", (24, 24))
        self.assertEqual(image.get_size(), (24, 24))
        self.assertEqual(tuple(image.get_at((12, 12))), (25, 100, 200, 128))

    def test_cache_avoids_repeated_reads_and_shares_surface(self) -> None:
        self.save_image("coin.png")
        with patch("pygame.image.load", wraps=pygame.image.load) as load:
            first = self.assets.load_image("coin.png", (24, 24))
            second = self.assets.load_image("coin.png", (24, 24))
        self.assertIs(first, second)
        load.assert_called_once_with(str(self.directory / "coin.png"))

    def test_different_sizes_have_separate_cache_entries(self) -> None:
        self.save_image("coin.png")
        small = self.assets.load_image("coin.png", (24, 24))
        large = self.assets.load_image("coin.png", (48, 48))
        self.assertIsNot(small, large)
        self.assertEqual(large.get_size(), (48, 48))

    def test_corrupt_image_warns_once_and_falls_back(self) -> None:
        (self.directory / "coin.png").write_bytes(b"invalid png")
        with self.assertLogs("asset_manager", level="WARNING") as log:
            self.assertIsNone(self.assets.load_image("coin.png", (24, 24)))
            self.assertIsNone(self.assets.load_image("coin.png", (24, 24)))
        self.assertEqual(len(log.output), 1)

    def test_game_wires_all_optional_images(self) -> None:
        for name in ("player.png", "coin.png", "obstacle.png", "background.png"):
            self.save_image(name)
        game = self.create_game()
        self.assertEqual(game.player.image.get_size(), (64, 32))
        first = game.spawn_coin()
        second = game.spawn_coin()
        self.assertIs(first.image, second.image)
        self.assertEqual(first.image.get_size(), (24, 24))
        self.assertEqual(game.spawn_obstacle().image.get_size(), (48, 36))
        game.draw()
        self.assertEqual(tuple(game.screen.get_at((700, 400)))[:3], (90, 180, 120))

    def test_partial_replacement_keeps_other_fallbacks(self) -> None:
        self.save_image("player.png")
        game = self.create_game()
        self.assertIsNotNone(game.player.image)
        self.assertIsNone(game.spawn_coin().image)
        self.assertIsNone(game.spawn_obstacle().image)
        self.assertEqual(tuple(game.background.get_at((0, 0)))[:3], settings.BACKGROUND_TOP_COLOR)

    def test_transparent_background_does_not_leave_trails(self) -> None:
        self.save_image("background.png", (0, 0, 0, 0))
        game = self.create_game()
        with patch("pygame.key.get_focused", return_value=True):
            game.screen.fill((255, 0, 0))
            game.draw()
        self.assertEqual(game.screen.get_at((500, 300)), game.background.get_at((500, 300)))
        self.assertEqual(tuple(game.background.get_at((0, 0)))[:3], settings.BACKGROUND_TOP_COLOR)

    def test_images_render_without_changing_collision_geometry(self) -> None:
        self.save_image("sprite.png", (90, 180, 120, 255))
        objects = (
            Player(20, 20, self.assets.load_image("sprite.png", (64, 32))),
            Coin(100, 100, self.assets.load_image("sprite.png", (24, 24))),
            Obstacle(150, 150, self.assets.load_image("sprite.png", (48, 36))),
        )
        expected_sizes = ((64, 32), (24, 24), (48, 36))
        surface = pygame.Surface((300, 300))
        for obj, size in zip(objects, expected_sizes):
            with self.subTest(object=type(obj).__name__):
                before = obj.get_rect()
                obj.draw(surface)
                self.assertEqual(obj.get_rect(), before)
                self.assertEqual(obj.get_rect().size, size)
                self.assertEqual(tuple(surface.get_at(before.center))[:3], (90, 180, 120))

    def test_image_hit_feedback_preserves_transparency_and_original(self) -> None:
        image = pygame.Surface((64, 32), pygame.SRCALPHA)
        pygame.draw.rect(image, (80, 120, 200, 128), (10, 8, 44, 20))
        player = Player(20, 20, image)
        player.take_damage(1)
        self.assertEqual(tuple(player.hit_image.get_at((20, 15))), (*settings.PLAYER_HIT_COLOR, 128))
        self.assertEqual(player.hit_image.get_at((0, 0)).a, 0)
        self.assertEqual(tuple(image.get_at((20, 15))), (80, 120, 200, 128))

    def test_corrupt_coin_still_draws_default_graphic(self) -> None:
        (self.directory / "coin.png").write_bytes(b"invalid png")
        game = self.create_game()
        with self.assertLogs("asset_manager", level="WARNING"):
            coin = game.spawn_coin()
        self.assertIsNone(coin.image)
        coin.x, coin.y = 100.0, 100.0
        surface = pygame.Surface((200, 200))
        coin.draw(surface)
        self.assertEqual(tuple(surface.get_at((100, 100)))[:3], settings.COIN_COLOR)

    def test_background_creation_does_not_consume_game_random_sequence(self) -> None:
        previous = random.getstate()
        try:
            random.seed(121)
            expected = random.Random(121).random()
            create_background((150, 100))
            self.assertEqual(random.random(), expected)
        finally:
            random.setstate(previous)

    def test_hud_stays_readable_when_objects_cross_it(self) -> None:
        game = self.create_game()
        game.draw()
        hud = pygame.Rect(0, 0, 800, settings.HUD_HEIGHT)
        before = pygame.image.tobytes(game.screen.subsurface(hud), "RGB")
        game.coins = [Coin(400, 57)]
        game.draw()
        self.assertEqual(before, pygame.image.tobytes(game.screen.subsurface(hud), "RGB"))


if __name__ == "__main__":
    unittest.main()
