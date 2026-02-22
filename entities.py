import random
from typing import List, Optional, Tuple

import pygame

from models import DifficultyProfile
from settings import BULLET_SPEED, HEIGHT, MAX_STAMINA, PLAYER_SPEED, SPRINT_MULTIPLIER, Vec, WIDTH


class Bullet:
    def __init__(self, pos: Vec, direction: Vec, owner: str):
        self.pos = Vec(pos)
        self.dir = direction.normalize() if direction.length_squared() else Vec(1, 0)
        self.owner = owner
        self.radius = 4 if owner == "player" else 5
        self.alive = True

    def update(self, obstacles: List[pygame.Rect]):
        self.pos += self.dir * BULLET_SPEED
        if self.pos.x < 0 or self.pos.x > WIDTH or self.pos.y < 0 or self.pos.y > HEIGHT:
            self.alive = False
            return
        hitbox = pygame.Rect(self.pos.x - self.radius, self.pos.y - self.radius, self.radius * 2, self.radius * 2)
        for wall in obstacles:
            if wall.colliderect(hitbox):
                self.alive = False
                return

    def draw(self, screen: pygame.Surface):
        pygame.draw.circle(screen, (255, 220, 95) if self.owner == "player" else (255, 90, 90), (int(self.pos.x), int(self.pos.y)), self.radius)


class Character:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.rect = pygame.Rect(x, y, w, h)
        self.vel = Vec(0, 0)
        self.look_dir = Vec(1, 0)
        self.muzzle_timer = 0.0

    def move_and_collide(self, obstacles: List[pygame.Rect]):
        self.rect.x += int(self.vel.x)
        for wall in obstacles:
            if self.rect.colliderect(wall):
                if self.vel.x > 0:
                    self.rect.right = wall.left
                elif self.vel.x < 0:
                    self.rect.left = wall.right

        self.rect.y += int(self.vel.y)
        for wall in obstacles:
            if self.rect.colliderect(wall):
                if self.vel.y > 0:
                    self.rect.bottom = wall.top
                elif self.vel.y < 0:
                    self.rect.top = wall.bottom


class Player(Character):
    def __init__(self, x: int, y: int, profile: DifficultyProfile):
        super().__init__(x, y, 22, 32)
        self.health = profile.player_health
        self.stamina = MAX_STAMINA
        self.has_gun = False
        self.ammo = 0
        self.keys = {"jail_key": False, "cave_key": False, "boat_key": False}
        self.clues = 0
        self.rescued_npcs = 0
        self.fire_cooldown = 0.0

    def handle_input(self, dt: float, stamina_drain: float, stamina_recover: float):
        keys = pygame.key.get_pressed()
        direction = Vec(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1

        sprinting = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and self.stamina > 0 and direction.length_squared() > 0
        speed = PLAYER_SPEED * (SPRINT_MULTIPLIER if sprinting else 1)
        if sprinting:
            self.stamina = max(0.0, self.stamina - stamina_drain * dt)
        else:
            self.stamina = min(MAX_STAMINA, self.stamina + stamina_recover * dt)

        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.look_dir = Vec(direction)
        self.vel = direction * speed

        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.muzzle_timer = max(0.0, self.muzzle_timer - dt)

    def try_shoot(self, target_pos: Tuple[int, int]) -> Optional[Bullet]:
        if not self.has_gun or self.ammo <= 0 or self.fire_cooldown > 0:
            return None
        self.ammo -= 1
        self.fire_cooldown = 0.18
        origin = Vec(self.rect.center)
        direction = Vec(target_pos) - origin
        if direction.length_squared() > 0:
            self.look_dir = direction.normalize()
        self.muzzle_timer = 0.05
        return Bullet(origin, direction, "player")

    def draw(self, screen: pygame.Surface):
        body = self.rect
        pygame.draw.rect(screen, (55, 145, 232), body, border_radius=4)
        pygame.draw.circle(screen, (241, 208, 170), (body.centerx, body.top - 8), 7)
        pygame.draw.line(screen, (20, 20, 20), (body.centerx - 5, body.bottom), (body.centerx - 5, body.bottom + 10), 3)
        pygame.draw.line(screen, (20, 20, 20), (body.centerx + 5, body.bottom), (body.centerx + 5, body.bottom + 10), 3)
        if self.has_gun:
            gun_rect = pygame.Rect(body.right + 4, body.top + 12, 10, 3)
            pygame.draw.rect(screen, (50, 50, 50), gun_rect)
            if self.muzzle_timer > 0:
                self._draw_muzzle_flash(screen, Vec(gun_rect.right, gun_rect.centery), self.look_dir)

    def _draw_muzzle_flash(self, screen: pygame.Surface, origin: Vec, direction: Vec):
        d = direction.normalize() if direction.length_squared() else Vec(1, 0)
        perp = Vec(-d.y, d.x)
        tip = origin + d * 14
        p2 = origin + perp * 4
        p3 = origin - perp * 4
        pygame.draw.polygon(screen, (255, 240, 130), [tip, p2, p3])


class Guard(Character):
    def __init__(self, x: int, y: int, patrol_points: List[Tuple[int, int]], profile: DifficultyProfile):
        x = max(50, min(WIDTH - 70, x))
        y = max(50, min(HEIGHT - 70, y))
        super().__init__(x, y, 22, 32)
        self.patrol_points = [Vec(p) for p in patrol_points]
        self.current_patrol = 0
        self.health = profile.guard_health
        self.profile = profile
        self.shoot_timer = random.uniform(0.2, 0.8)
        self.alerted = False

    def update(self, dt: float, player: Player, obstacles: List[pygame.Rect]) -> Optional[Bullet]:
        to_player = Vec(player.rect.center) - Vec(self.rect.center)
        dist = to_player.length()
        can_see = dist <= self.profile.guard_sight and self._line_of_sight(player.rect.center, obstacles)
        self.alerted = can_see

        if can_see:
            self.look_dir = to_player.normalize() if dist > 0 else self.look_dir
            self.vel = self.look_dir * self.profile.guard_speed if dist > 75 else Vec(0, 0)
        else:
            target = self.patrol_points[self.current_patrol]
            path = target - Vec(self.rect.center)
            if path.length() < 10:
                self.current_patrol = (self.current_patrol + 1) % len(self.patrol_points)
                path = self.patrol_points[self.current_patrol] - Vec(self.rect.center)
            self.vel = path.normalize() * self.profile.guard_speed if path.length_squared() > 0 else Vec(0, 0)
            if path.length_squared() > 0:
                self.look_dir = path.normalize()

        self.move_and_collide(obstacles)
        self.shoot_timer -= dt
        self.muzzle_timer = max(0.0, self.muzzle_timer - dt)
        if can_see and self.shoot_timer <= 0:
            self.shoot_timer = self.profile.guard_shoot_cooldown
            self.muzzle_timer = 0.05
            return Bullet(Vec(self.rect.center), to_player, "guard")
        return None

    def _line_of_sight(self, target: Tuple[int, int], obstacles: List[pygame.Rect]) -> bool:
        x1, y1 = self.rect.center
        x2, y2 = target
        for i in range(1, 26):
            t = i / 26
            probe = pygame.Rect(x1 + (x2 - x1) * t - 2, y1 + (y2 - y1) * t - 2, 4, 4)
            if any(w.colliderect(probe) for w in obstacles):
                return False
        return True

    def draw(self, screen: pygame.Surface):
        body = self.rect
        pygame.draw.rect(screen, (175, 72, 72), body, border_radius=4)
        pygame.draw.circle(screen, (235, 202, 168), (body.centerx, body.top - 8), 7)
        pygame.draw.rect(screen, (40, 40, 40), pygame.Rect(body.right + 4, body.top + 12, 10, 3))


# In entities.py, ensure the NPC class has this update method:
class NPC(Character):
    def __init__(self, x: int, y: int, zone: str):
        super().__init__(x, y, 20, 30)
        self.zone = zone
        self.following = False
        self.rescued = False

    def update(self, player: Player, obstacles: List[pygame.Rect]):
        if self.rescued:
            return
        if self.following:
            # Calculate distance to player
            to_player = Vec(player.rect.center) - Vec(self.rect.center)
            distance = to_player.length()
            
            # Only move if too far from player
            if distance > 50:
                # Move towards player
                if distance > 0:
                    self.vel = to_player.normalize() * 2.2
                else:
                    self.vel = Vec(0, 0)
            elif distance < 30:
                # Move away a bit if too close
                if distance > 0:
                    self.vel = -to_player.normalize() * 1.0
                else:
                    self.vel = Vec(0, 0)
            else:
                self.vel = Vec(0, 0)
            
            self.move_and_collide(obstacles)
    
    def draw(self, screen: pygame.Surface):
        # Draw with different color if following
        color = (92, 188, 108) if not self.following else (165, 242, 187)
        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.circle(screen, (235, 202, 168), (self.rect.centerx, self.rect.top - 7), 6)