"""管理游戏主循环、输入处理、状态更新和画面绘制。"""

import random
from enum import Enum, auto
from typing import Callable

import pygame

import settings
from asset_manager import AssetManager
from coin import Coin
from difficulty import Difficulty
from obstacle import Obstacle
from player import Player
from utils import create_background, draw_centered_text, draw_heart, draw_panel


class GameState(Enum):
    """每局游戏状态；窗口是否继续运行由 running 单独管理。"""

    PLAYING = auto()
    GAME_OVER = auto()


class GameManager:
    """协调输入、玩家、下落对象、碰撞计分和伤害，以及绘制。"""

    def __init__(self) -> None:
        # Pygame 由入口初始化；这里只创建游戏需要的资源。
        self.screen = pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        )
        pygame.display.set_caption(settings.GAME_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.title_font = pygame.font.Font(None, settings.TITLE_FONT_SIZE)
        self.body_font = pygame.font.Font(None, settings.BODY_FONT_SIZE)
        self.detail_font = pygame.font.Font(None, settings.HUD_DETAIL_FONT_SIZE)
        self.brand_font = pygame.font.Font(None, settings.BRAND_FONT_SIZE)
        self.assets = AssetManager()
        self.background = create_background(self.screen.get_size())
        background_image = self.assets.load_image(settings.BACKGROUND_IMAGE, self.screen.get_size())
        if background_image is not None:
            # 将透明背景合成到不透明底图，避免逐帧绘制留下拖影。
            self.background.blit(background_image, (0, 0))
        self.game_over_overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        self.game_over_overlay.fill(settings.GAME_OVER_OVERLAY_COLOR)
        self.reset_game()

    def reset_game(self) -> None:
        """初始化一局数据；重用窗口、字体和时钟，不递归启动主循环。"""
        # 游戏操作不需要文字输入，重开后也保持输入法编辑关闭。
        pygame.key.stop_text_input()
        self.player = Player(
            x=(self.screen.get_width() - settings.PLAYER_WIDTH) / 2,
            y=(
                self.screen.get_height()
                - settings.PLAYER_HEIGHT
                - settings.PLAYER_BOTTOM_MARGIN
            ),
            image=self.assets.load_image(settings.PLAYER_IMAGE, (settings.PLAYER_WIDTH, settings.PLAYER_HEIGHT)),
        )
        self.coins: list[Coin] = []
        self.coin_spawn_timer = 0.0
        self.obstacles: list[Obstacle] = []
        self.obstacle_spawn_timer = 0.0
        self.score = 0
        self.game_time = 0.0
        self.difficulty = Difficulty.from_game_time(self.game_time)
        self.state = GameState.PLAYING

    def run(self) -> None:
        """依次处理输入、更新状态、绘制并刷新窗口。"""
        while self.running:
            # 将毫秒换算成秒，后续对象使用 speed * dt 实现移动。
            dt = self.clock.tick(settings.FPS) / 1000.0
            self.handle_events()
            if not self.running:
                break
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def handle_events(self) -> None:
        """处理退出、结束后重新开始，以及恢复焦点时的输入模式。"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif (
                    self.running
                    and self.state == GameState.GAME_OVER
                    and event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_KP_ENTER)
                ):
                    self.reset_game()
            elif event.type == pygame.WINDOWFOCUSGAINED:
                # 切回窗口后仍保持游戏操作模式，不启动输入法编辑。
                pygame.key.stop_text_input()

    def update(self, dt: float) -> None:
        """仅在进行中更新玩法；结束或失去焦点时停止更新。"""
        if self.state != GameState.PLAYING or not pygame.key.get_focused():
            return
        if self.player.hp <= 0:
            self.state = GameState.GAME_OVER
            return
        self.game_time += dt
        self.update_difficulty()
        keys = pygame.key.get_pressed()
        move_left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        move_right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        # 同向双键不会加倍速度；左右同时按下时 direction 为 0。
        direction = int(move_right) - int(move_left)
        self.player.update(dt, direction, self.screen.get_width())
        self.update_coins(dt)
        self.collect_coins()
        self.update_obstacles(dt)
        self.handle_obstacle_collisions()

    def update_difficulty(self) -> None:
        """同步速度与生成间隔，保留障碍计时器已经完成的比例。"""
        old_interval = self.difficulty.obstacle_spawn_interval
        new_difficulty = Difficulty.from_game_time(self.game_time)
        self.obstacle_spawn_timer *= new_difficulty.obstacle_spawn_interval / old_interval
        self.difficulty = new_difficulty
        for coin in self.coins:
            coin.speed = self.difficulty.coin_speed
        for obstacle in self.obstacles:
            obstacle.speed = self.difficulty.obstacle_speed

    @staticmethod
    def _spawn_due_objects(
        dt: float,
        timer: float,
        interval: float,
        spawn: Callable[[], Coin | Obstacle],
    ) -> float:
        """共用生成计时；spawn 创建并登记对象，返回保留的时间。"""
        timer += dt
        while timer >= interval:
            timer -= interval
            obj = spawn()
            # 补上对象在本帧生成后经过的时间，减少帧率差异。
            obj.update(timer)
        return timer

    def spawn_coin(self) -> Coin:
        """在顶部随机位置创建金币，横坐标预留半径边距。"""
        radius = settings.COIN_RADIUS
        coin = Coin(
            x=random.uniform(radius, self.screen.get_width() - radius),
            y=-radius,
            image=self.assets.load_image(settings.COIN_IMAGE, (radius * 2, radius * 2)),
        )
        coin.speed = self.difficulty.coin_speed
        self.coins.append(coin)
        return coin

    def update_coins(self, dt: float) -> None:
        """更新下落、累计生成计时，并清理完全离屏的金币。"""
        for coin in self.coins:
            coin.update(dt)

        self.coin_spawn_timer = self._spawn_due_objects(
            dt, self.coin_spawn_timer, settings.COIN_SPAWN_INTERVAL, self.spawn_coin
        )

        # 创建保留列表，避免一边遍历一边删除造成漏删。
        self.coins = [
            coin for coin in self.coins
            if not coin.is_off_screen(self.screen.get_height())
        ]

    def collect_coins(self) -> None:
        """接住金币后按其价值计分，并移除已接住的金币。"""
        player_rect = self.player.get_rect()
        remaining_coins: list[Coin] = []
        for coin in self.coins:
            if player_rect.colliderect(coin.get_rect()):
                self.score += coin.value
            else:
                remaining_coins.append(coin)
        # 同一帧可接到多枚金币，移除后后续帧不会重复计分。
        self.coins = remaining_coins

    def spawn_obstacle(self) -> Obstacle:
        """在顶部随机位置创建障碍物，保证整个宽度位于窗口内。"""
        obstacle = Obstacle(
            x=random.uniform(0, self.screen.get_width() - settings.OBSTACLE_WIDTH),
            y=-settings.OBSTACLE_HEIGHT,
            image=self.assets.load_image(settings.OBSTACLE_IMAGE, (settings.OBSTACLE_WIDTH, settings.OBSTACLE_HEIGHT)),
        )
        obstacle.speed = self.difficulty.obstacle_speed
        self.obstacles.append(obstacle)
        return obstacle

    def update_obstacles(self, dt: float) -> None:
        """更新障碍下落、生成计时，并清理完全离屏的障碍物。"""
        for obstacle in self.obstacles:
            obstacle.update(dt)
        self.obstacle_spawn_timer = self._spawn_due_objects(
            dt,
            self.obstacle_spawn_timer,
            self.difficulty.obstacle_spawn_interval,
            self.spawn_obstacle,
        )
        self.obstacles = [
            obstacle for obstacle in self.obstacles
            if not obstacle.is_off_screen(self.screen.get_height())
        ]

    def handle_obstacle_collisions(self) -> None:
        """每个相撞障碍只造成一次伤害，移除后避免连续帧重复扣血。"""
        player_rect = self.player.get_rect()
        remaining_obstacles: list[Obstacle] = []
        for obstacle in self.obstacles:
            if player_rect.colliderect(obstacle.get_rect()):
                self.player.take_damage(obstacle.damage)
            else:
                remaining_obstacles.append(obstacle)
        self.obstacles = remaining_obstacles
        if self.player.hp <= 0:
            self.state = GameState.GAME_OVER

    def draw(self) -> None:
        """绘制游戏场景、HUD，并根据状态显示结束界面。"""
        self.screen.blit(self.background, (0, 0))
        for coin in self.coins:
            coin.draw(self.screen)
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)
        self.player.draw(self.screen)
        self.draw_hud()
        if self.state == GameState.GAME_OVER:
            self.draw_game_over()
            return
        center_x = self.screen.get_width() // 2
        draw_centered_text(
            self.screen,
            "ARROWS / A D  |  ESC TO EXIT",
            self.detail_font,
            settings.MUTED_TEXT_COLOR,
            (center_x, self.screen.get_height() - 12),
        )
        if not pygame.key.get_focused():
            draw_panel(self.screen, pygame.Rect(center_x - 220, 230, 440, 95))
            draw_centered_text(
                self.screen, "PAUSED", self.brand_font, settings.TEXT_COLOR, (center_x, 255)
            )
            draw_centered_text(
                self.screen,
                "Click this window to enable movement",
                self.body_font,
                settings.TEXT_COLOR,
                (center_x, 295),
            )

    def draw_hud(self) -> None:
        """左上角显示分数，右上角用心形显示剩余生命值。"""
        pygame.draw.rect(
            self.screen, settings.BACKGROUND_TOP_COLOR,
            (0, 0, self.screen.get_width(), settings.HUD_HEIGHT),
        )
        pygame.draw.line(
            self.screen, settings.PANEL_BORDER_COLOR,
            (0, settings.HUD_HEIGHT), (self.screen.get_width() - 1, settings.HUD_HEIGHT),
        )
        draw_panel(self.screen, pygame.Rect(10, 10, 250, 68))
        draw_panel(self.screen, pygame.Rect(self.screen.get_width() - 170, 10, 160, 54))
        center_x = self.screen.get_width() // 2
        draw_centered_text(
            self.screen, settings.GAME_TITLE, self.brand_font, settings.TEXT_COLOR, (center_x, 30)
        )
        draw_centered_text(
            self.screen, "CATCH GOLD. DODGE RED.", self.detail_font,
            settings.MUTED_TEXT_COLOR, (center_x, 57),
        )
        score_surface = self.body_font.render(
            f"Score: {self.score}", True, settings.TEXT_COLOR
        )
        margin = settings.HUD_MARGIN
        self.screen.blit(score_surface, (margin, margin))
        detail_surface = self.detail_font.render(
            f"Time: {int(self.game_time)}s | Speed: x{self.difficulty.speed_multiplier:.2f}",
            True,
            settings.MUTED_TEXT_COLOR,
        )
        self.screen.blit(detail_surface, (margin, margin + self.body_font.get_height() + 8))
        bar_rect = pygame.Rect(margin, 69, 230, 3)
        pygame.draw.rect(self.screen, settings.PANEL_BORDER_COLOR, bar_rect)
        if self.difficulty.progress > 0.0:
            pygame.draw.rect(
                self.screen, settings.ACCENT_COLOR,
                (bar_rect.x, bar_rect.y, round(bar_rect.width * self.difficulty.progress), bar_rect.height),
            )
        slots = settings.PLAYER_INITIAL_HP
        hearts_width = slots * settings.HEART_SIZE + (slots - 1) * settings.HEART_GAP
        hearts_x = self.screen.get_width() - margin - hearts_width
        hp_label = self.body_font.render("HP:", True, settings.TEXT_COLOR)
        self.screen.blit(
            hp_label,
            (
                hearts_x - hp_label.get_width() - 10,
                margin + (settings.HEART_SIZE - hp_label.get_height()) // 2,
            ),
        )
        for index in range(slots):
            color = settings.HEART_COLOR if index < self.player.hp else settings.HEART_EMPTY_COLOR
            rect = pygame.Rect(
                hearts_x + index * (settings.HEART_SIZE + settings.HEART_GAP),
                margin,
                settings.HEART_SIZE,
                settings.HEART_SIZE,
            )
            draw_heart(self.screen, color, rect)

    def draw_game_over(self) -> None:
        """在冻结的场景上覆盖结束提示，保留最终分数。"""
        self.screen.blit(self.game_over_overlay, (0, 0))
        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2
        draw_panel(self.screen, pygame.Rect(center_x - 240, center_y - 130, 480, 250))
        draw_centered_text(
            self.screen,
            "GAME OVER",
            self.title_font,
            settings.TEXT_COLOR,
            (center_x, center_y - 60),
        )
        draw_centered_text(
            self.screen,
            f"Final Score: {self.score}",
            self.body_font,
            settings.TEXT_COLOR,
            (center_x, center_y),
        )
        draw_centered_text(
            self.screen,
            "Press R or Enter to restart",
            self.body_font,
            settings.MUTED_TEXT_COLOR,
            (center_x, center_y + 50),
        )
        draw_centered_text(
            self.screen,
            "Press Esc to exit",
            self.body_font,
            settings.MUTED_TEXT_COLOR,
            (center_x, center_y + 85),
        )
