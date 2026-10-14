"""金币的位置、下落、绘制与离屏判断。"""

import pygame

import settings


class Coin:
    """独立金币对象；生成和生命周期由游戏管理器协调。"""

    def __init__(self, x: float, y: float, image: pygame.Surface | None = None) -> None:
        self.x = float(x)
        self.y = float(y)
        self.radius = settings.COIN_RADIUS
        self.speed = settings.COIN_SPEED
        self.value = settings.COIN_VALUE
        self.image = image

    def update(self, dt: float) -> None:
        """按秒向下移动，保留浮点位置。"""
        self.y += self.speed * dt

    def is_off_screen(self, screen_height: int) -> bool:
        """整个金币越过窗口底边后才允许清理。"""
        return self.y - self.radius >= screen_height

    def get_rect(self) -> pygame.Rect:
        """返回金币的外接矩形，供玩家碰撞检测使用。"""
        return pygame.Rect(
            round(self.x) - self.radius,
            round(self.y) - self.radius,
            self.radius * 2,
            self.radius * 2,
        )

    def draw(self, surface: pygame.Surface) -> None:
        """优先使用图片；默认金币增加内圈与高光。"""
        if self.image is not None:
            surface.blit(self.image, self.get_rect())
            return
        center = (round(self.x), round(self.y))
        pygame.draw.circle(surface, settings.COIN_COLOR, center, self.radius)
        pygame.draw.circle(
            surface, settings.COIN_BORDER_COLOR, center, self.radius, width=2
        )
        pygame.draw.circle(surface, settings.COIN_BORDER_COLOR, center, self.radius - 4, width=1)
        pygame.draw.circle(surface, (255, 245, 175), (center[0] - 4, center[1] - 4), 2)
