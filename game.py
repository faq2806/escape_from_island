import math
import random
from typing import Dict, List, Tuple

import pygame
from audio import AudioManager
from entities import Bullet, NPC, Player, Guard
from levels import DIFFICULTIES, build_decor, build_guards, build_items, build_zone_data, gradient_fill, pulsing, ZoneGate
import settings


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Escape the Secret Island")
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(settings.FONT_NAME, 22)
        self.small_font = pygame.font.SysFont(settings.FONT_NAME, 18)
        self.large_font = pygame.font.SysFont(settings.FONT_NAME, 48)

        self.audio = AudioManager()
        self.state = "menu"
        self.selected_difficulty = 1
        self.profile = DIFFICULTIES[self.selected_difficulty]

        self.zone = "Ground"
        self.region_order = ["Ground", "Estate", "Tunnels", "Harbor"]
        self.player = Player(100, 600, self.profile)
        self.message = "Choose difficulty to begin."
        self.message_time = 0.0
        self.water_anim = 0.0
        self.controls_timer = 10.0
        self.ui_collapsed = False
        self.pathway_cooldown = 0.0
        self.pathway_hint_cooldown = 0.0
        self.creepy_flicker = 0.0
        self.damage_flash_timer = 0.0

        self.boat_escape_active = False
        self.boat_x = 1080
        self.boat_y = 70
        self.followers_in_boat: List[NPC] = []

        self.running = True
        self.game_over = False
        self.victory = False

        self.bullets: List[Bullet] = []
        self.guards: Dict[str, list] = {}
        self.npcs: List[NPC] = []
        self.collected = set()
        self.items = build_items()
        self.decor = build_decor()
        
        # Load sprites
        self.load_sprites()

    def load_sprites(self):
        """Load all game sprites"""
        try:
            # Load tree sprite if available
            original_tree = pygame.image.load("tree.png").convert_alpha()
            self.tree_sprite = pygame.transform.scale(
                original_tree,
                (original_tree.get_width() * 4, original_tree.get_height() * 4)
            )
            print(f"Tree sprite loaded! Size: {self.tree_sprite.get_size()}")
        except:
            self.tree_sprite = None
            print("Tree sprite not found, using fallback drawing")

    def randomize_spawns(self):
        """Randomize positions of guards, keys, and items with collision checking"""

        # Define expanded safe zones with more positions
        safe_zones = {
            "Ground": [
                (150, 550), (300, 200), (800, 500), (1000, 300), (500, 400),
                (250, 600), (700, 200), (900, 550), (400, 300), (600, 500)
            ],
            "Estate": [
                (250, 250), (700, 400), (900, 200), (400, 500),
                (300, 350), (600, 300), (500, 200), (800, 450)
            ],
            "Tunnels": [
                (200, 200), (500, 200), (800, 200), (300, 350), 
                (600, 350), (200, 500), (500, 500), (800, 500),
                (400, 250), (700, 450), (350, 400), (550, 300)
            ],
            "Harbor": [(800, 300), (600, 400), (400, 200), (500, 300), (700, 350)]
        }

        # Get obstacles for each zone to check collisions
        zone_obstacles = {}
        for zone in safe_zones:
            try:
                obstacles, _, _ = build_zone_data(zone)
                zone_obstacles[zone] = obstacles if obstacles else []
            except:
                # If build_zone_data fails, use empty obstacles list
                zone_obstacles[zone] = []
                print(f"Warning: Could not get obstacles for {zone}")

        def is_position_safe(zone, x, y, padding=40):
            """Check if a position is not inside walls and not too close to edges"""
            # Check screen boundaries
            if x < 60 or x > settings.WIDTH - 100 or y < 60 or y > settings.HEIGHT - 100:
                return False

            # Check collision with walls
            test_rect = pygame.Rect(x - padding//2, y - padding//2, padding, padding)
            for wall in zone_obstacles.get(zone, []):
                if test_rect.colliderect(wall):
                    return False
            return True

        # Filter safe zones to only include positions that are actually safe
        for zone in safe_zones:
            safe_zones[zone] = [pos for pos in safe_zones[zone] if is_position_safe(zone, pos[0], pos[1])]
            # If no safe positions, add some default ones
            if not safe_zones[zone]:
                if zone == "Ground":
                    safe_zones[zone] = [(200, 550), (400, 300), (800, 500)]
                elif zone == "Tunnels":
                    safe_zones[zone] = [(300, 300), (500, 400), (700, 300)]
                else:
                    safe_zones[zone] = [(300, 300)]

        # Randomize key positions (ensure they don't overlap)
        used_positions = []

        def get_unique_position(zone, used_positions):
            """Get a position not already used and not colliding with walls"""
            if zone not in safe_zones or not safe_zones[zone]:
                # Fallback position
                return (300, 300)

            available = [p for p in safe_zones[zone] if p not in used_positions]
            if not available:
                # If all positions used, find a new one
                for _ in range(20):  # Try 20 times
                    x = random.randint(100, settings.WIDTH - 100)
                    y = random.randint(100, settings.HEIGHT - 100)
                    if is_position_safe(zone, x, y) and (x, y) not in used_positions:
                        return (x, y)
                # Fallback
                return safe_zones[zone][0]
            return random.choice(available)

        # Randomize key positions
        key_positions = {
            "jail_key": get_unique_position("Ground", used_positions)
        }
        used_positions.append(key_positions["jail_key"])

        key_positions["cave_key"] = get_unique_position("Estate", used_positions)
        used_positions.append(key_positions["cave_key"])

        key_positions["boat_key"] = get_unique_position("Tunnels", used_positions)
        used_positions.append(key_positions["boat_key"])

        # Randomize clue positions (different from keys)
        clue_positions = {
            "Ground": get_unique_position("Ground", used_positions)
        }
        used_positions.append(clue_positions["Ground"])

        clue_positions["Estate"] = get_unique_position("Estate", used_positions)
        used_positions.append(clue_positions["Estate"])

        clue_positions["Tunnels"] = get_unique_position("Tunnels", used_positions)
        used_positions.append(clue_positions["Tunnels"])

        # Randomize gun position (different from keys and clues)
        gun_position = get_unique_position("Ground", used_positions)
        used_positions.append(gun_position)

        # Randomize ammo spawns (2-4 per zone)
        ammo_positions = {}
        for zone in ["Ground", "Estate", "Tunnels"]:
            ammo_count = random.randint(2, 3)
            zone_ammo = []
            for _ in range(ammo_count):
                pos = get_unique_position(zone, used_positions)
                zone_ammo.append(pos)
                used_positions.append(pos)
            ammo_positions[zone] = zone_ammo

        # Update items dictionary with random positions
        self.items = {
            "Ground": {
                "gun": pygame.Rect(gun_position[0], gun_position[1], 24, 12),
                "ammo": [pygame.Rect(x, y, 16, 10) for x, y in ammo_positions["Ground"]],
                "clue": pygame.Rect(clue_positions["Ground"][0], clue_positions["Ground"][1], 20, 14),
                "jail_key": pygame.Rect(key_positions["jail_key"][0], key_positions["jail_key"][1], 18, 12),
            },
            "Estate": {
                "clue": pygame.Rect(clue_positions["Estate"][0], clue_positions["Estate"][1], 20, 14),
                "cave_key": pygame.Rect(key_positions["cave_key"][0], key_positions["cave_key"][1], 18, 12),
                "ammo": [pygame.Rect(x, y, 16, 10) for x, y in ammo_positions["Estate"]],
            },
            "Tunnels": {
                "clue": pygame.Rect(clue_positions["Tunnels"][0], clue_positions["Tunnels"][1], 20, 14),
                "ammo": [pygame.Rect(x, y, 16, 10) for x, y in ammo_positions["Tunnels"]],
                "boat_key": pygame.Rect(key_positions["boat_key"][0], key_positions["boat_key"][1], 18, 12),
            },
            "Harbor": {},
        }        
    def draw_star_of_david(self, x, y, size=20, color=(0, 56, 184)):
        """Draw a Star of David (Magen David) at the specified position"""
        # Calculate points for two overlapping triangles
        height = size * (3 ** 0.5) / 2  # Height of equilateral triangle

        # Upward pointing triangle
        up_points = [
            (x, y - height),  # Top
            (x - size, y + height/2),  # Bottom left
            (x + size, y + height/2),  # Bottom right
        ]

        # Downward pointing triangle
        down_points = [
            (x, y + height),  # Bottom
            (x - size, y - height/2),  # Top left
            (x + size, y - height/2),  # Top right
        ]

        # Draw triangles with transparency
        up_surf = pygame.Surface((size*3, size*3), pygame.SRCALPHA)
        down_surf = pygame.Surface((size*3, size*3), pygame.SRCALPHA)

        pygame.draw.polygon(up_surf, (*color, 180), 
                           [(p[0] - x + size, p[1] - y + size) for p in up_points])
        pygame.draw.polygon(down_surf, (*color, 180), 
                           [(p[0] - x + size, p[1] - y + size) for p in down_points])

        self.screen.blit(up_surf, (x - size, y - size))
        self.screen.blit(down_surf, (x - size, y - size))

        # Optional: Draw outline
        pygame.draw.polygon(self.screen, (0, 0, 0), up_points, 1)
        pygame.draw.polygon(self.screen, (0, 0, 0), down_points, 1)

    def validate_player_position(self):
        """Ensure player is not stuck in water or off-screen"""
        obstacles, gates, extraction = build_zone_data(self.zone)

        if self.zone == "Harbor":
            # Define walkable areas in Harbor
            ground_area = pygame.Rect(40, 300, 1120, 340)  # Main ground
            pier_area = pygame.Rect(800, 200, 300, 40)    # Pier (adjusted y)
            boat_area = pygame.Rect(1020, 210, 80, 40)    # Boat area

            # Allow player on pier and boat area (y between 200-280)
            if (pier_area.colliderect(self.player.rect) or 
                boat_area.colliderect(self.player.rect)):
                # Player is on pier or boat - that's fine
                pass
            
            # Check if player is in water (y < 200 and not on pier/boat)
            elif self.player.rect.centery < 200:
                # Teleport player back to solid ground
                self.player.rect.center = (500, 400)
                self.message = "You can't swim! Get back on land."
                self.message_time = 2.0
                self.audio.play_sound("hurt")

            # Check if player is too far left/right
            if self.player.rect.left < 40:
                self.player.rect.left = 40
            if self.player.rect.right > settings.WIDTH - 40:
                self.player.rect.right = settings.WIDTH - 40

            # Allow player on pier (y between 200-240)
            if self.player.rect.top < 200 and not pier_area.colliderect(self.player.rect):
                self.player.rect.top = 200

        # General bounds checking for all zones
        if self.player.rect.left < 40:
            self.player.rect.left = 40
        if self.player.rect.right > settings.WIDTH - 40:
            self.player.rect.right = settings.WIDTH - 40
        if self.player.rect.top < 40:
            self.player.rect.top = 40
        if self.player.rect.bottom > settings.HEIGHT - 40:
            self.player.rect.bottom = settings.HEIGHT - 40

    def reset_round(self, profile):
        self.profile = profile
        self.state = "playing"
        self.zone = "Ground"
        # Make sure player spawns on solid ground in Ground zone
        self.player = Player(100, 550, self.profile)  # Changed from 600 to 550 to be more central
        self.bullets.clear()
        self.collected = set()

        # Spawn NPCs in safe, visible positions
        self.npcs = [
            NPC(350, 300, "Estate"),
            NPC(500, 350, "Tunnels")
        ]

        self.guards = build_guards(profile)
        self.randomize_spawns()
        self.game_over = False
        self.victory = False
        self.boat_escape_active = False
        self.controls_timer = 10.0
        self.damage_flash_timer = 0.0
        self.message = f"Difficulty: {profile.name}. Escape the island!"
        self.message_time = 3.0

    def current_region_tasks(self):
        if self.zone == "Ground":
            return [("Find Ground clue", "clue_Ground" in self.collected), ("Collect Jail key", self.player.keys["jail_key"]), ("Get a weapon", self.player.has_gun)]
        if self.zone == "Estate":
            done = any(n.zone == "Estate" and (n.following or n.rescued) for n in self.npcs)
            return [("Find Estate clue", "clue_Estate" in self.collected), ("Collect Cave key", self.player.keys["cave_key"]), ("Help trapped worker", done)]
        if self.zone == "Tunnels":
            done = any(n.zone == "Tunnels" and (n.following or n.rescued) for n in self.npcs)
            return [("Find Tunnel clue", "clue_Tunnels" in self.collected), ("Collect Boat key", self.player.keys["boat_key"]), ("Guide tunnel survivor", done)]
        return [("Bring all clues", self.player.clues >= 3), ("Bring all keys", all(self.player.keys.values())), ("Rescue both survivors", self.player.rescued_npcs >= 2)]

    def region_complete(self, zone):
        return all(done for _, done in self.current_region_tasks()) if self.zone == zone else False

    def run(self):
        while self.running:
            dt = self.clock.tick(settings.FPS) / 1000.0
            self.events()
            if self.state == "playing" and not self.game_over and not self.victory:
                self.update(dt)
            self.draw()
        pygame.quit()

    def events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif self.state == "menu" and event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_difficulty = (self.selected_difficulty - 1) % len(DIFFICULTIES)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_difficulty = (self.selected_difficulty + 1) % len(DIFFICULTIES)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.reset_round(DIFFICULTIES[self.selected_difficulty])
            elif self.state == "playing":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_e:
                        self.interact()
                    elif event.key == pygame.K_TAB:
                        self.ui_collapsed = not self.ui_collapsed
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.boat_escape_active:
                    b = self.player.try_shoot(pygame.mouse.get_pos())
                    if b:
                        self.bullets.append(b)
                        self.audio.play_sound("gunshot")

    def take_damage(self, amount):
        """Handle player taking damage with visual and audio feedback"""
        self.player.health -= amount
        self.damage_flash_timer = 0.2
        self.audio.play_sound("hurt", priority=True)
        self.creepy_flicker = 0.15
        if self.player.health <= 0:
            self.game_over = True
            self.message = "You were defeated."

    def update(self, dt):
        self.audio.update(dt)
    
        obstacles, gates, extraction = build_zone_data(self.zone)
    
        # SPECIAL CASE FOR HARBOR: The pier should be walkable
        # We need to remove the pier area from obstacles if it was accidentally added
        if self.zone == "Harbor":
            # Filter out any obstacles that are part of the pier
            pier_rect = pygame.Rect(800, 150, 300, 40)
            obstacles = [o for o in obstacles if not o.colliderect(pier_rect)]
        
        self.water_anim += dt
        self.pathway_cooldown = max(0.0, self.pathway_cooldown - dt)
        self.pathway_hint_cooldown = max(0.0, self.pathway_hint_cooldown - dt)
        self.damage_flash_timer = max(0.0, self.damage_flash_timer - dt)
        
        # Validate player position
        self.validate_player_position()

        self.player.handle_input(dt, self.profile.stamina_drain, self.profile.stamina_recover)
        self.player.move_and_collide(obstacles)

        # Check for alerted guards
        any_alert = False
        for guard in list(self.guards[self.zone]):
            shot = guard.update(dt, self.player, obstacles)
            if hasattr(guard, 'alerted') and guard.alerted:
                any_alert = True
            if shot:
                self.bullets.append(shot)
            if guard.health <= 0:
                self.guards[self.zone].remove(guard)

        # Play appropriate music
        self.audio.play_music_for_zone(self.zone, any_alert)

        for npc in self.npcs:
            if npc.zone == self.zone:
                npc.update(self.player, obstacles)
                if npc.following and self.zone == "Harbor" and npc.rect.centerx > 1010 and not npc.rescued:
                    npc.rescued = True
                    self.player.rescued_npcs += 1
                    self.audio.play_sound("item_pickup")

        for bullet in list(self.bullets):
            bullet.update(obstacles)
            if not bullet.alive:
                self.bullets.remove(bullet)
                continue
            if bullet.owner == "guard" and self.player.rect.collidepoint(bullet.pos):
                self.take_damage(self.profile.guard_damage)
                bullet.alive = False
            elif bullet.owner == "player":
                for g in self.guards[self.zone]:
                    if g.rect.collidepoint(bullet.pos):
                        g.health -= self.profile.player_damage
                        bullet.alive = False
                        break
            if not bullet.alive and bullet in self.bullets:
                self.bullets.remove(bullet)

        # In the gate collision section of update():
        for gate in gates:
            if self.pathway_cooldown > 0:
                break
            if self.player.rect.colliderect(gate.rect):
                if gate.required_key and not self.player.keys.get(gate.required_key, False):
                    if self.pathway_hint_cooldown <= 0:
                        self.message = f"Pathway locked: requires {gate.required_key.replace('_', ' ')}"
                        self.pathway_hint_cooldown = 1.0
                    continue
                
                current_idx = self.region_order.index(self.zone)
                target_idx = self.region_order.index(gate.target_zone)
                
                if target_idx > current_idx and not self.region_complete(self.zone):
                    if self.pathway_hint_cooldown <= 0:
                        self.message = "Complete this region's tasks first."
                        self.pathway_hint_cooldown = 1.0
                    continue
                
                # TRANSFER FOLLOWERS FIRST!
                self.transfer_followers(gate.target_zone)
                
                # Then move the player
                self.zone = gate.target_zone
                self.player.rect.topleft = gate.spawn
                
                # Extra validation for Harbor spawn
                if self.zone == "Harbor":
                    # Ensure player spawns on solid ground (y between 300-600)
                    if self.player.rect.centery < 300:
                        self.player.rect.centery = 400
                
                self.pathway_cooldown = 0.7
                self.audio.play_sound("door")
                self.message = f"Entered {self.zone}"
                break

        if extraction and self.player.rect.colliderect(extraction):
            if self.player.clues >= 3 and all(self.player.keys.values()) and self.player.rescued_npcs >= 2:
                self.victory = True
                self.audio.play_sound("victory", priority=True)
            else:
                self.message = "Not ready: need all clues, keys, and rescued survivors."

        self.message_time = max(0.0, self.message_time - dt)

    def transfer_followers(self, new_zone: str):
        """Transfer all following NPCs to the new zone and position them near the player"""
        followers_transferred = 0
        for npc in self.npcs:
            # Check if NPC is following and not rescued, and is in the current zone
            if npc.following and not npc.rescued and npc.zone == self.zone:
                # Change their zone
                npc.zone = new_zone
                
                # Position them near the player with some spacing
                offset_x = -40 - (followers_transferred * 20)
                offset_y = 20
                
                # Make sure they're not placed inside walls (simple check)
                npc.rect.center = (
                    self.player.rect.centerx + offset_x,
                    self.player.rect.centery + offset_y
                )
                
                followers_transferred += 1
                print(f"Transferred follower to {new_zone}")  # Debug line
        
        if followers_transferred > 0:
            self.message = f"{followers_transferred} survivor(s) followed you through the portal"
            self.message_time = 2.0

    def interact(self):
        items = self.items.get(self.zone, {})
        p = self.player.rect
        collected_anything = False
        
        if "gun" in items and p.colliderect(items["gun"]) and "gun" not in self.collected:
            self.collected.add("gun")
            self.player.has_gun = True
            self.player.ammo += 20
            collected_anything = True
            self.message = "You found a pistol with 20 ammo."
            
        for idx, box in enumerate(items.get("ammo", [])):
            key = f"ammo_{self.zone}_{idx}"
            if p.colliderect(box) and key not in self.collected:
                self.collected.add(key)
                self.player.ammo += 12
                collected_anything = True
                self.message = "Picked up ammo (+12)."
                
        if "clue" in items:
            key = f"clue_{self.zone}"
            if p.colliderect(items["clue"]) and key not in self.collected:
                self.collected.add(key)
                self.player.clues += 1
                collected_anything = True
                self.message = f"Clue found ({self.player.clues}/3)."
                
        for k in ["jail_key", "cave_key", "boat_key"]:
            if k in items and p.colliderect(items[k]) and not self.player.keys[k]:
                self.player.keys[k] = True
                collected_anything = True
                self.message = f"Collected {k.replace('_', ' ')}."
                
        for npc in self.npcs:
            if npc.zone == self.zone and not npc.following and not npc.rescued and p.colliderect(npc.rect.inflate(24, 24)):
                npc.following = True
                collected_anything = True
                self.message = "Survivor is now following you."
        
        if collected_anything:
            self.audio.play_sound("item_pickup")
            self.message_time = 2.0

    def draw_wall_with_texture(self, rect, base_color, texture_color=None, pattern="brick"):
        """Draw walls with better visual appearance"""
        if texture_color is None:
            texture_color = (min(base_color[0] + 30, 255), 
                            min(base_color[1] + 30, 255), 
                            min(base_color[2] + 30, 255))
        
        # Draw base wall
        pygame.draw.rect(self.screen, base_color, rect, border_radius=3)
        
        # Add texture pattern
        if pattern == "brick":
            # Draw brick pattern (horizontal lines)
            for y in range(rect.top + 5, rect.bottom, 8):
                pygame.draw.line(self.screen, texture_color, 
                               (rect.left + 2, y), (rect.right - 2, y), 1)
            # Vertical mortar lines
            for x in range(rect.left + 4, rect.right, 20):
                pygame.draw.line(self.screen, texture_color, 
                               (x, rect.top + 2), (x, rect.bottom - 2), 1)
        
        elif pattern == "stone":
            # Draw stone pattern (random circles)
            for _ in range(rect.width * rect.height // 500):
                x = random.randint(rect.left + 5, rect.right - 5)
                y = random.randint(rect.top + 5, rect.bottom - 5)
                pygame.draw.circle(self.screen, texture_color, (x, y), 3)
        
        elif pattern == "wood":
            # Draw wood grain (vertical lines)
            for x in range(rect.left + 2, rect.right, 6):
                pygame.draw.line(self.screen, texture_color, 
                               (x, rect.top + 2), (x, rect.bottom - 2), 1)
        
        # Add highlight/shadow for 3D effect
        pygame.draw.line(self.screen, (255, 255, 255, 30), 
                        (rect.left, rect.top), (rect.right, rect.top), 1)
        pygame.draw.line(self.screen, (0, 0, 0, 30), 
                        (rect.left, rect.bottom), (rect.right, rect.bottom), 1)

    def draw_zone_background(self):
        if self.zone == "Ground":
            self.screen.fill((35, 112, 62))
            for tx, ty in self.decor["Ground"]["trees"]:
                if hasattr(self, 'tree_sprite') and self.tree_sprite:
                    # Draw sprite
                    tree_rect = self.tree_sprite.get_rect(center=(tx, ty))
                    self.screen.blit(self.tree_sprite, tree_rect)
                else:
                    # Fallback drawing
                    pygame.draw.circle(self.screen, (50, 88, 50), (tx, ty + 8), 19)
                    pygame.draw.circle(self.screen, (48, 138, 76), (tx, ty), 30)
                    pygame.draw.rect(self.screen, (92, 62, 40), (tx - 6, ty + 24, 12, 22))
            for bx, by in self.decor["Ground"]["bushes"]:
                pygame.draw.circle(self.screen, (40, 132, 62), (bx, by), 17)
                pygame.draw.circle(self.screen, (60, 162, 90), (bx + 10, by + 2), 13)

        elif self.zone == "Estate":
            self.screen.fill((62, 88, 72))
            for h in self.decor["Estate"]["hedges"]:
                pygame.draw.rect(self.screen, (38, 118, 64), h, border_radius=8)
            for f in self.decor["Estate"]["fountains"]:
                pygame.draw.ellipse(self.screen, (70, 110, 130), f)
                pygame.draw.ellipse(self.screen, (120, 180, 210), f.inflate(-24, -24))

        elif self.zone == "Tunnels":
            self.screen.fill((54, 52, 68))
            for c in self.decor["Tunnels"]["crystals"]:
                pygame.draw.polygon(self.screen, (120, 220, 255), [(c.centerx, c.y), (c.right, c.bottom - 4), (c.x, c.bottom - 4)])
            wave = int((1 + math.sin(self.water_anim * 2.7)) * 12)
            for pool in self.decor["Tunnels"]["pools"]:
                pygame.draw.ellipse(self.screen, (34, 82 + wave, 130 + wave // 2), pool)
            # creepy glowing eyes in tunnels
            for eyes in [(170, 470), (580, 640), (1010, 510)]:
                pygame.draw.circle(self.screen, (220, 40, 40), eyes, 3)
                pygame.draw.circle(self.screen, (220, 40, 40), (eyes[0] + 11, eyes[1]), 3)

        elif self.zone == "Harbor":
            # Water at the TOP
            water_rect = pygame.Rect(0, 0, settings.WIDTH, 250)
            wave = int((1 + math.sin(self.water_anim * 3.0)) * 15)

            # Water gradient
            for i in range(water_rect.height):
                y = i
                color_value = 100 + int(i * 0.3) + wave//2
                pygame.draw.line(self.screen, (0, color_value, 180), 
                                (0, y), (settings.WIDTH, y))

            # Water surface highlights
            for i in range(5):
                highlight_y = 50 + i * 40 + wave//2
                pygame.draw.line(self.screen, (200, 240, 255), 
                                (0, highlight_y), (settings.WIDTH, highlight_y), 2)

            # Sand/beach transition - this is a VISUAL boundary, not physical
            beach_rect = pygame.Rect(0, 230, settings.WIDTH, 70)
            for i in range(beach_rect.height):
                y = 230 + i
                sand_color = 200 - i // 2
                pygame.draw.line(self.screen, (sand_color, sand_color - 30, 150), 
                                (0, y), (settings.WIDTH, y))

            # Draw a clear boundary line between sand and ground
            pygame.draw.line(self.screen, (139, 69, 19), (40, 300), (settings.WIDTH-40, 300), 3)

            # Ground area (bottom portion) - WALKABLE AREA
            ground_rect = pygame.Rect(40, 300, 1120, 340)

            # Draw base ground with solid color
            pygame.draw.rect(self.screen, (160, 140, 100), ground_rect)

            # Draw tile pattern on ground (visual only)
            tile_size = 40
            for x in range(ground_rect.left + 20, ground_rect.right - 20, tile_size):
                for y in range(ground_rect.top + 20, ground_rect.bottom - 20, tile_size):
                    # Light tile border
                    pygame.draw.rect(self.screen, (120, 100, 70), 
                                   (x - 2, y - 2, tile_size + 4, tile_size + 4), 1)

                    # Lighter tile color
                    variation = random.randint(-20, 20)
                    tile_color = (180 + variation, 160 + variation, 120 + variation)
                    pygame.draw.rect(self.screen, tile_color, 
                                   (x, y, tile_size - 4, tile_size - 4))

            # Star of David pattern on ground (visual only)
            star_positions = [
                (300, 450), (500, 350), (700, 550), (900, 400), (1100, 500),
                (200, 600), (400, 550), (600, 450), (800, 350), (1000, 600)
            ]
            for sx, sy in star_positions:
                self.draw_star_of_david(sx, sy, size=15, color=(0, 56, 184))

            # Pier - make it longer and more accessible
            pier_rect = pygame.Rect(800, 200, 300, 40)  # Moved down from y=150 to y=200
            pier_surf = pygame.Surface((300, 40), pygame.SRCALPHA)
            pier_surf.fill((139, 90, 43, 200))
            self.screen.blit(pier_surf, (800, 200))

            # Draw pier planks
            for i in range(0, 300, 30):
                pygame.draw.line(self.screen, (101, 67, 33), 
                                (800 + i, 200), (800 + i, 240), 2)

            # Pier pilings (obstacles) - already defined in obstacles
            stair_x = 780
            for i in range(5):
                stair_rect = pygame.Rect(stair_x - i*5, 260 + i*8, 40, 8)
                pygame.draw.rect(self.screen, (101, 67, 33), stair_rect)
                pygame.draw.rect(self.screen, (70, 40, 20), stair_rect, 1)
            # Boat (extraction point) - at end of pier but lower
            boat_rect = pygame.Rect(1020, 210, 80, 40)  # Moved down to match pier
            pygame.draw.ellipse(self.screen, (101, 67, 33), boat_rect)
            pygame.draw.ellipse(self.screen, (70, 40, 20), boat_rect, 2)

            # Boat cabin
            cabin_surf = pygame.Surface((50, 25), pygame.SRCALPHA)
            cabin_surf.fill((80, 80, 120, 200))
            self.screen.blit(cabin_surf, (1035, 190))  # Adjusted y position

            # Add a small dock/ramp from ground to pier
            ramp_rect = pygame.Rect(780, 240, 40, 60)
            pygame.draw.polygon(self.screen, (101, 67, 33), 
                               [(780, 300), (820, 240), (860, 240), (820, 300)])

            # Buildings (obstacles) - drawn with transparency so player can see themselves
            # Warehouse 1
            warehouse1_surf = pygame.Surface((150, 80), pygame.SRCALPHA)
            warehouse1_surf.fill((120, 100, 80, 180))
            self.screen.blit(warehouse1_surf, (200, 400))
            pygame.draw.rect(self.screen, (80, 60, 40), (200, 400, 150, 80), 3)

            # Warehouse 2
            warehouse2_surf = pygame.Surface((120, 60), pygame.SRCALPHA)
            warehouse2_surf.fill((130, 110, 90, 180))
            self.screen.blit(warehouse2_surf, (500, 450))
            pygame.draw.rect(self.screen, (90, 70, 50), (500, 450, 120, 60), 3)

            # Harbor office
            office_surf = pygame.Surface((150, 70), pygame.SRCALPHA)
            office_surf.fill((150, 130, 100, 180))
            self.screen.blit(office_surf, (900, 400))
            pygame.draw.rect(self.screen, (100, 80, 60), (900, 400, 150, 70), 3)

            # Crates (obstacles)
            for cx, cy in [(300, 550), (600, 350)]:
                crate_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
                crate_surf.fill((160, 120, 80, 200))
                self.screen.blit(crate_surf, (cx, cy))
                pygame.draw.rect(self.screen, (100, 70, 40), (cx, cy, 40, 40), 2)

            # Barrels (obstacles)
            for bx, by in [(400, 500), (700, 500)]:
                barrel_surf = pygame.Surface((30, 30), pygame.SRCALPHA)
                pygame.draw.ellipse(barrel_surf, (110, 70, 40, 200), (0, 0, 30, 30))
                self.screen.blit(barrel_surf, (bx, by))
                pygame.draw.ellipse(self.screen, (80, 50, 30), (bx, by, 30, 30), 2)

            # Boat (extraction point)
            boat_rect = pygame.Rect(1020, 150, 80, 40)
            pygame.draw.ellipse(self.screen, (101, 67, 33), boat_rect)
            pygame.draw.ellipse(self.screen, (70, 40, 20), boat_rect, 2)

            # Boat cabin
            cabin_surf = pygame.Surface((50, 25), pygame.SRCALPHA)
            cabin_surf.fill((80, 80, 120, 200))
            self.screen.blit(cabin_surf, (1035, 130))

            # Portal at bottom
            portal_rect = pygame.Rect(1080, 620, 60, 60)
            pygame.draw.rect(self.screen, (100, 50, 150), portal_rect, border_radius=30)
            pygame.draw.rect(self.screen, (200, 100, 255), portal_rect, 3, border_radius=30)
            portal_text = self.small_font.render("TUNNELS", True, (255, 255, 255))
            self.screen.blit(portal_text, (portal_rect.x - 10, portal_rect.y - 20))


    def draw_item_symbols(self, items: Dict[str, object]):
        def marker(rect: pygame.Rect, text: str, col=(245,245,245)):
            pygame.draw.circle(self.screen, (20,20,20), (rect.centerx, rect.y - 10), 9)
            self.screen.blit(self.small_font.render(text, True, col), (rect.centerx - 5, rect.y - 18))  
        if "gun" in items and "gun" not in self.collected:
            marker(items["gun"], "G")
        if "clue" in items and f"clue_{self.zone}" not in self.collected:
            marker(items["clue"], "C")
        for idx, box in enumerate(items.get("ammo", [])):
            if f"ammo_{self.zone}_{idx}" not in self.collected:
                marker(box, "A", (255, 220, 90))
        key_map = {"jail_key": "K1", "cave_key": "K2", "boat_key": "K3"}
        for k, sym in key_map.items():
            if k in items and not self.player.keys[k]:
                marker(items[k], sym, (255, 215, 90))

    def draw_creepy_overlay(self):
        darkness = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        darkness.fill((0, 0, 0, 48 if self.zone != "Tunnels" else 78))
        if self.creepy_flicker > 0:
            darkness.fill((120, 0, 0, 60), special_flags=pygame.BLEND_RGBA_ADD)
        self.screen.blit(darkness, (0, 0))

    def draw_damage_flash(self):
        """Draw red overlay when taking damage"""
        if self.damage_flash_timer > 0:
            # Create semi-transparent red overlay
            flash = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
            alpha = int(150 * self.damage_flash_timer * 5)  # Fade out
            flash.fill((255, 0, 0, min(alpha, 200)))
            self.screen.blit(flash, (0, 0))

    def draw_hud(self):
        """Draw HUD with toggle support"""
        if self.ui_collapsed:
            # Draw only minimal info when collapsed
            mini_panel = pygame.Rect(10, 10, 200, 40)
            pygame.draw.rect(self.screen, (10, 10, 13), mini_panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 54), mini_panel, 2, border_radius=8)
            
            # Show only health and zone
            health_text = self.small_font.render(f"❤️ {int(self.player.health)}", True, (255, 100, 100))
            zone_text = self.small_font.render(f"📍 {self.zone}", True, (100, 255, 100))
            
            self.screen.blit(health_text, (20, 18))
            self.screen.blit(zone_text, (100, 18))
            
            # Tab hint
            hint = self.small_font.render("TAB ↑", True, (150, 150, 150))
            self.screen.blit(hint, (20, 45))
        else:
            # Draw full HUD
            panel = pygame.Rect(10, 10, 430, 180)
            pygame.draw.rect(self.screen, (10, 10, 13), panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 54), panel, 2, border_radius=8)
            
            # Zone and difficulty
            self.screen.blit(self.font.render(f"Zone: {self.zone} ({self.profile.name})", 
                             True, (240, 240, 240)), (20, 18))
            
            # Health bar
            health_pct = self.player.health / self.profile.player_health
            health_bar = pygame.Rect(20, 45, 200, 15)
            pygame.draw.rect(self.screen, (60, 60, 60), health_bar)
            pygame.draw.rect(self.screen, (255, 0, 0), 
                            (20, 45, int(200 * health_pct), 15))
            self.screen.blit(self.small_font.render(f"Health: {int(self.player.health)}", 
                             True, (255, 255, 255)), (230, 43))
            
            # Stamina bar
            stamina_pct = self.player.stamina / 100
            stamina_bar = pygame.Rect(20, 65, 200, 10)
            pygame.draw.rect(self.screen, (60, 60, 60), stamina_bar)
            pygame.draw.rect(self.screen, (0, 255, 255), 
                            (20, 65, int(200 * stamina_pct), 10))
            
            # Ammo
            ammo_color = (255, 255, 0) if self.player.ammo > 0 else (100, 100, 100)
            self.screen.blit(self.small_font.render(f"Ammo: {self.player.ammo}", 
                             True, ammo_color), (20, 85))
            
            # Keys collected
            keys_text = "Keys: "
            for key, obtained in self.player.keys.items():
                keys_text += "✓" if obtained else "○"
            self.screen.blit(self.small_font.render(keys_text, True, (255, 215, 0)), (20, 105))
            
            # Progress
            self.screen.blit(self.small_font.render(f"Clues: {self.player.clues}/3 | Rescued: {self.player.rescued_npcs}/2", 
                             True, (220, 220, 220)), (20, 125))
            
            # Tasks panel (right side)
            tasks_panel = pygame.Rect(settings.WIDTH - 420, 10, 410, 170)
            pygame.draw.rect(self.screen, (10, 10, 13), tasks_panel, border_radius=8)
            pygame.draw.rect(self.screen, (50, 50, 54), tasks_panel, 2, border_radius=8)
            
            self.screen.blit(self.font.render("Current Tasks", True, (255, 255, 255)), 
                            (settings.WIDTH - 410, 18))
            
            for i, (task, done) in enumerate(self.current_region_tasks()):
                color = (100, 255, 100) if done else (255, 255, 255)
                mark = "✓" if done else "○"
                self.screen.blit(self.small_font.render(f"{mark} {task}", True, color), 
                               (settings.WIDTH - 410, 45 + i * 25))
            
            # Tab hint
            hint = self.small_font.render("TAB ↓ to collapse", True, (150, 150, 150))
            self.screen.blit(hint, (settings.WIDTH - 200, 190))

    def draw_menu(self):
        gradient_fill(self.screen, (8, 12, 20), (24, 40, 60))
        title = self.large_font.render("Escape the Secret Island", True, (240, 240, 245))
        self.screen.blit(title, (settings.WIDTH // 2 - title.get_width() // 2, 60))
        for i, d in enumerate(DIFFICULTIES):
            selected = i == self.selected_difficulty
            panel = pygame.Rect(settings.WIDTH // 2 - 260, 190 + i * 120, 520, 98)
            pygame.draw.rect(self.screen, (34, 44, 66) if selected else (22, 28, 40), panel, border_radius=12)
            pygame.draw.rect(self.screen, (120, 150, 220) if selected else (60, 70, 90), panel, 2, border_radius=12)
            txt = self.font.render(f"{i + 1}. {d.name}", True, (240, 240, 240))
            detail = self.small_font.render(f"HP {d.player_health} | Guard Speed {d.guard_speed:.2f} | Extra Guards {d.extra_guards}", True, (215, 225, 240))
            self.screen.blit(txt, (panel.x + 16, panel.y + 14))
            self.screen.blit(detail, (panel.x + 16, panel.y + 50))

        hint = self.small_font.render("W/S or ↑/↓ to choose · Enter to start", True, (190, 205, 220))
        self.screen.blit(hint, (settings.WIDTH // 2 - hint.get_width() // 2, settings.HEIGHT - 58))

    def draw(self):
        if self.state == "menu":
            self.audio.play_music_for_zone("menu", False)
            self.draw_menu()
            pygame.display.flip()
            return

        obstacles, gates, extraction = build_zone_data(self.zone)

        # LAYER 1: Draw background (sky, ground, water)
        self.draw_zone_background()

        # LAYER 2: Draw walls and gates (but not for Harbor - we handle separately)
        if self.zone != "Harbor":
            for wall in obstacles:
                # Choose texture based on zone
                if self.zone == "Ground":
                    self.draw_wall_with_texture(wall, (40, 35, 30), pattern="stone")
                elif self.zone == "Estate":
                    self.draw_wall_with_texture(wall, (70, 60, 50), pattern="brick")
                elif self.zone == "Tunnels":
                    self.draw_wall_with_texture(wall, (30, 30, 40), pattern="stone")
                elif self.zone == "Harbor":
                    # Harbor walls are drawn in background
                    pass
                
        # LAYER 3: Draw items (they should be on top of walls but under characters)
        items = self.items.get(self.zone, {})
        if "gun" in items and "gun" not in self.collected:
            pygame.draw.rect(self.screen, (40, 40, 40), items["gun"])
        for idx, box in enumerate(items.get("ammo", [])):
            if f"ammo_{self.zone}_{idx}" not in self.collected:
                pygame.draw.rect(self.screen, (240, 220, 70), box)
        if "clue" in items and f"clue_{self.zone}" not in self.collected:
            pygame.draw.rect(self.screen, (230, 230, 245), items["clue"])
        for k in ["jail_key", "cave_key", "boat_key"]:
            if k in items and not self.player.keys[k]:
                pygame.draw.rect(self.screen, (245, 200, 70), items[k])

        # Draw item symbols
        self.draw_item_symbols(items)

        # LAYER 4: Draw characters (player, NPCs, guards)
        for npc in self.npcs:
            if npc.zone == self.zone and not npc.rescued:
                npc.draw(self.screen)

        for guard in self.guards[self.zone]:
            guard.draw(self.screen)

        # Draw player - IMPORTANT: Make sure player is drawn!
        self.player.draw(self.screen)

        # LAYER 5: Draw bullets and effects
        for bullet in self.bullets:
            bullet.draw(self.screen)

        # LAYER 6: Draw gates (on top of characters but under UI)
        for gate in gates:
            # Check if gate is locked
            is_locked = gate.required_key and not self.player.keys.get(gate.required_key, False)

            # Choose color based on lock status
            if is_locked:
                color = (204, 120, 82)  # Reddish for locked
                border_color = (255, 0, 0)
            else:
                color = (80, 210, 100)  # Green for unlocked
                border_color = (0, 255, 0)

            # Draw gate with glow effect
            if gate.required_key == "boat_key" and not is_locked:
                # Make final gate extra shiny
                glow = pulsing(self.water_anim, 3.0, 30)
                color = (100 + glow, 230, 100 + glow)

            # Draw gate
            pygame.draw.rect(self.screen, color, gate.rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, gate.rect, 3, border_radius=8)

            # Draw gate symbol
            gate_symbol = "→"
            if gate.required_key:
                gate_symbol = "🔒" if is_locked else "🔑"

            symbol_surf = self.font.render(gate_symbol, True, (255, 255, 255))
            symbol_rect = symbol_surf.get_rect(center=gate.rect.center)
            self.screen.blit(symbol_surf, symbol_rect)

        # LAYER 7: Draw extraction point (boat)
        if extraction:
            # Only draw if not in Harbor (Harbor draws its own boat in background)
            if self.zone != "Harbor":
                glow = pulsing(self.water_anim, 4.2, 26)
                pygame.draw.rect(self.screen, (220, 200 + glow // 4, 120), extraction, border_radius=4)

        # LAYER 8: Draw overlays
        self.draw_creepy_overlay()
        self.draw_damage_flash()

        # LAYER 9: Draw HUD (always on top)
        self.draw_hud()

        # Draw messages
        if self.message_time > 0:
            info = self.font.render(self.message, True, (255, 245, 170))
            bg = pygame.Rect(settings.WIDTH // 2 - info.get_width() // 2 - 12, 
                           settings.HEIGHT - 58, info.get_width() + 24, 40)
            pygame.draw.rect(self.screen, (10, 10, 10), bg, border_radius=6)
            pygame.draw.rect(self.screen, (90, 90, 90), bg, 2, border_radius=6)
            self.screen.blit(info, (bg.x + 12, bg.y + 9))

        # Draw victory/game over
        if self.victory:
            text = self.large_font.render("VICTORY! You escaped!", True, (255, 230, 110))
            self.screen.blit(text, (settings.WIDTH // 2 - text.get_width() // 2, settings.HEIGHT // 2 - 20))
        elif self.game_over:
            text = self.large_font.render("GAME OVER", True, (255, 90, 90))
            self.screen.blit(text, (settings.WIDTH // 2 - text.get_width() // 2, settings.HEIGHT // 2 - 20))

        pygame.display.flip()
if __name__ == "__main__":
    game = Game()
    game.run()