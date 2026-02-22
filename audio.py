import pygame
import math
import os
import random
from array import array
from typing import Dict, Optional

class AudioManager:
    """Enhanced audio manager with zone music, volume ducking, and priority sounds"""
    
    def __init__(self):
        self.enabled = False
        self.current_music = None
        self.current_zone = None
        self.in_combat = False
        
        # Volume settings
        self.music_volume = 0.4
        self.sfx_volume = 0.5
        self.priority_volume = 0.8  # For damage sounds
        self.ducked_volume = 0.15    # Music volume when shooting
        
        # Volume ducking for gunshots
        self.volume_duck_timer = 0
        self.duck_duration = 0.3     # How long music stays quiet after shot
        
        # Track if sounds are loaded from files or generated
        self.using_file_sounds = False
        
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2)
            self.enabled = True
            
            # Try to load external sound files first
            self._load_sound_files()
            
            # If files don't exist, generate procedural sounds
            if not self.using_file_sounds:
                self._generate_procedural_sounds()
                
        except pygame.error as e:
            print(f"Audio system error: {e}")
            self.enabled = False
    
    def _load_sound_files(self):
        """Load sound effects from files if they exist"""
        self.sounds = {}
        sound_files = {
            "gunshot": "gunshot.wav",
            "footstep": "footstep.wav", 
            "item_pickup": "pickup.wav",
            "door": "door.wav",
            "hurt": "hurt.wav",
            "guard_alert": "alert.wav",
        }
        
        # Music files (if they exist as MP3s)
        self.music_tracks = {}
        music_files = {
            "menu": "menu_theme.mp3",
            "Ground": "ground_theme.mp3",
            "Estate": "estate_theme.mp3",
            "Tunnels": "tunnels_theme.mp3",
            "Harbor": "harbor_theme.mp3",
            "combat": "combat_theme.mp3",
            "victory": "victory_fanfare.mp3"
        }
        
        loaded_any = False
        for name, filename in sound_files.items():
            if os.path.exists(filename):
                try:
                    self.sounds[name] = pygame.mixer.Sound(filename)
                    loaded_any = True
                    print(f"Loaded {filename}")
                except:
                    print(f"Could not load {filename}")
        
        self.using_file_sounds = loaded_any
    
    def _generate_procedural_sounds(self):
        """Generate all sounds procedurally"""
        self.sounds = {}
        self.music_tracks = {}
        
        # Generate music tracks
        self.music_tracks["menu"] = self._generate_music_loop("menu")
        self.music_tracks["Ground"] = self._generate_music_loop("explore")
        self.music_tracks["Estate"] = self._generate_music_loop("stealth")
        self.music_tracks["Tunnels"] = self._generate_music_loop("tunnels")
        self.music_tracks["Harbor"] = self._generate_music_loop("harbor")
        self.music_tracks["combat"] = self._generate_music_loop("combat")
        self.music_tracks["victory"] = self._generate_music_loop("victory")
        
        # Generate sound effects
        self.sounds["gunshot"] = self._generate_gunshot()
        self.sounds["footstep"] = self._generate_footstep()
        self.sounds["item_pickup"] = self._generate_pickup()
        self.sounds["door"] = self._generate_door()
        self.sounds["hurt"] = self._generate_hurt()
        self.sounds["guard_alert"] = self._generate_alert()
        
        # Set volumes
        for name, sound in self.sounds.items():
            if name == "hurt":
                sound.set_volume(self.priority_volume)
            else:
                sound.set_volume(self.sfx_volume)
        
        print("Generated procedural sounds")
    
    def _clamp_sample(self, value):
        """Clamp sample value to valid 16-bit range"""
        return max(-32767, min(32767, int(value)))
    
    def _generate_music_loop(self, style: str) -> pygame.mixer.Sound:
        """Generate procedural background music based on style"""
        sample_rate = 44100
        duration = 3.0
        samples = int(sample_rate * duration)
        data = array("h")
        
        # Define note sequences for different styles
        if style == "menu":
            notes = [220, 262, 330, 262]  # A3, C4, E4, C4
            base_freq = 1.0
        elif style == "explore":  # Ground
            notes = [196, 220, 262, 294]  # G3, A3, C4, D4
            base_freq = 1.2
        elif style == "stealth":  # Estate
            notes = [110, 147, 185, 147]  # A2, D3, F#3, D3
            base_freq = 0.8
        elif style == "tunnels":
            notes = [98, 123, 147, 185]  # G2, B2, D3, F#3
            base_freq = 0.6
        elif style == "harbor":
            notes = [262, 330, 392, 523]  # C4, E4, G4, C5
            base_freq = 1.5
        elif style == "combat":
            notes = [196, 233, 277, 311]  # G3, Bb3, Db4, Eb4
            base_freq = 1.8
        else:  # victory
            notes = [330, 392, 494, 587]  # E4, G4, B4, D5
            base_freq = 2.0
        
        for i in range(samples):
            t = i / sample_rate
            # Select note with some variation
            note_idx = int((t * base_freq) % len(notes))
            note = notes[note_idx]
            
            # Create a richer sound with harmonics - REDUCED AMPLITUDE
            wave = (math.sin(2 * math.pi * note * t) * 0.4 +
                    math.sin(2 * math.pi * note * 2 * t) * 0.2 +
                    math.sin(2 * math.pi * note * 0.5 * t) * 0.1)
            
            # Add envelope and fade
            envelope = 0.5 + 0.2 * math.sin(2 * math.pi * 0.3 * t)
            
            # Add slight tremolo for atmosphere
            tremolo = 0.8 + 0.1 * math.sin(2 * math.pi * 4 * t)
            
            value = wave * envelope * tremolo * 8000  # Reduced multiplier
            data.append(self._clamp_sample(value))
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_gunshot(self):
        """Generate a gunshot sound"""
        sample_rate = 44100
        duration = 0.3
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            # Sharp attack, quick decay
            envelope = math.exp(-t * 20)
            noise = (random.random() * 2 - 1) * envelope
            data.append(self._clamp_sample(20000 * noise))  # Reduced multiplier
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_hurt(self):
        """Generate a loud, painful sound"""
        sample_rate = 44100
        duration = 0.4
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            # Harsh, dissonant sound
            freq = 200 * math.exp(-t * 5)
            wave = (math.sin(2 * math.pi * freq * t) * 0.5 +
                   math.sin(2 * math.pi * freq * 1.5 * t) * 0.3)
            envelope = math.exp(-t * 8)
            value = wave * envelope * 25000  # High but safe multiplier
            data.append(self._clamp_sample(value))
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_footstep(self):
        """Generate a footstep sound"""
        sample_rate = 44100
        duration = 0.1
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            noise = (random.random() * 2 - 1) * math.exp(-t * 30)
            data.append(self._clamp_sample(10000 * noise))  # Reduced multiplier
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_pickup(self):
        """Generate an item pickup sound"""
        sample_rate = 44100
        duration = 0.15
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            freq = 440 * (1 + t * 10)  # Rising pitch
            wave = math.sin(2 * math.pi * freq * t)
            envelope = math.exp(-t * 10)
            data.append(self._clamp_sample(12000 * wave * envelope))  # Reduced multiplier
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_door(self):
        """Generate a door sound"""
        sample_rate = 44100
        duration = 0.3
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            # Low creaking sound
            noise = (random.random() * 2 - 1) * math.exp(-t * 8)
            data.append(self._clamp_sample(15000 * noise))  # Reduced multiplier
        
        return pygame.mixer.Sound(buffer=data)
    
    def _generate_alert(self):
        """Generate a guard alert sound"""
        sample_rate = 44100
        duration = 0.25
        samples = int(sample_rate * duration)
        data = array("h")
        
        for i in range(samples):
            t = i / sample_rate
            freq = 440 * (1 + t * 15)
            wave = math.sin(2 * math.pi * freq * t)
            envelope = 0.5 * math.exp(-t * 5)
            data.append(self._clamp_sample(15000 * wave * envelope))  # Reduced multiplier
        
        return pygame.mixer.Sound(buffer=data)
    
    def play(self, name: str):
        """Compatibility method - redirects to appropriate playback"""
        if name in ["menu", "Ground", "Estate", "Tunnels", "Harbor", "combat", "victory"]:
            self.play_music_for_zone(name, name == "combat")
        elif name in self.sounds:
            self.play_sound(name)
        else:
            print(f"Warning: Unknown audio '{name}'")
    
    def play_music_for_zone(self, zone: str, combat_active: bool = False):
        """Play appropriate music for current zone and combat state"""
        if not self.enabled:
            return
        
        # Determine which track to play
        if combat_active:
            track = "combat"
        elif zone in self.music_tracks:
            track = zone
        else:
            track = "menu"
        
        # Don't restart if same track is playing
        if hasattr(self, 'current_music') and self.current_music == track:
            return
        
        # Stop current music
        pygame.mixer.stop()
        
        # Play new track if we have it
        if track in self.music_tracks:
            self.music_tracks[track].play(loops=-1)
            self.current_music = track
    
    def play_sound(self, sound_name: str, priority: bool = False):
        """Play a sound effect with optional priority (louder)"""
        if not self.enabled or sound_name not in self.sounds:
            return
        
        # Save original volume
        original_vol = self.sounds[sound_name].get_volume()
        
        if priority:
            # Boost volume for priority sounds
            self.sounds[sound_name].set_volume(self.priority_volume)
        
        # Play the sound
        self.sounds[sound_name].play()
        
        # Restore original volume
        if priority:
            self.sounds[sound_name].set_volume(original_vol)
        
        # Trigger volume ducking for gunshots
        if sound_name == "gunshot":
            self.volume_duck_timer = self.duck_duration
    
    def update(self, dt: float):
        """Update volume ducking timer"""
        if self.volume_duck_timer > 0:
            self.volume_duck_timer -= dt
    
    def stop_music(self):
        """Stop all music"""
        pygame.mixer.stop()
        self.current_music = None
    
    def set_music_volume(self, volume: float):
        """Set music volume (0.0 to 1.0)"""
        self.music_volume = max(0.0, min(1.0, volume))
        for track in self.music_tracks.values():
            track.set_volume(self.music_volume)
    
    def set_sfx_volume(self, volume: float):
        """Set sound effects volume (0.0 to 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, volume))
        for name, sound in self.sounds.items():
            if name != "hurt":
                sound.set_volume(self.sfx_volume)