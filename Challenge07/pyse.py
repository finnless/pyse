#!/usr/bin/env python3
import sys
import ctypes
import time
import numpy as np
import sdl2
import sdl2.ext
from numba import jit, uint32
import os

# Add the vendored pyz80 directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
pyz80_dir = os.path.join(script_dir, 'pyz80')
if pyz80_dir not in sys.path:
    sys.path.insert(0, pyz80_dir)

# TODO REMOVE THIS GARBAGE. change pyz80 to an installed package.
os.chdir(os.path.join(os.path.dirname(__file__), 'pyz80'))

# Import Z80 CPU
from pyz80 import Z80
from _z80_bindings import Z80_INT, Z80_M1, Z80_MREQ, Z80_IORQ, Z80_RD, Z80_WR, Z80_SET_DATA, Z80_PIN_D0

# TODO REMOVE THIS GARBAGE
# Change back to original directory
os.chdir(os.path.dirname(__file__))

# Global debug flag
DEBUG_ENABLED = False

def debug_print(*args, **kwargs):
    """Print function that respects the global debug flag"""
    if DEBUG_ENABLED:
        print("DEBUG_ENABLED: ", DEBUG_ENABLED)
        print(*args, **kwargs)

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
            0x000000FF,  # Black
            0x0000FFFF,  # Blue
            0xFF0000FF,  # Red
            0xFF00FFFF,  # Magenta
            0x00FF00FF,  # Green
            0x00FFFFFF,  # Cyan
            0xFFFF00FF,  # Yellow
            0xFFFFFFFF   # White
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
        update_pixels_jit(self.pixels, line, column, display_byte, attr_byte,
                          self.TOP_BLANKING, self.VISIBLE_LINES, self.TOTAL_WIDTH, self.CRT_LINES,
                          self.odd_field, self.flash_inverted, self.rgba_color_table)

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


# JIT-compiled pixel update function for better performance
@jit(nopython=True)
def update_pixels_jit(pixels, line, column, display_byte, attr_byte, 
                      top_blanking, visible_lines, total_width, crt_lines,
                      odd_field, flash_inverted, rgba_color_table):
    """Update a group of 8 pixels based on display byte and attribute byte with Numba acceleration"""
    # Skip if in blanking interval
    if line < top_blanking or line >= (top_blanking + visible_lines):
        return
        
    # Adjust for top blanking
    line -= top_blanking
    
    # Interlace fields (odd/even lines)
    line = line * 2 + (1 if odd_field else 0)
    
    # Calculate pixel offset
    offset_y = line
    offset_x = column * 8
    
    # Calculate bleed line (for phosphor effect)
    bleed_y = offset_y + (-1 if odd_field else 1)
    bleed_y = max(0, min(bleed_y, crt_lines - 1))  # Clamp to valid range
    
    # Parse attribute byte
    flash = (attr_byte & 0x80) != 0
    bright = (attr_byte & 0x40) != 0
    paper = (attr_byte >> 3) & 0x07
    ink = attr_byte & 0x07
    
    # Handle flash attribute
    if flash and flash_inverted:
        temp = paper
        paper = ink
        ink = temp
        
    # Get colors from palette
    paper_color = rgba_color_table[paper]
    ink_color = rgba_color_table[ink]
    
    # Update 8 pixels (MSB is leftmost)
    for bit in range(7, -1, -1):
        pixel_set = (display_byte & (1 << bit)) != 0
        color = ink_color if pixel_set else paper_color
        
        # Apply pixel to main scanline
        pixel_x = offset_x + (7 - bit)
        pixels[offset_y, pixel_x] = ((pixels[offset_y, pixel_x] >> 2) & 0x3F3F3F3F) | color
        
        # Apply bleed effect to adjacent scanline
        if not bright:
            # 50% brightness for non-bright colors
            bleed_color = ((color >> 1) & 0x7F7F7F7F) | 0x000000FF
        else:
            # 84% brightness for bright colors (mimics phosphor persistence)
            bleed_color = (((color >> 3) & 0x07070707) * 27) | 0x000000FF
            
        pixels[bleed_y, pixel_x] = ((pixels[bleed_y, pixel_x] >> 2) & 0x3F3F3F3F) | bleed_color


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
            # return  # Ignore writes to ROM
            # TODO: See if we should reenable this memory protection
            pass  # Ignore writes to ROM
        # Track writes to screen memory (0x4000-0x5AFF)
        if 0x4000 <= address <= 0x5AFF:
            # Print only a small number of screen writes to avoid overwhelming output
            if (address & 0xFF) == 0:
                debug_print(f"Screen write: 0x{address:04X} = 0x{value:02X}")
                
        self.ram[address] = value
    
    def load_from_file(self, filename, addr, size):
        """Load binary data from a file into memory"""
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
# IODevice: Abstract base class for IO devices
class IODevice:
    def read(self, addr):
        """Read a byte from IO port at the specified address"""
        return 0xFF  # Default implementation returns 0xFF (all bits set)
    
    def write(self, addr, value):
        """Write a byte to IO port at the specified address"""
        pass  # Default implementation does nothing


# -----------------------------------------------------------------------------
# IODeviceBus: Manages IO devices with port masking
class IODeviceBus:
    def __init__(self):
        # List of (mask, device) pairs
        self.devices = []
    
    def add_device(self, mask, device):
        """Add a device with the specified port mask
        
        Args:
            mask: port mask (devices respond when ~addr & mask == mask)
            device: IODevice instance
        """
        self.devices.append((mask, device))
    
    def read(self, addr):
        """Read from the appropriate device based on port address"""
        for mask, device in self.devices:
            if ((~addr) & mask) == mask:
                return device.read(addr)
        return 0xFF  # Default return value if no device responds
    
    def write(self, addr, value):
        """Write to the appropriate device based on port address"""
        for mask, device in self.devices:
            if ((~addr) & mask) == mask:
                device.write(addr, value)
                return


# -----------------------------------------------------------------------------
# CPU class: Wraps the Z80 CPU and interfaces with memory and IO
class CPU:
    def __init__(self, memory, io_bus=None):
        self.memory = memory
        self.io_bus = io_bus
        self.z80 = Z80()
        self.pins = self.z80.pins
        
    def get_state_summary(self):
        """Get a clean summary of the CPU state"""
        return str(self.z80)
        
    def tick(self):
        """Process one CPU cycle"""
        # print(f"pyse::CPU::tick 1: pins = {self.pins} (0x{self.pins:016X})")
        self.pins = self.z80.tick(self.pins)
        # print(f"pyse::CPU::tick 2: pins = {self.pins} (0x{self.pins:016X})")
        
        # Monitor state after interrupt (with countdown to avoid too much output)
        if hasattr(self, 'check_state_after_interrupt'):
            self.check_state_after_interrupt -= 1
            if self.check_state_after_interrupt == 0:
                debug_print(f"CPU State after interrupt handling: {self.get_state_summary()}")
                delattr(self, 'check_state_after_interrupt')
        
    def transact(self):
        """Handle memory and IO transactions based on pin state"""
        if (self.pins & Z80_MREQ):  # Memory request
            addr = self.z80.addr
            if (self.pins & Z80_RD):  # Memory read
                # Add IM2 vector table read debugging
                if self.z80.im == 2 and hasattr(self, 'in_interrupt_sequence'):
                    # For IM2, we need to track reads during interrupt
                    i_reg = self.z80.i
                    vector_base = (i_reg << 8)
                    if addr >= vector_base and addr <= vector_base + 1:
                        debug_print(f"IM2: Reading from vector table at 0x{addr:04X} = 0x{self.memory.read(addr):02X}")
                    
                data = self.memory.read(addr)
                self.pins = Z80_SET_DATA((self.pins), int(data & 0xFF))
            elif (self.pins & Z80_WR):  # Memory write
                data = self.z80.data
                self.memory.write(addr, data)
        elif (self.pins & Z80_IORQ):  # IO request
            addr = self.z80.addr
            if (self.pins & Z80_M1):  # Interrupt acknowledge
                debug_print(f"CPU: Interrupt acknowledged at T-state cycle")
                debug_print(f"CPU State during INT ACK: {self.get_state_summary()}")
                debug_print(f"Pin state during INT ACK: 0x{self.pins:016X}")
                debug_print(f"INT ACK: M1={self.z80.is_m1()}, IORQ={self.z80.is_iorq()}, RD={self.z80.is_rd()}")
                
                # Add IM2 vector calculation debugging
                if self.z80.im == 2:
                    i_reg = self.z80.i
                    data_bus_value = 0xFF  # Value we'll put on data bus
                    vector_addr = (i_reg << 8) | data_bus_value
                    debug_print(f"IM2 Interrupt Ack: I={i_reg:02X}, Data Bus=0xFF, Vector Address=0x{vector_addr:04X}")
                    
                    # For debugging: Show what's at that memory location
                    low_byte = self.memory.read(vector_addr)
                    high_byte = self.memory.read(vector_addr + 1)
                    handler_addr = (high_byte << 8) | low_byte
                    debug_print(f"IM2 Vector Table: Reading from 0x{vector_addr:04X}, points to 0x{handler_addr:04X}")
                    
                    # Flag to track this interrupt sequence
                    self.in_interrupt_sequence = True
                
                self.pins = Z80_SET_DATA((self.pins), 0xFF)
                # Set a flag to check state after a few cycles
                self.check_state_after_interrupt = 20  # Check after fewer cycles
            else:
                if (self.pins & Z80_RD):  # IO read
                    if self.io_bus is not None:
                        data = self.io_bus.read(addr)
                    else:
                        data = 0xFF  # Default if no IO bus
                    self.pins = Z80_SET_DATA((self.pins), int(data & 0xFF))
                elif (self.pins & Z80_WR):  # IO write
                    data = self.z80.data
                    debug_print(f"CPU: IO Write - Port: 0x{addr:04X}, Data: 0x{data:02X}, Pins: 0x{self.pins:016X}")
                    if self.io_bus is not None:
                        self.io_bus.write(addr, data)
                        debug_print(f"CPU: IO Write forwarded to IO bus")
    
    def interrupt(self, status=True):
        """Set or clear the interrupt pin"""
        if status:
            debug_print(f"CPU: Setting interrupt pin (INT=1)")
            debug_print(f"CPU State: {self.get_state_summary()}")
            debug_print(f"Pin state before interrupt: 0x{self.pins:016X}")
            debug_print(f"IFF1={self.z80.iff1}, IFF2={self.z80.iff2}, IM={self.z80.im}")
            self.pins |= Z80_INT  # Set interrupt pin
            debug_print(f"Pin state after setting INT: 0x{self.pins:016X}")
        else:
            debug_print(f"CPU: Clearing interrupt pin (INT=0)")
            debug_print(f"Pin state before clearing: 0x{self.pins:016X}")
            self.pins &= ~Z80_INT  # Clear interrupt pin
            debug_print(f"Pin state after clearing INT: 0x{self.pins:016X}")
            debug_print(f"IFF1={self.z80.iff1}, IFF2={self.z80.iff2}, IM={self.z80.im}")
            
    def set_pc(self, addr):
        """Set the program counter to a specific address"""
        self.pins = self.z80.prefetch(addr)
        
    def set_register_i(self, value):
        """Set Z80 I register"""
        self.z80.i = value
        
    def set_register_r(self, value):
        """Set Z80 R register"""
        self.z80.r = value
        
    def set_register_iff2(self, value):
        """Set Z80 IFF2 flag (enable/disable interrupts)"""
        self.z80.iff2 = value
        
    def set_register_im(self, value):
        """Set Z80 interrupt mode (0/1/2)"""
        self.z80.im = value
        
    def set_register_pair(self, pair_name, value):
        """Set a register pair (HL, DE, BC, AF, IX, IY, SP)"""
        if pair_name == 'hl':
            self.z80.hl = value
        elif pair_name == 'de':
            self.z80.de = value
        elif pair_name == 'bc':
            self.z80.bc = value
        elif pair_name == 'af':
            self.z80.af = value
        elif pair_name == 'ix':
            self.z80.ix = value
        elif pair_name == 'iy':
            self.z80.iy = value
        elif pair_name == 'sp':
            self.z80.sp = value
        elif pair_name == 'hl_alt' or pair_name == 'hl2':
            self.z80.hl_prime = value
        elif pair_name == 'de_alt' or pair_name == 'de2':
            self.z80.de_prime = value
        elif pair_name == 'bc_alt' or pair_name == 'bc2':
            self.z80.bc_prime = value
        elif pair_name == 'af_alt' or pair_name == 'af2':
            self.z80.af_prime = value


# -----------------------------------------------------------------------------
# Keyboard class: Handles keyboard input for the ZX Spectrum
class Keyboard(IODevice):
    """
    ZX Spectrum Keyboard implementation
    
    The ZX Spectrum keyboard is arranged as an 8x5 matrix:
    - 8 rows (0-7), each mapped to a specific address line
    - 5 columns (bits 0-4), each representing a key within that row
    
    When reading the keyboard, the Z80 uses I/O port addresses where:
    - The low byte is usually 0xFE
    - The high byte has specific bits cleared to select the rows to read
    
    The port mapping is as follows:
    | Port    | Row | Keys                   |
    |---------|-----|------------------------|
    | 0xFEFE  | 0   | CAPS, Z, X, C, V       |
    | 0xFDFE  | 1   | A, S, D, F, G          |
    | 0xFBFE  | 2   | Q, W, E, R, T          |
    | 0xF7FE  | 3   | 1, 2, 3, 4, 5          |
    | 0xEFFE  | 4   | 0, 9, 8, 7, 6          |
    | 0xDFFE  | 5   | P, O, I, U, Y          |
    | 0xBFFE  | 6   | ENTER, L, K, J, H      |
    | 0x7FFE  | 7   | SPACE, SYM, M, N, B    |
    
    The keyboard state is represented as 8 bytes, one for each row.
    Within each byte, bits 0-4 represent the 5 keys in that row.
    A value of 0 means the key is pressed, 1 means not pressed.
    """

    def __init__(self):
        super().__init__()
        # Initialize keyboard state (8 rows with 5 bits per row)
        # In ZX Spectrum, 0=pressed, 1=not pressed, so initialize all to 0xFF (not pressed)
        self.rows = [0xFF] * 8
        
        # Debug flag
        self.debug_mode = False
        
        # Define mapping from SDL scancodes to ZX Spectrum keyboard positions
        # Format: SDL_SCANCODE: (row, bit_mask)
        self.key_map = {
            # Row 0: CAPS SHIFT, Z, X, C, V
            sdl2.SDL_SCANCODE_LSHIFT: (0, 0x01),
            sdl2.SDL_SCANCODE_RSHIFT: (0, 0x01),  # Both shifts map to CAPS SHIFT
            sdl2.SDL_SCANCODE_Z: (0, 0x02),
            sdl2.SDL_SCANCODE_X: (0, 0x04),
            sdl2.SDL_SCANCODE_C: (0, 0x08),
            sdl2.SDL_SCANCODE_V: (0, 0x10),
            
            # Row 1: A, S, D, F, G
            sdl2.SDL_SCANCODE_A: (1, 0x01),
            sdl2.SDL_SCANCODE_S: (1, 0x02),
            sdl2.SDL_SCANCODE_D: (1, 0x04),
            sdl2.SDL_SCANCODE_F: (1, 0x08),
            sdl2.SDL_SCANCODE_G: (1, 0x10),
            
            # Row 2: Q, W, E, R, T
            sdl2.SDL_SCANCODE_Q: (2, 0x01),
            sdl2.SDL_SCANCODE_W: (2, 0x02),
            sdl2.SDL_SCANCODE_E: (2, 0x04),
            sdl2.SDL_SCANCODE_R: (2, 0x08),
            sdl2.SDL_SCANCODE_T: (2, 0x10),
            
            # Row 3: 1, 2, 3, 4, 5
            sdl2.SDL_SCANCODE_1: (3, 0x01),
            sdl2.SDL_SCANCODE_2: (3, 0x02),
            sdl2.SDL_SCANCODE_3: (3, 0x04),
            sdl2.SDL_SCANCODE_4: (3, 0x08),
            sdl2.SDL_SCANCODE_5: (3, 0x10),
            
            # Row 4: 0, 9, 8, 7, 6
            sdl2.SDL_SCANCODE_0: (4, 0x01),
            sdl2.SDL_SCANCODE_9: (4, 0x02),
            sdl2.SDL_SCANCODE_8: (4, 0x04),
            sdl2.SDL_SCANCODE_7: (4, 0x08),
            sdl2.SDL_SCANCODE_6: (4, 0x10),
            
            # Row 5: P, O, I, U, Y
            sdl2.SDL_SCANCODE_P: (5, 0x01),
            sdl2.SDL_SCANCODE_O: (5, 0x02),
            sdl2.SDL_SCANCODE_I: (5, 0x04),
            sdl2.SDL_SCANCODE_U: (5, 0x08),
            sdl2.SDL_SCANCODE_Y: (5, 0x10),
            
            # Row 6: ENTER, L, K, J, H
            sdl2.SDL_SCANCODE_RETURN: (6, 0x01),
            sdl2.SDL_SCANCODE_L: (6, 0x02),
            sdl2.SDL_SCANCODE_K: (6, 0x04),
            sdl2.SDL_SCANCODE_J: (6, 0x08),
            sdl2.SDL_SCANCODE_H: (6, 0x10),
            
            # Row 7: SPACE, SYM SHIFT (LCTRL), M, N, B
            sdl2.SDL_SCANCODE_SPACE: (7, 0x01),
            sdl2.SDL_SCANCODE_LCTRL: (7, 0x02),  # Left CTRL as SYM SHIFT
            sdl2.SDL_SCANCODE_M: (7, 0x04),
            sdl2.SDL_SCANCODE_N: (7, 0x08),
            sdl2.SDL_SCANCODE_B: (7, 0x10),
        }
    
    def press(self, scancode):
        """Handle key press event - set the corresponding bit to 0"""
        if scancode in self.key_map:
            row, bit_mask = self.key_map[scancode]
            # Clear the bit (0 = pressed in ZX Spectrum)
            self.rows[row] &= ~bit_mask
            
            if self.debug_mode:
                self.print_debug_info()
    
    def release(self, scancode):
        """Handle key release event - set the corresponding bit to 1"""
        if scancode in self.key_map:
            row, bit_mask = self.key_map[scancode]
            # Set the bit (1 = not pressed in ZX Spectrum)
            self.rows[row] |= bit_mask
            
            if self.debug_mode:
                self.print_debug_info()
                
    def print_debug_info(self):
        """Print debug information about the current keyboard state"""
        debug_print("Keyboard State:")
        for row in range(8):
            bits = ""
            for bit in range(5):
                bit_value = (self.rows[row] >> bit) & 0x01
                bits += str(bit_value)
            debug_print(f"Row {row}: {bits} (0x{self.rows[row]:02X})")
        debug_print("--------")
    
    def toggle_debug_mode(self):
        """Toggle keyboard debug mode"""
        self.debug_mode = not self.debug_mode
        debug_print(f"Keyboard debug mode: {'ON' if self.debug_mode else 'OFF'}")
        
        if self.debug_mode:
            self.print_debug_info()
    
    def read_row(self, row):
        """Read the state of a specific keyboard row"""
        if 0 <= row < 8:
            return self.rows[row]
        return 0xFF  # Default: all keys up
    
    def read(self, addr):
        """Implement the IODevice interface for keyboard reading
        
        On the ZX Spectrum, keyboard is read through the ULA:
        - Low byte of address is typically 0xFE
        - Bits of high byte select which rows to read:
          - Bit 0 clear (0xFE) selects row 0
          - Bit 1 clear (0xFD) selects row 1
          - etc.
        - If multiple bits are clear, then multiple rows are read
          and the results are combined with bitwise AND
        """
        # We only care about the high byte for keyboard reading
        high_byte = (addr >> 8) & 0xFF
        
        # Initialize result with all 1s (no keys pressed)
        result = 0xFF
        
        # For each cleared bit in the high byte, read the corresponding row
        for row in range(8):
            # Check if this row's bit is cleared in the high byte
            if not (high_byte & (1 << row)):
                # If the bit is cleared, read this row and combine with result
                result &= self.rows[row]
        
        return result


# -----------------------------------------------------------------------------
# ULA (Uncommitted Logic Array) class: Handles display generation and timing
class ULA(IODevice):
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
    
    def __init__(self, memory, crt, cpu):
        super().__init__()
        self.memory = memory
        self.crt = crt
        self.cpu = cpu
        self.border_color = 0
        self.keyboard = Keyboard()  # Create keyboard instance
        
        # Current position tracking for beam simulation
        self.line = 0           # Current scanline (0-311)
        self.line_cycle = 0     # Current cycle within line (0-223)
        self.current_column = 0
        self.flash_flipper = self.FLASH_RATE
    
    def read(self, addr):
        """Read from ULA ports (0xFE)"""
        # The ULA handles both keyboard input and other I/O
        # For keyboard reads, the high byte of the address selects which rows to read
        
        # Check the low byte - ULA responds to port addresses with bit 0 clear
        if (addr & 0x01) == 0:
            # Get keyboard state
            keyboard_state = self.keyboard.read(addr)
            
            # The lower 5 bits come from the keyboard (bits 0-4)
            # The upper 3 bits (bits 5-7) are always 1
            # So we need to clear bits 5-7 from keyboard_state and then set them to 1
            result = (keyboard_state & 0x1F) | 0xE0
            
            return result
        
        # Default return for non-keyboard reads
        return 0xFF
    
    def write(self, addr, value):
        """Write to ULA ports (0xFE)"""
        # Border color is in the lower 3 bits
        self.set_border_color(value)
    
    def tick(self):
        """Process one T-state of ULA operation"""
        # First tick the CPU
        self.cpu.tick()
        
        # Check for interrupt-related state immediately after CPU tick
        if self.cpu.pins & Z80_INT:
            if self.cpu.z80.pc == 0x38 or (self.cpu.z80.is_m1() and self.cpu.z80.is_iorq()):
                debug_print(f"ULA: Detected interrupt activity after CPU tick - PC=0x{self.cpu.z80.pc:04X}, M1={self.cpu.z80.is_m1()}, IORQ={self.cpu.z80.is_iorq()}, INT={bool(self.cpu.pins & Z80_INT)}")
                debug_print(f"ULA: CPU flags - IFF1={self.cpu.z80.iff1}, IFF2={self.cpu.z80.iff2}, pins=0x{self.cpu.pins:016X}")
        
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
        
        self.cpu.transact()
        
        if self.cpu.z80.is_m1() and self.cpu.z80.is_iorq():
            debug_print(f"INT ACKNOWLEDGE: PC={self.cpu.z80.pc:04X}, IFF1={self.cpu.z80.iff1}, IFF2={self.cpu.z80.iff2}")
        elif self.cpu.z80.pc == 0x38:
            debug_print(f"INTERRUPT HANDLER: PC=0x38, AF={self.cpu.z80.af:04X}, pins=0x{self.cpu.pins:016X}")
        
        # int handler
        if self.cpu.z80.pc >= 0x38 and self.cpu.z80.pc <= 0x44:
            debug_print(f"INT HANDLER STEP: PC=0x{self.cpu.z80.pc:04X}, A={self.cpu.z80.af>>8:02X}, pins=0x{self.cpu.pins:016X}")
            
            # Specifically trace the RET instruction
            if self.cpu.z80.pc == 0x44:
                debug_print(f"RETURN FROM INTERRUPT: PC=0x44, AF={self.cpu.z80.af:04X}, IFF1={self.cpu.z80.iff1}, IFF2={self.cpu.z80.iff2}")
            # Specifically trace the EI instruction
            elif self.cpu.z80.pc == 0x43:
                debug_print(f"ENABLE INTERRUPTS (EI): PC=0x43, IFF1 before={self.cpu.z80.iff1}, IFF2 before={self.cpu.z80.iff2}")
                # Note: The IFF flags will be updated AFTER this instruction executes
        
        # Track if we're returning to main program from interrupt handler
        if hasattr(self, 'last_pc') and self.last_pc == 0x44 and self.cpu.z80.pc != 0x44:
            debug_print(f"INT HANDLER RETURNED TO: PC=0x{self.cpu.z80.pc:04X}, AF={self.cpu.z80.af:04X}, pins=0x{self.cpu.pins:016X}")
            debug_print(f"IFF1={self.cpu.z80.iff1}, IFF2={self.cpu.z80.iff2}, IM={self.cpu.z80.im}")
        
        # Track PC changes to see execution flow
        if hasattr(self, 'last_pc'):
            if self.last_pc != self.cpu.z80.pc:
                # Track the actual jump destination after interrupt
                if hasattr(self.cpu, 'in_interrupt_sequence') and self.cpu.in_interrupt_sequence:
                    debug_print(f"IM2: CPU jumped to 0x{self.cpu.z80.pc:04X} after interrupt")
                    delattr(self.cpu, 'in_interrupt_sequence')  # Clear the flag
                    
                # Define known loop addresses
                loop_addresses = {0x010A, 0x010B, 0x010C}
                
                # Check if we're in the main loop
                if self.cpu.z80.pc in loop_addresses:
                    # Only report entering the loop once
                    if not hasattr(self, 'in_main_loop') or not self.in_main_loop:
                        debug_print(f"PC is in main loop between 0x010A and 0x010C")
                        self.in_main_loop = True
                else:
                    # Not in the main loop, print PC change
                    debug_print(f"PC changed: 0x{self.last_pc:04X} -> 0x{self.cpu.z80.pc:04X}")
                    self.in_main_loop = False
                    
        self.last_pc = self.cpu.z80.pc
        
        # Update position counters
        self.line_cycle += 1
        
        # Generate interrupts at the start of the frame
        if self.line == 0 and self.line_cycle == self.BORDER_T_STATES:
            # Generate CPU interrupt
            debug_print(f"ULA: Generating interrupt at line={self.line}, cycle={self.line_cycle}")
            debug_print(f"ULA: CPU state before interrupt: {self.cpu.get_state_summary()}")
            self.cpu.interrupt(True)
        elif self.line == 0 and self.line_cycle == self.BORDER_T_STATES + self.INTERRUPT_DURATION:
            # End of interrupt
            debug_print(f"ULA: Ending interrupt at line={self.line}, cycle={self.line_cycle}")
            debug_print(f"ULA: CPU state before ending interrupt: {self.cpu.get_state_summary()}")
            self.cpu.interrupt(False)
            
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
    
    def __init__(self, debug=False):
        # Set global debug flag
        global DEBUG_ENABLED
        DEBUG_ENABLED = debug
        
        # Initialize components
        self.crt = CRT()
        self.memory = Memory()
        
        # Create IO bus for device handling
        self.io_bus = IODeviceBus()
        
        # Create CPU with memory and IO bus
        self.cpu = CPU(self.memory, self.io_bus)
        
        # Create ULA and connect to the bus
        self.ula = ULA(self.memory, self.crt, self.cpu)
        
        # Add ULA to the IO bus with port mask 0x0001
        # This will make the ULA respond to port 0xFE
        self.io_bus.add_device(0x0001, self.ula)
        
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
                    # Process key press
                    scancode = event.key.keysym.scancode
                    # Handle special keys
                    if scancode == sdl2.SDL_SCANCODE_ESCAPE:
                        quit = True
                    # Handle border color changes with number keys
                    elif scancode >= sdl2.SDL_SCANCODE_0 and scancode <= sdl2.SDL_SCANCODE_7:
                        border_color = scancode - sdl2.SDL_SCANCODE_0
                        self.ula.set_border_color(border_color)
                    # Toggle keyboard debug mode with F1
                    elif scancode == sdl2.SDL_SCANCODE_F1:
                        self.ula.keyboard.toggle_debug_mode()
                    
                    # Pass key press to the keyboard handler
                    self.ula.keyboard.press(scancode)
                    
                elif event.type == sdl2.SDL_KEYUP:
                    # Pass key release to the keyboard handler
                    scancode = event.key.keysym.scancode
                    self.ula.keyboard.release(scancode)
            
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
        self.memory.load_from_file(filename, 0x4000, 6912)
        debug_print(f"Screen file loaded: {filename}")
            
    def load_rom(self, filename):
        """Load a ROM file into memory at address 0x0000"""
        self.memory.load_from_file(filename, 0x0000, 16384)  # 16KB ROM
        debug_print(f"ROM loaded: {filename}")
            
    def load_sna(self, filename):
        """Load a .sna snapshot file
        
        SNA Layout:
        Offset  Size  Description
        -----------------------------------
        0       1     byte   I
        1       8     word   HL',DE',BC',AF'
        9       10    word   HL,DE,BC,IY,IX
        19      1     byte   Interrupt (bit 2 contains IFF2, 1=EI/0=DI)
        20      1     byte   R
        21      4     words  AF,SP
        25      1     byte   IntMode (0=IM0/1=IM1/2=IM2)
        26      1     byte   BorderColor (0..7)
        27      49152 bytes  RAM dump 16384..65535
        """
        with open(filename, 'rb') as f:
            # Set PC first
            self.cpu.set_pc(0x0072)
            
            # Read data directly in the same order as the reference
            # I register
            i_reg = int.from_bytes(f.read(1), byteorder='little')
            self.cpu.set_register_i(i_reg)
            
            # Alternate register set (HL', DE', BC', AF')
            hl_alt = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('hl_alt', hl_alt)
            
            de_alt = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('de_alt', de_alt)
            
            bc_alt = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('bc_alt', bc_alt)
            
            af_alt = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('af_alt', af_alt)
            
            # Main register set (HL, DE, BC, IY, IX)
            hl = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('hl', hl)
            
            de = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('de', de)
            
            bc = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('bc', bc)
            
            iy = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('iy', iy)
            
            ix = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('ix', ix)
            
            # Interrupt flag
            interrupt_byte = int.from_bytes(f.read(1), byteorder='little')
            iff2 = (interrupt_byte & 0x04) != 0
            self.cpu.set_register_iff2(iff2)
            
            # IFF1 needs to be set as well for interrupts to work
            # In Z80, interrupts are enabled when IFF1 is set
            print(f"Setting interrupt flags: IFF2={iff2}, setting IFF1 to same value")
            self.cpu.z80.iff1 = iff2  # Set IFF1 to same value as IFF2
            
            # R register
            r_reg = int.from_bytes(f.read(1), byteorder='little')
            self.cpu.set_register_r(r_reg)
            
            # AF and SP
            af = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('af', af)
            
            sp = int.from_bytes(f.read(2), byteorder='little')
            self.cpu.set_register_pair('sp', sp)
            
            # Interrupt mode
            im = int.from_bytes(f.read(1), byteorder='little')
            self.cpu.set_register_im(im)
            
            # Border color
            border = int.from_bytes(f.read(1), byteorder='little') & 0x07
            self.ula.set_border_color(border)
            
            # Load RAM directly
            ram_data = f.read(49152)
            if len(ram_data) < 49152:
                raise RuntimeError(f"Invalid SNA file: not enough memory data")
            
            # Load into RAM
            self.memory.ram[0x4000:0x10000] = np.frombuffer(ram_data, dtype=np.uint8)
        debug_print(f"SNA file loaded: {filename}")


# -----------------------------------------------------------------------------
# Main: Initializes SDL, runs the system, and handles any exceptions
def main():
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        print(f"SDL_Init Error: {sdl2.SDL_GetError().decode()}", file=sys.stderr)
        return 1

    # Default debugging state
    debug_enabled = False    
    # Parse command line arguments
    rom_loaded = False
    
    # Process arguments that might affect system creation first
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-d" or arg == "--debug":
            debug_enabled = True
            args.pop(i)
        else:
            i += 1
    
    # Create system with proper debug setting
    system = System(debug=debug_enabled)
    
    # Track if we need to load files
    rom_file = None
    sna_file = None
    scr_files = []
    
    # Process command line arguments for loading files
    if len(args) > 0:
        for arg in args:
            if arg == "-h" or arg == "--help":
                print(f"Usage: {sys.argv[0]} [options] [filename...]")
                print("Options:")
                print("  -h, --help           Display command information")
                print("  -d, --debug          Enable debugging output")
                print("Available file formats:")
                print("  .scr                 Screen data (6912 bytes)")
                print("  .rom                 System ROM (16384 bytes)")
                print("  .sna                 Snapshot file (49179 bytes)")
                print("Default ROM '48.rom' will be loaded if no ROM specified.")
                return 0
            elif arg.endswith(".rom"):
                print(f"Found ROM file: {arg}")
                rom_file = arg
            elif arg.endswith(".sna"):
                print(f"Found SNA snapshot file: {arg}")
                sna_file = arg
            elif arg.endswith(".scr"):
                print(f"Found screen file: {arg}")
                scr_files.append(arg)
            else:
                print(f"Unknown file type: {arg}", file=sys.stderr)
    
    # Load ROM first (either specified or default)
    if rom_file:
        print(f"Loading ROM file: {rom_file}")
        system.load_rom(rom_file)
    else:
        print("Loading default ROM: 48.rom")
        system.load_rom("48.rom")
    
    # Then load snapshot if available
    if sna_file:
        print(f"Loading SNA snapshot file: {sna_file}")
        system.load_sna(sna_file)
    
    # Finally load any screen files
    for scr_file in scr_files:
        print(f"Loading screen file: {scr_file}")
        system.load_scr(scr_file)
    
    system.run()
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 