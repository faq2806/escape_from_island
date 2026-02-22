from dataclasses import dataclass
from typing import Optional, Tuple

import pygame


@dataclass
class DifficultyProfile:
    name: str
    player_health: int
    stamina_drain: float
    stamina_recover: float
    guard_speed: float
    guard_sight: int
    guard_shoot_cooldown: float
    guard_health: int
    guard_damage: int
    player_damage: int
    extra_guards: int


@dataclass
class ZoneGate:
    rect: pygame.Rect
    target_zone: str
    spawn: Tuple[int, int]
    required_key: Optional[str] = None
