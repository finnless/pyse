#!/usr/bin/env python3
import sys
import random
import ctypes
import sdl2
import sdl2.ext

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

    # Generates a frame with classic color bars, a scanline effect, and some
    # noise.
    def generate_frame(self):
        # 7 color bars (ARGB): white, yellow, cyan, green, magenta, red, blue.
        color_bars = [
            0xFFFFFFFF,  # White
            0xFFFFFF00,  # Yellow
            0xFF00FFFF,  # Cyan
            0xFF00FF00,  # Green
            0xFFFF00FF,  # Magenta
            0xFFFF0000,  # Red
            0xFF0000FF   # Blue
        ]

        for y in range(self.HEIGHT):
            brightness = 0.75 if y % 2 == 0 else 1.0  # Scanline dimming
            for x in range(self.WIDTH):
                bar_index = (x * 7) // self.WIDTH
                base_color = color_bars[bar_index]

                # Extract ARGB components and apply brightness
                a = (base_color >> 24) & 0xFF
                r = int(((base_color >> 16) & 0xFF) * brightness)
                g = int(((base_color >> 8) & 0xFF) * brightness)
                b = int((base_color & 0xFF) * brightness)
                color = (a << 24) | (r << 16) | (g << 8) | b

                # Generate a mask to add noise. 1s in the high bits (and
                # the alpha channel), random noise in the low order bits.
                noise = random.randint(0, 0xFFFFFFFF) | 0xFFC0C0C0
                color &= noise

                self.pixels[y * self.WIDTH + x] = color


# -----------------------------------------------------------------------------
# System class: Manages the main event loop.
class System:
    def __init__(self):
        self.display = Display("Retro PAL TV Simulation in Python")

    def run(self):
        quit = False
        event = sdl2.SDL_Event()
        while not quit:
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                if event.type == sdl2.SDL_QUIT or event.type == sdl2.SDL_KEYDOWN:
                    quit = True
            self.display.update()
            sdl2.SDL_Delay(16)  # ~60 FPS


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