#!/usr/bin/env python3
import sys
import ctypes
import time
import numpy as np
import sdl2
import sdl2.ext
from numba import jit, uint32

# -----------------------------------------------------------------------------
# Timing constants (all in T-states)
T_STATES_PER_LINE = 224
T_STATES_PER_FRAME = 69888  # (64+192+56)*224
CLOCK_RATE = 3_500_000      # 3.5MHz

# -----------------------------------------------------------------------------
# CRT Display class: Handles window creation, rendering, texture updates
class CRT:
    # Display constants
    TOTAL_WIDTH = 352
    COLUMNS = TOTAL_WIDTH // 8
    FIELD_LINES = 312
    TOP_BLANKING = 16
    BOTTOM_BLANKING = 4
    VISIBLE_LINES = FIELD_LINES - TOP_BLANKING - BOTTOM_BLANKING
    CRT_LINES = VISIBLE_LINES * 2  # For interlacing

    def __init__(self, title="PYSE - Python Spectrum Emulator"):
        # Initialize SDL window and renderer with 2x scaling for better visibility
        self.window = sdl2.SDL_CreateWindow(
            title.encode(),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            self.TOTAL_WIDTH * 2,  # 2x horizontal scaling
            self.CRT_LINES,
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

        # Set 2x horizontal scaling
        sdl2.SDL_RenderSetScale(self.renderer, 2.0, 1.0)

        self.texture = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.TOTAL_WIDTH,
            self.CRT_LINES
        )
        if not self.texture:
            raise RuntimeError(f"SDL_CreateTexture Error: {sdl2.SDL_GetError().decode()}")

        # Create pixel buffer
        self.pixels = np.zeros((self.CRT_LINES, self.TOTAL_WIDTH), dtype=np.uint32)
        
        # Base title for window
        self.base_title = title
        
        # Flash state
        self.odd_field = False
        self.flash_inverted = False
        
        # Spectrum color palette (RGBA format)
        self.rgba_color_table = np.array([
            0x00000000,  # Black
            0x0000FF00,  # Blue
            0xFF000000,  # Red
            0xFF00FF00,  # Magenta
            0x00FF0000,  # Green
            0x00FFFF00,  # Cyan
            0xFFFF0000,  # Yellow
            0xFFFFFF00   # White
        ], dtype=np.uint32)

    def __del__(self):
        if hasattr(self, 'texture') and self.texture:
            sdl2.SDL_DestroyTexture(self.texture)
        if hasattr(self, 'renderer') and self.renderer:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if hasattr(self, 'window') and self.window:
            sdl2.SDL_DestroyWindow(self.window)

    def update_pixels(self, line, column, display_byte, attr_byte):
        """Update a group of 8 pixels based on display byte and attribute byte"""
        # Skip if in blanking interval
        if line < self.TOP_BLANKING or line >= (self.TOP_BLANKING + self.VISIBLE_LINES):
            return
            
        # Adjust for top blanking
        line -= self.TOP_BLANKING
        
        # Interlace fields (odd/even lines)
        line = line * 2 + (1 if self.odd_field else 0)
        
        # Calculate pixel offset
        offset_y = line
        offset_x = column * 8
        
        # Calculate bleed line (for phosphor effect)
        bleed_y = offset_y + (-1 if self.odd_field else 1)
        bleed_y = max(0, min(bleed_y, self.CRT_LINES - 1))  # Clamp to valid range
        
        # Parse attribute byte
        flash = (attr_byte & 0x80) != 0
        bright = (attr_byte & 0x40) != 0
        paper = (attr_byte >> 3) & 0x07
        ink = attr_byte & 0x07
        
        # Handle flash attribute
        if flash and self.flash_inverted:
            paper, ink = ink, paper
            
        # Get colors from palette
        paper_color = self.rgba_color_table[paper]
        ink_color = self.rgba_color_table[ink]
        
        # Update 8 pixels (MSB is leftmost)
        for bit in range(7, -1, -1):
            pixel_set = (display_byte & (1 << bit)) != 0
            color = ink_color if pixel_set else paper_color
            
            # Apply pixel to main scanline
            pixel_x = offset_x + (7 - bit)
            self.pixels[offset_y, pixel_x] = ((self.pixels[offset_y, pixel_x] >> 2) & 0x3F3F3F3F) | color
            
            # Apply bleed effect to adjacent scanline
            if not bright:
                # 50% brightness for non-bright colors
                bleed_color = ((color >> 1) & 0x7F7F7F7F) | 0x000000FF
            else:
                # 84% brightness for bright colors (mimics phosphor persistence)
                bleed_color = (((color >> 3) & 0x07070707) * 27) | 0x000000FF
                
            self.pixels[bleed_y, pixel_x] = ((self.pixels[bleed_y, pixel_x] >> 2) & 0x3F3F3F3F) | bleed_color

    def refresh(self):
        """Update the screen with current pixel data"""
        # Convert numpy array to ctypes array for SDL
        pixels_ptr = self.pixels.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32))
        
        sdl2.SDL_UpdateTexture(
            self.texture,
            None,
            pixels_ptr,
            self.TOTAL_WIDTH * ctypes.sizeof(ctypes.c_uint32)
        )
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        sdl2.SDL_RenderPresent(self.renderer)

    def toggle_flash(self):
        """Toggle the flash state for FLASH attribute"""
        self.flash_inverted = not self.flash_inverted

    def set_title_fps(self, fps):
        """Update window title with FPS information"""
        title = f"{self.base_title} - FPS: {fps:.1f}"
        sdl2.SDL_SetWindowTitle(self.window, title.encode())

    def toggle_field(self):
        """Toggle between odd and even fields for interlacing"""
        self.odd_field = not self.odd_field


# -----------------------------------------------------------------------------
# Test pattern generator to visualize the display
@jit(nopython=True)
def generate_test_pattern(pixels, width, height, color_table):
    """Generate a test pattern similar to ZX Spectrum's display"""
    # Clear the screen first
    for y in range(height):
        for x in range(width):
            pixels[y, x] = color_table[0]  # Black background
    
    # Draw a spectrum-like test pattern
    # ZX Spectrum has 24 rows of 32 columns (8x8 character cells)
    cell_width = 8
    cell_height = 8
    
    for row in range(24):
        for col in range(32):
            if col < width // cell_width and row < height // cell_height:
                # Choose colors based on position
                ink_color = (col % 8)  # Cycle through all 8 colors
                paper_color = (row % 8)  # Cycle through all 8 colors
                
                # Skip if ink and paper are the same to improve visibility
                if ink_color == paper_color:
                    ink_color = (ink_color + 4) % 8
                
                # Calculate cell position
                cell_x = col * cell_width
                cell_y = row * cell_height * 2  # Doubled for interlacing
                
                # Draw character cell (a block with a letter-like pattern)
                for cy in range(cell_height * 2):  # Double height for interlacing
                    for cx in range(cell_width):
                        y = cell_y + cy
                        x = cell_x + cx
                        
                        # Bounds check
                        if y < height and x < width:
                            # Create a simple pattern: horizontal stripes in some cells,
                            # vertical in others, and checkerboard in the rest
                            pattern_type = (row + col) % 3
                            
                            if pattern_type == 0:
                                # Horizontal stripes
                                is_ink = (cy // 2) % 2 == 0
                            elif pattern_type == 1:
                                # Vertical stripes
                                is_ink = cx % 2 == 0
                            else:
                                # Checkerboard
                                is_ink = ((cx % 2) ^ ((cy // 2) % 2)) == 0
                                
                            pixels[y, x] = color_table[ink_color if is_ink else paper_color]


# -----------------------------------------------------------------------------
# Memory class: Implements a 64K memory space with ROM protection
class Memory:
    def __init__(self):
        # Create 64K of RAM initialized to 0
        self.ram = np.zeros(0x10000, dtype=np.uint8)
        
        # Initialize screen memory with a recognizable pattern
        for y in range(192):
            for x in range(32):
                addr = 0x4000 + (y * 32) + x
                # Create diagonal stripes (similar to omse-mini)
                self.ram[addr] = 0xAA if ((x + (y // 8)) & 0x07) else 0x55
                
        # Set attributes to alternate colors
        for y in range(24):
            for x in range(32):
                attr_addr = 0x5800 + (y * 32) + x
                # Alternate between cyan on black and yellow on blue
                self.ram[attr_addr] = 0x45 if ((x + y) & 1) else 0x16
    
    def read(self, address):
        """Read a byte from memory at the specified address"""
        return self.ram[address]
    
    def write(self, address, value):
        """Write a byte to memory, with ROM protection"""
        if address < 0x4000:
            return  # Ignore writes to ROM
        self.ram[address] = value
    
    def load_from_file(self, filename, addr, size):
        """Load binary data from a file into memory"""
        try:
            with open(filename, 'rb') as f:
                # Get file size
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                f.seek(0)     # Seek back to beginning
                
                # Check if we have enough data
                if file_size < size:
                    raise RuntimeError(f"File too small: need at least {size} bytes")
                
                # Read data into memory
                data = f.read(size)
                self.ram[addr:addr+size] = np.frombuffer(data, dtype=np.uint8)
                
        except Exception as e:
            raise RuntimeError(f"Could not load file {filename}: {e}")
            
    def calculate_display_address(self, line, col):
        """Calculate the memory address for a display byte using Spectrum's screen layout"""
        # Start of screen memory
        addr = 0x4000
        
        # Add Y portion
        addr |= ((line & 0xC0) << 5)  # Which third of the screen (0-2)
        addr |= ((line & 0x07) << 8)  # Which character cell row (0-7)
        addr |= ((line & 0x38) << 2)  # Remaining bits (which row of character cells)
        
        # Add X portion
        addr |= col & 0b00011111      # 5 bits of X (0-31)
        
        return addr
    
    def calculate_attr_address(self, line, col):
        """Calculate the memory address for an attribute byte"""
        return 0x5800 + ((line >> 3) * 32) + col


# -----------------------------------------------------------------------------
# ULA (Uncommitted Logic Array) class: Handles display generation and timing
class ULA:
    # Display generation constants
    SCREEN_START_LINE = 64
    SCREEN_START_COLUMN = 6
    SCREEN_WIDTH_BYTES = 32
    SCREEN_HEIGHT = 192
    BORDER_T_STATES = SCREEN_START_COLUMN * 4
    SCREEN_WIDTH_T_STATES = SCREEN_WIDTH_BYTES * 4
    FIELD_LINES = CRT.FIELD_LINES
    FLASH_RATE = 16
    INTERRUPT_DURATION = 32
    
    def __init__(self, memory, crt):
        self.memory = memory
        self.crt = crt
        self.border_color = 0
        
        # Current position tracking for beam simulation
        self.line = 0           # Current scanline (0-311)
        self.line_cycle = 0     # Current cycle within line (0-223)
        self.current_column = 0
        self.flash_flipper = self.FLASH_RATE
    
    def tick(self):
        """Process one T-state of ULA operation"""
        # Check if we're in the visible (non-blanking) area
        visible = (self.line >= CRT.TOP_BLANKING and 
                  self.line < (CRT.FIELD_LINES - CRT.BOTTOM_BLANKING))
                  
        if visible and self.line_cycle < (CRT.COLUMNS * 4):
            # Only process during active display time
            # Every 4 cycles we output 8 pixels
            in_screen_line = (self.line >= self.SCREEN_START_LINE and 
                             self.line < (self.SCREEN_START_LINE + self.SCREEN_HEIGHT))
                             
            if self.line_cycle % 4 == 0:
                self.current_column = self.line_cycle // 4
                in_screen_col = (self.current_column >= self.SCREEN_START_COLUMN and 
                                self.current_column < (self.SCREEN_START_COLUMN + self.SCREEN_WIDTH_BYTES))
                                
                if in_screen_line and in_screen_col:
                    # We're in the active screen area - display pixel data from memory
                    screen_line = self.line - self.SCREEN_START_LINE
                    screen_col = self.current_column - self.SCREEN_START_COLUMN
                    
                    # Calculate memory addresses for display and attribute data
                    display_addr = self.memory.calculate_display_address(screen_line, screen_col)
                    attr_addr = self.memory.calculate_attr_address(screen_line, screen_col)
                    
                    # Read display and attribute bytes from memory
                    display_byte = self.memory.read(display_addr)
                    attr_byte = self.memory.read(attr_addr)
                    
                    # Update the display
                    self.crt.update_pixels(self.line, self.current_column, display_byte, attr_byte)
                else:
                    # In border area - display border color
                    border_attr = (self.border_color << 3)  # Border color as paper
                    self.crt.update_pixels(self.line, self.current_column, 0x00, border_attr)
        
        # Update position counters
        self.line_cycle += 1
        
        # Generate interrupts at the start of the frame
        if self.line == 0 and self.line_cycle == self.BORDER_T_STATES:
            # CPU interrupt would happen here in the full implementation
            pass
        elif self.line == 0 and self.line_cycle == self.BORDER_T_STATES + self.INTERRUPT_DURATION:
            # End of interrupt
            pass
            
        # Check if we've reached the end of a line
        if self.line_cycle >= T_STATES_PER_LINE:
            self.line_cycle = 0
            self.line += 1
            
            # Check if we've reached the end of a frame
            if self.line >= self.FIELD_LINES:
                self.line = 0
                self.flash_flipper -= 1
                
                # Toggle flash state at the flash rate (16 frames)
                if self.flash_flipper == 0:
                    self.flash_flipper = self.FLASH_RATE
                    self.crt.toggle_flash()
                
                # Toggle interlace field
                self.crt.toggle_field()
    
    def set_border_color(self, color):
        """Set the border color (0-7)"""
        self.border_color = color & 0x07
        
    def get_border_color(self):
        """Get the current border color"""
        return self.border_color


# -----------------------------------------------------------------------------
# System class: Manages the main event loop and timing
class System:
    # Chunk size for processing (in T-states)
    CHUNK_SIZE = 13 * 8 * 224  # Approximately 13 character rows
    
    def __init__(self):
        # Initialize components
        self.crt = CRT()
        self.memory = Memory()
        self.ula = ULA(self.memory, self.crt)
        
        # Timing variables
        self.current_t_state = 0
        
        # FPS tracking variables
        self.frame_count = 0
        self.fps = 0.0
        self.last_time = time.time()
        self.fps_update_interval = 0.5
        
        # Do an initial refresh to display the screen immediately
        self.crt.refresh()

    def run(self):
        quit = False
        event = sdl2.SDL_Event()
        
        # Track both virtual and real time
        start_time = time.time()
        next_refresh_t_state = self.current_t_state + T_STATES_PER_FRAME
        
        while not quit:
            # Process SDL events
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                if event.type == sdl2.SDL_QUIT:
                    quit = True
                elif event.type == sdl2.SDL_KEYDOWN:
                    # ESC key to quit
                    if event.key.keysym.sym == sdl2.SDLK_ESCAPE:
                        quit = True
                    # Number keys 0-7 to change border color
                    elif event.key.keysym.sym >= sdl2.SDLK_0 and event.key.keysym.sym <= sdl2.SDLK_7:
                        border_color = event.key.keysym.sym - sdl2.SDLK_0
                        self.ula.set_border_color(border_color)
            
            # Process a chunk of emulation
            target_t_state = self.current_t_state + self.CHUNK_SIZE
            while self.current_t_state < target_t_state:
                self.ula.tick()
                self.current_t_state += 1
            
            # FPS calculation
            current_time = time.time()
            self.frame_count += 1
            
            # Update FPS counter periodically
            elapsed = current_time - self.last_time
            if elapsed >= self.fps_update_interval:
                self.fps = self.frame_count / elapsed
                self.crt.set_title_fps(self.fps)
                self.frame_count = 0
                self.last_time = current_time
            
            # Check if we need to refresh the display
            if self.current_t_state >= next_refresh_t_state:
                self.crt.refresh()
                next_refresh_t_state += T_STATES_PER_FRAME
            
            # Sleep if we're ahead of real time
            target_time = start_time + ((self.current_t_state * 1_000_000) / CLOCK_RATE / 1_000_000)
            time_ahead = target_time - time.time()
            
            if time_ahead > 0.001:  # More than 1ms ahead
                time.sleep(time_ahead - 0.001)  # Leave 1ms margin
    
    def load_scr(self, filename):
        """Load a .scr screen file"""
        try:
            self.memory.load_from_file(filename, 0x4000, 6912)
        except Exception as e:
            print(f"Error loading SCR file: {e}", file=sys.stderr)
            
    def load_rom(self, filename):
        """Load a ROM file into memory at address 0x0000"""
        try:
            self.memory.load_from_file(filename, 0x0000, 16384)  # 16KB ROM
        except Exception as e:
            print(f"Error loading ROM file: {e}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Main: Initializes SDL, runs the system, and handles any exceptions
def main():
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        print(f"SDL_Init Error: {sdl2.SDL_GetError().decode()}", file=sys.stderr)
        return 1

    try:
        # Parse command line arguments
        system = System()
        
        # Track if a ROM has been loaded
        rom_loaded = False
        
        # Handle command line arguments for loading files
        if len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                if arg == "-h" or arg == "--help":
                    print(f"Usage: {sys.argv[0]} [options] [filename...]")
                    print("Options:")
                    print("  -h, --help           Display command information")
                    print("Available file formats:")
                    print("  .scr                 Screen data (6912 bytes)")
                    print("  .rom                 System ROM (16384 bytes)")
                    print("Default ROM '48.rom' will be loaded if no ROM specified.")
                    return 0
                elif arg.endswith(".scr"):
                    print(f"Loading screen file: {arg}")
                    system.load_scr(arg)
                elif arg.endswith(".rom"):
                    print(f"Loading ROM file: {arg}")
                    system.load_rom(arg)
                    rom_loaded = True
                else:
                    print(f"Unknown file type: {arg}", file=sys.stderr)
        
        # Load default ROM if no ROM was specified
        if not rom_loaded:
            try:
                print("Loading default ROM: 48.rom")
                system.load_rom("48.rom")
            except Exception as e:
                print(f"Error loading default ROM: {e}", file=sys.stderr)
        
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