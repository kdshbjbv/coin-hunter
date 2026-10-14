"""Coin Hunter 游戏入口。"""

import pygame

from game_manager import GameManager


def main() -> None:
    """初始化 Pygame，并确保退出时释放资源。"""
    try:
        pygame.init()
        game = GameManager()
        game.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
