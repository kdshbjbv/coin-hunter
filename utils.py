"""可复用的文字与心形绘图工具。"""

import random

import pygame

import settings


def draw_centered_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    center: tuple[int, int],
) -> None:
    """以指定坐标为中心绘制文字。"""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=center)
    surface.blit(text_surface, text_rect)


def draw_heart(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """使用圆形与三角形绘制心形，避免依赖字体中的 Emoji 字形。"""
    radius = rect.width // 4
    pygame.draw.circle(surface, color, (rect.left + radius, rect.top + radius), radius)
    pygame.draw.circle(
        surface, color, (rect.right - radius - 1, rect.top + radius), radius
    )
    pygame.draw.polygon(
        surface,
        color,
        [
            (rect.left, rect.top + radius),
            (rect.right - 1, rect.top + radius),
            (rect.centerx, rect.bottom - 1),
        ],
    )


def draw_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """绘制统一的圆角面板与细描边。"""
    pygame.draw.rect(surface, settings.PANEL_COLOR, rect, border_radius=12)
    pygame.draw.rect(surface, settings.PANEL_BORDER_COLOR, rect, width=1, border_radius=12)


def create_background(size: tuple[int, int]) -> pygame.Surface:
    """一次性生成渐变、星点和底部平台，不消耗游戏生成对象的随机序列。"""
    width, height = size
    background = pygame.Surface(size).convert()
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(
            round(top + (bottom - top) * ratio)
            for top, bottom in zip(settings.BACKGROUND_TOP_COLOR, settings.BACKGROUND_BOTTOM_COLOR)
        )
        pygame.draw.line(background, color, (0, y), (width - 1, y))
    rng = random.Random(7)
    star_top = min(settings.HUD_HEIGHT + 1, height - 1)
    star_bottom = max(star_top + 1, height - 45)
    for _ in range(70):
        position = (rng.randrange(width), rng.randrange(star_top, star_bottom))
        pygame.draw.circle(background, settings.STAR_COLOR, position, 1)
    for x in range(40, width, 80):
        pygame.draw.line(background, settings.GRID_COLOR, (x, settings.HUD_HEIGHT + 6), (x, height - 24))
    ground_y = max(0, height - settings.PLAYER_BOTTOM_MARGIN)
    pygame.draw.rect(background, settings.GROUND_COLOR, (0, ground_y, width, height - ground_y))
    pygame.draw.line(background, settings.PANEL_BORDER_COLOR, (0, ground_y), (width - 1, ground_y))
    return background
