"""障碍物的位置、下落、绘制与离屏判断。"""

import pygame

import settings


class Obstacle:
    """矩形障碍物；生成和玩家碰撞由游戏管理器协调。"""

    def __init__(self, x: float, y: float, image: pygame.Surface | None = None) -> None:
        self.x = float(x)
        self.y = float(y)
        self.width = settings.OBSTACLE_WIDTH
        self.height = settings.OBSTACLE_HEIGHT
        self.speed = settings.OBSTACLE_SPEED
        self.damage = settings.OBSTACLE_DAMAGE
        self.image = image

    def update(self, dt: float) -> None:
        """按秒向下移动，保留浮点位置。"""
        self.y += self.speed * dt

    def is_off_screen(self, screen_height: int) -> bool:
        """障碍物顶边越过窗口底边，表示整个障碍物已离屏。"""
        return self.y >= screen_height

    def get_rect(self) -> pygame.Rect:
        """返回与绘制位置一致的矩形碰撞区域。"""
        return pygame.Rect(
            round(self.x), round(self.y), self.width, self.height
        )

    def draw(self, surface: pygame.Surface) -> None:
        """优先使用图片；默认障碍增加内边框与铆钉细节。"""
        rect = self.get_rect()
        if self.image is not None:
            surface.blit(self.image, rect)
            return
        pygame.draw.rect(surface, settings.OBSTACLE_COLOR, rect)
        pygame.draw.rect(surface, settings.OBSTACLE_BORDER_COLOR, rect, width=3)
        pygame.draw.rect(surface, (255, 150, 160), rect.inflate(-10, -10), width=1)
        for x in (rect.left + 7, rect.right - 8):
            for y in (rect.top + 7, rect.bottom - 8):
                pygame.draw.circle(surface, settings.OBSTACLE_BORDER_COLOR, (x, y), 2)
