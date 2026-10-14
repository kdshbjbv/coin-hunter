"""玩家的位置、移动、绘制与碰撞区域。"""

import pygame

import settings


class Player:
    """底部玩家角色；接收移动方向，不直接依赖键盘输入。"""

    def __init__(self, x: float, y: float, image: pygame.Surface | None = None) -> None:
        # 保留浮点位置，避免每帧移动的小数部分丢失。
        self.x = float(x)
        self.y = float(y)
        self.width = settings.PLAYER_WIDTH
        self.height = settings.PLAYER_HEIGHT
        self.speed = settings.PLAYER_SPEED
        self.hp = settings.PLAYER_INITIAL_HP
        self.hit_flash_timer = 0.0
        self.image = image
        self.hit_image = None
        if image is not None:
            # 提前生成受伤颜色版本，保留透明度，不在每帧重新处理图片。
            self.hit_image = image.copy()
            self.hit_image.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self.hit_image.fill((*settings.PLAYER_HIT_COLOR, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def update(self, dt: float, direction: int, screen_width: int) -> None:
        """按秒更新位置；direction 为 -1（左）、0（停）、1（右）。"""
        self.x += direction * self.speed * dt
        # 限制整个角色处于窗口内部，右边界需要扣除角色宽度。
        max_x = max(0.0, float(screen_width - self.width))
        self.x = max(0.0, min(self.x, max_x))
        self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

    def take_damage(self, damage: int) -> None:
        """扣除生命值并触发短暂变色，生命值最低为 0。"""
        self.hp = max(0, self.hp - damage)
        self.hit_flash_timer = settings.PLAYER_HIT_FLASH_DURATION

    def get_rect(self) -> pygame.Rect:
        """根据当前位置生成碰撞区域，供后续金币和障碍物检测使用。"""
        return pygame.Rect(
            round(self.x), round(self.y), self.width, self.height
        )

    def draw(self, surface: pygame.Surface) -> None:
        """优先使用图片；默认角色保留受伤变色并增加轮廓和高光。"""
        rect = self.get_rect()
        if self.image is not None:
            image = self.hit_image if self.hit_flash_timer > 0.0 else self.image
            surface.blit(image, rect)
            return
        color = (
            settings.PLAYER_HIT_COLOR
            if self.hit_flash_timer > 0.0 else settings.PLAYER_COLOR
        )
        pygame.draw.rect(
            surface, color, rect, border_radius=8
        )
        pygame.draw.rect(surface, settings.PLAYER_BORDER_COLOR, rect, width=2, border_radius=8)
        pygame.draw.line(
            surface, settings.PLAYER_HIGHLIGHT_COLOR,
            (rect.left + 10, rect.top + 4), (rect.right - 11, rect.top + 4), width=2,
        )
        for eye_x in (rect.left + 16, rect.right - 17):
            pygame.draw.circle(surface, settings.BACKGROUND_TOP_COLOR, (eye_x, rect.top + 12), 3)
