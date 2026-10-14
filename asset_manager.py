"""可选图片资源加载与缓存；缺失或损坏时使用默认图形。"""

import logging
from pathlib import Path

import pygame

import settings


class AssetManager:
    """创建窗口后使用；相同文件和尺寸只加载、缩放一次。"""

    def __init__(self, images_dir: Path = settings.IMAGES_DIR) -> None:
        self.images_dir = Path(images_dir)
        self._cache: dict[tuple[str, tuple[int, int]], pygame.Surface | None] = {}

    def load_image(self, filename: str, size: tuple[int, int]) -> pygame.Surface | None:
        """加载透明图片并缩放到目标尺寸；返回 None 表示使用图形回退。"""
        key = (filename, size)
        if key in self._cache:
            return self._cache[key]
        path = self.images_dir / filename
        try:
            if not path.is_file():
                self._cache[key] = None
                return None
            image = pygame.image.load(str(path)).convert_alpha()
            image = pygame.transform.smoothscale(image, size)
        except (pygame.error, OSError) as error:
            logging.getLogger(__name__).warning("图片 %s 加载失败，使用默认图形：%s", path, error)
            image = None
        self._cache[key] = image
        return image
