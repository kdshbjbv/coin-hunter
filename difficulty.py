"""根据有效游戏时间计算难度，不处理输入、对象移动或绘制。"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Difficulty:
    """某个时间点的难度参数；不可变，便于测试与复用。"""

    progress: float
    speed_multiplier: float
    coin_speed: float
    obstacle_speed: float
    obstacle_spawn_interval: float

    @classmethod
    def from_game_time(cls, game_time: float) -> "Difficulty":
        """适应期后线性提升，达到上限后保持稳定。"""
        active_time = max(0.0, game_time - settings.DIFFICULTY_WARMUP)
        progress = min(active_time / settings.DIFFICULTY_RAMP_DURATION, 1.0)
        multiplier = 1.0 + (settings.MAX_SPEED_MULTIPLIER - 1.0) * progress
        interval = (
            settings.OBSTACLE_SPAWN_INTERVAL
            + (
                settings.MIN_OBSTACLE_SPAWN_INTERVAL
                - settings.OBSTACLE_SPAWN_INTERVAL
            ) * progress
        )
        return cls(
            progress=progress,
            speed_multiplier=multiplier,
            coin_speed=settings.COIN_SPEED * multiplier,
            obstacle_speed=settings.OBSTACLE_SPEED * multiplier,
            obstacle_spawn_interval=max(settings.MIN_OBSTACLE_SPAWN_INTERVAL, interval),
        )
