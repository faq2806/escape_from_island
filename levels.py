import pygame
import math
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from entities import Guard
import math  # Make sure math is imported for the calculations

# Import settings
import settings

WIDTH = settings.WIDTH
HEIGHT = settings.HEIGHT

@dataclass
class ZoneGate:
    rect: pygame.Rect
    target_zone: str
    spawn: Tuple[int, int]
    required_key: Optional[str] = None

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

# Difficulty profiles
DIFFICULTIES: List[DifficultyProfile] = [
    DifficultyProfile("Story", 120, 24.0, 20.0, 1.45, 260, 1.2, 38, 12, 24, 0),
    DifficultyProfile("Survivor", 95, 30.0, 15.0, 1.9, 340, 0.85, 55, 18, 20, 1),
    DifficultyProfile("Nightmare", 75, 38.0, 11.0, 2.4, 420, 0.62, 70, 24, 18, 2),
]

def gradient_fill(screen, top_color, bottom_color):
    """Draw a gradient background"""
    for y in range(settings.HEIGHT):
        ratio = y / settings.HEIGHT
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        pygame.draw.line(screen, (r, g, b), (0, y), (settings.WIDTH, y))

def pulsing(anim_time, speed=3.0, max_val=30):
    """Return a pulsing value for effects"""
    return int((math.sin(anim_time * speed) + 1) / 2 * max_val)

def build_zone_data(zone: str):
    """Build obstacles, gates, and extraction point for each zone"""
    obstacles: List[pygame.Rect] = []
    gates: List[ZoneGate] = []
    extraction = None

    border = [
        pygame.Rect(0, 0, WIDTH, 40),  # Top border
        pygame.Rect(0, HEIGHT - 40, WIDTH, 40),  # Bottom border
        pygame.Rect(0, 0, 40, HEIGHT),  # Left border
        pygame.Rect(WIDTH - 40, 0, 40, HEIGHT)  # Right border
    ]
    
    if zone == "Ground":
        obstacles = border + [
            pygame.Rect(270, 90, 620, 24), 
            pygame.Rect(270, 90, 24, 220), 
            pygame.Rect(866, 90, 24, 200),
            pygame.Rect(180, 320, 560, 24), 
            pygame.Rect(716, 320, 24, 210), 
            pygame.Rect(330, 530, 410, 24),
        ]
        gates = [ZoneGate(pygame.Rect(52, 84, 54, 92), "Estate", (1060, 620), "jail_key")]
        
    elif zone == "Estate":
        obstacles = border + [
            pygame.Rect(130, 180, 840, 24), 
            pygame.Rect(130, 180, 24, 360), 
            pygame.Rect(946, 180, 24, 360),
            pygame.Rect(350, 340, 430, 24), 
            pygame.Rect(350, 340, 24, 180), 
            pygame.Rect(756, 340, 24, 180),
            pygame.Rect(550, 530, 230, 24),
        ]
        gates = [
            ZoneGate(pygame.Rect(1082, 620, 56, 56), "Ground", (100, 140)),
            ZoneGate(pygame.Rect(80, 620, 60, 60), "Tunnels", (1040, 600), "cave_key")
        ]
        
    elif zone == "Tunnels":
        obstacles = border + [
            pygame.Rect(120, 120, 200, 20),  # Top left horizontal
            pygame.Rect(400, 120, 500, 20),  # Top right horizontal
            pygame.Rect(120, 120, 20, 300),  # Left vertical
            pygame.Rect(880, 120, 20, 300),  # Right vertical
            pygame.Rect(120, 400, 300, 20),  # Middle left horizontal
            pygame.Rect(500, 400, 400, 20),  # Middle right horizontal
            pygame.Rect(400, 200, 20, 220),  # Center vertical divider
            pygame.Rect(600, 200, 20, 220),  # Another vertical divider
            pygame.Rect(120, 520, 300, 20),  # Bottom left horizontal
            pygame.Rect(580, 520, 300, 20),  # Bottom right horizontal
            pygame.Rect(120, 400, 20, 140),  # Bottom left vertical
            pygame.Rect(860, 400, 20, 140),  # Bottom right vertical
            pygame.Rect(250, 220, 100, 20),  # Top chamber wall
            pygame.Rect(650, 220, 100, 20),  # Another top chamber
        ]
        gates = [
            ZoneGate(pygame.Rect(1082, 620, 56, 56), "Estate", (120, 620)),
            ZoneGate(pygame.Rect(70, 80, 80, 80), "Harbor", (500, 400), "boat_key")  # Fixed spawn point
        ]
        
    elif zone == "Harbor":
        obstacles = border + [
            # Ground area (bottom portion) - this is the WALKABLE area
            # No obstacles here for the main ground
            
            # Buildings/structures at harbor - these should be obstacles
            pygame.Rect(200, 400, 150, 80),   # Warehouse 1 (obstacle)
            pygame.Rect(500, 450, 120, 60),   # Warehouse 2 (obstacle)
            pygame.Rect(900, 400, 150, 70),   # Harbor office (obstacle)
            
            # Small obstacles - things you can't walk through
            pygame.Rect(300, 550, 40, 40),    # Crate stack (obstacle)
            pygame.Rect(600, 350, 40, 40),    # Crate stack (obstacle)
            pygame.Rect(400, 500, 30, 30),    # Barrel (obstacle)
            pygame.Rect(700, 500, 30, 30),    # Barrel (obstacle)
            
            # Pier supports/pilings (obstacles)
            pygame.Rect(820, 180, 15, 60),    # Piling 1 (moved down)
            pygame.Rect(920, 180, 15, 60),    # Piling 2 (moved down)
            pygame.Rect(1020, 180, 15, 60),   # Piling 3 (moved down)
        ]
        
        # Pier - make it longer and more accessible
        # The pier is at pygame.Rect(800, 200, 300, 40) - not an obstacle
        
        # Portal at bottom (going back to Tunnels)
        gates = [
            ZoneGate(pygame.Rect(1080, 620, 60, 60), "Tunnels", (160, 140), None)
        ]
        
        # Boat extraction point - moved to a more accessible location
        # Option 1: At the end of the pier but lower (more reachable)
        extraction = pygame.Rect(1020, 210, 80, 40)  # Boat lower on pier
        
        # Option 2: On the ground near the pier
        # extraction = pygame.Rect(850, 320, 80, 40)  # Boat on ground
        
        # Option 3: At the base of the pier (most accessible)
        # extraction = pygame.Rect(820, 260, 80, 40)  # Boat at pier base
    
    # IMPORTANT: Always return something
    return obstacles, gates, extraction

def build_guards(profile):
    """Build guards for each zone based on difficulty"""
    guards = {
        "Ground": [],
        "Estate": [],
        "Tunnels": [],
        "Harbor": []
    }
    
    # This is a simplified version - you can expand this later
    return guards

def build_items():
    """Build initial item positions (will be randomized in game)"""
    items = {
        "Ground": {
            "gun": pygame.Rect(200, 550, 24, 12),
            "ammo": [pygame.Rect(300, 200, 16, 10), pygame.Rect(800, 500, 16, 10)],
            "clue": pygame.Rect(400, 300, 20, 14),
            "jail_key": pygame.Rect(500, 400, 18, 12),
        },
        "Estate": {
            "clue": pygame.Rect(250, 250, 20, 14),
            "cave_key": pygame.Rect(700, 400, 18, 12),
            "ammo": [pygame.Rect(300, 350, 16, 10)],
        },
        "Tunnels": {
            "clue": pygame.Rect(500, 200, 20, 14),
            "ammo": [pygame.Rect(600, 350, 16, 10), pygame.Rect(300, 500, 16, 10)],
            "boat_key": pygame.Rect(800, 200, 18, 12),
        },
        "Harbor": {},
    }
    return items

def build_decor():
    """Build decorative elements for each zone"""
    decor = {
        "Ground": {
            "trees": [(140, 140), (210, 550), (610, 250), (810, 610), (980, 520)],
            "bushes": [(300, 520), (740, 160), (520, 640), (1040, 300)]
        },
        "Estate": {
            "hedges": [
                pygame.Rect(150, 110, 280, 26), 
                pygame.Rect(520, 110, 300, 26), 
                pygame.Rect(890, 110, 170, 26)
            ],
            "fountains": [pygame.Rect(620, 470, 90, 90)]
        },
        "Tunnels": {
            "crystals": [
                pygame.Rect(130, 130, 22, 36), 
                pygame.Rect(900, 250, 22, 36), 
                pygame.Rect(260, 610, 22, 36)
            ],
            "pools": [
                pygame.Rect(720, 110, 180, 70), 
                pygame.Rect(840, 530, 160, 55)
            ]
        },
        "Harbor": {
            "water": [(0, 0, WIDTH, 250)],
            "boats": [pygame.Rect(850, 320, 100, 40)],
            "crates": [pygame.Rect(300, 550, 40, 40), pygame.Rect(600, 350, 40, 40)],
            "barrels": [(400, 500), (700, 500)],
            "fishing_gear": [(350, 480), (550, 480)],
            "seagulls": [(300, 200), (600, 150), (900, 250)]
        }
    }
    return decor


def build_guards(profile):
    """Build guards for each zone based on difficulty"""
    guards = {
        "Ground": [],
        "Estate": [],
        "Tunnels": [],
        "Harbor": []
    }
    
    # Define base guard positions for each zone
    base_guard_configs = {
        "Ground": [
            (540, 500, [(500, 500), (760, 500), (760, 640), (500, 640)]),
            (950, 250, [(900, 210), (1080, 210), (1080, 420), (900, 420)]),
        ],
        "Estate": [
            (350, 300, [(250, 300), (550, 300)]),
            (850, 520, [(760, 520), (1040, 520)]),
        ],
        "Tunnels": [
            (700, 300, [(620, 260), (920, 340), (620, 500)]),
        ],
        "Harbor": [
            (800, 420, [(680, 420), (1000, 420)]),
        ],
    }
    
    # Extra guards for higher difficulties
    extra_guard_configs = {
        "Ground": [
            (760, 180, [(680, 180), (860, 180), (860, 300), (680, 300)]),
            (420, 210, [(360, 200), (520, 200), (520, 300), (360, 300)]),
        ],
        "Estate": [
            (1010, 230, [(940, 220), (1080, 220), (1080, 320), (940, 320)]),
            (140, 500, [(100, 450), (220, 520)]),
        ],
        "Tunnels": [
            (350, 460, [(300, 420), (480, 500), (320, 560)]),
            (980, 140, [(930, 120), (1080, 180)]),
        ],
        "Harbor": [
            (620, 280, [(560, 260), (760, 260)]),
            (1000, 520, [(900, 500), (1080, 580)]),
        ],
    }
    
    # Function to check if a position is valid (not inside obstacles)
    def is_valid_position(x, y, zone):
        # Get obstacles for this zone
        obstacles, _, _ = build_zone_data(zone)
        
        # Create a test rect for the guard
        test_rect = pygame.Rect(x, y, 22, 32)
        
        # Check collision with any obstacle
        for obstacle in obstacles:
            if test_rect.colliderect(obstacle):
                return False
        
        # Also check if too close to zone borders
        if x < 60 or x > settings.WIDTH - 100 or y < 60 or y > settings.HEIGHT - 100:
            return False
            
        return True
    
    # Function to find a valid spawn position near the intended location
    def find_valid_spawn(intended_x, intended_y, zone, max_attempts=20):
        if is_valid_position(intended_x, intended_y, zone):
            return (intended_x, intended_y)
        
        # Try to find a nearby valid position
        for attempt in range(max_attempts):
            angle = attempt * 0.5
            radius = 20 + attempt * 10
            test_x = intended_x + int(radius * math.cos(angle))
            test_y = intended_y + int(radius * math.sin(angle))
            
            # Clamp to screen bounds
            test_x = max(60, min(settings.WIDTH - 100, test_x))
            test_y = max(60, min(settings.HEIGHT - 100, test_y))
            
            if is_valid_position(test_x, test_y, zone):
                return (test_x, test_y)
        
        # Safe fallback positions
        safe_spots = {
            "Ground": (200, 600),
            "Estate": (200, 400),
            "Tunnels": (200, 300),
            "Harbor": (200, 500),
        }
        return safe_spots.get(zone, (200, 200))
    
    # Add base guards
    for zone in base_guard_configs:
        for x, y, patrol in base_guard_configs[zone]:
            spawn_x, spawn_y = find_valid_spawn(x, y, zone)
            guard = Guard(spawn_x, spawn_y, patrol, profile)
            guards[zone].append(guard)
    
    # Add extra guards based on difficulty
    for zone in extra_guard_configs:
        extras_to_add = extra_guard_configs[zone][:profile.extra_guards]
        for x, y, patrol in extras_to_add:
            spawn_x, spawn_y = find_valid_spawn(x, y, zone)
            guard = Guard(spawn_x, spawn_y, patrol, profile)
            guards[zone].append(guard)
    
    return guards