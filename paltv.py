#!/usr/bin/env python3
import sys
import random
import ctypes
import sdl2
import sdl2.ext
import time
import numpy as np
from numba import jit, uint32, int32, float32

# -----------------------------------------------------------------------------
# Display class: Handles window creation, rendering, texture updates, and frame
# generation.
class Display:
    WIDTH = 720
    HEIGHT = 576

    def __init__(self, title):
        self.window = sdl2.SDL_CreateWindow(
            title.encode(),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            self.WIDTH,
            self.HEIGHT,
            sdl2.SDL_WINDOW_SHOWN
        )
        if not self.window:
            raise RuntimeError(f"SDL_CreateWindow Error: {sdl2.SDL_GetError().decode()}")

        self.renderer = sdl2.SDL_CreateRenderer(
            self.window, 
            -1, 
            sdl2.SDL_RENDERER_ACCELERATED
        )
        if not self.renderer:
            raise RuntimeError(f"SDL_CreateRenderer Error: {sdl2.SDL_GetError().decode()}")

        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_ARGB8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.WIDTH,
            self.HEIGHT
        )
        if not self.texture:
            raise RuntimeError(f"SDL_CreateTexture Error: {sdl2.SDL_GetError().decode()}")

        # Create pixel buffer
        self.pixels = (ctypes.c_uint32 * (self.WIDTH * self.HEIGHT))()
        
        # Initialize random number generator
        random.seed()
        
        # Base title for window
        self.base_title = title
        
        # Random noise array
        self.noise_array = np.random.randint(0, 0xFFFFFFFF, (self.HEIGHT, self.WIDTH), dtype=np.uint32)

    def __del__(self):
        if hasattr(self, 'texture') and self.texture:
            sdl2.SDL_DestroyTexture(self.texture)
        if hasattr(self, 'renderer') and self.renderer:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if hasattr(self, 'window') and self.window:
            sdl2.SDL_DestroyWindow(self.window)

    # Updates the frame: regenerates the display with color bars, scanlines,
    # and noise.
    def update(self):
        # Update the noise array with fresh random values
        self.noise_array = np.random.randint(0, 0xFFFFFFFF, (self.HEIGHT, self.WIDTH), dtype=np.uint32)
        
        self.generate_frame()
        sdl2.SDL_UpdateTexture(
            self.texture,
            None,
            ctypes.byref(self.pixels),
            self.WIDTH * ctypes.sizeof(ctypes.c_uint32)
        )
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        sdl2.SDL_RenderPresent(self.renderer)
        
    def set_title_fps(self, fps):
        """Update window title with FPS information"""
        title = f"{self.base_title} - FPS: {fps:.1f}"
        sdl2.SDL_SetWindowTitle(self.window, title.encode())

    # Generates a frame with classic color bars, a scanline effect, and some
    # noise.
    def generate_frame(self):
        # Convert to NumPy array for Numba
        pixels_array = np.frombuffer(self.pixels, dtype=np.uint32).reshape(self.HEIGHT, self.WIDTH)
        
        # 7 color bars (ARGB): white, yellow, cyan, green, magenta, red, blue.
        color_bars = np.array([
            0xFFFFFFFF,  # White
            0xFFFFFF00,  # Yellow
            0xFF00FFFF,  # Cyan
            0xFF00FF00,  # Green
            0xFFFF00FF,  # Magenta
            0xFFFF0000,  # Red
            0xFF0000FF   # Blue
        ], dtype=np.uint32)
        
        # Call JIT-optimized function
        _generate_frame_jit(pixels_array, self.WIDTH, self.HEIGHT, color_bars, self.noise_array)

# JIT-optimized function for pixel manipulation
@jit(nopython=True)
def _generate_frame_jit(pixels, width, height, color_bars, noise_array):
    for y in range(height):
        brightness = 0.75 if y % 2 == 0 else 1.0  # Scanline dimming
        for x in range(width):
            bar_index = (x * 7) // width
            base_color = color_bars[bar_index]

            # Extract ARGB components and apply brightness
            a = (base_color >> 24) & 0xFF
            r = int(((base_color >> 16) & 0xFF) * brightness)
            g = int(((base_color >> 8) & 0xFF) * brightness)
            b = int((base_color & 0xFF) * brightness)
            color = (a << 24) | (r << 16) | (g << 8) | b

            # Use pre-generated noise from the noise array
            # Generate a mask to add noise. 1s in the high bits (and
            # the alpha channel), random noise in the low order bits.
            noise = noise_array[y, x] | 0xFFC0C0C0
            color &= noise

            pixels[y, x] = color


# -----------------------------------------------------------------------------
# System class: Manages the main event loop.
class System:
    def __init__(self):
        self.display = Display("Retro PAL TV Simulation in Python")
        # FPS tracking variables
        self.frame_count = 0
        self.fps = 0.0
        self.last_time = time.time()
        self.fps_update_interval = 0.5  # Update FPS display every 0.5 seconds

    def run(self):
        quit = False
        event = sdl2.SDL_Event()
        
        while not quit:
            # FPS calculation
            current_time = time.time()
            self.frame_count += 1
            
            # Update FPS counter every fps_update_interval seconds
            elapsed = current_time - self.last_time
            if elapsed >= self.fps_update_interval:
                self.fps = self.frame_count / elapsed
                self.display.set_title_fps(self.fps)
                self.frame_count = 0
                self.last_time = current_time
            
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                if event.type == sdl2.SDL_QUIT or event.type == sdl2.SDL_KEYDOWN:
                    quit = True
            
            self.display.update()
            sdl2.SDL_Delay(16)  # ~60 FPS target


# -----------------------------------------------------------------------------
# Main: Initializes SDL, runs the system, and handles any exceptions.
def main():
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        print(f"SDL_Init Error: {sdl2.SDL_GetError().decode()}", file=sys.stderr)
        return 1

    try:
        system = System()
        system.run()
    except Exception as ex:
        print(f"Exception caught: {ex}", file=sys.stderr)
        sdl2.SDL_Quit()
        return 1
    finally:
        sdl2.SDL_Quit()
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 