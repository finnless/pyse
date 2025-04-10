import ctypes
import os
import sys

# Import the auto-generated constants and setup function
try:
    from _z80_bindings import * # Import all constants, helpers, z80_t class
except ImportError:
    print("Error: Could not import generated bindings from _z80_bindings.py")
    print("Please run 'python generate_bindings.py' first.")
    sys.exit(1)

# --- Load the shared library ---
lib_path = None
if sys.platform == 'win32':
    lib_path = os.path.join('.', 'z80.dll')
elif sys.platform == 'darwin':
    lib_path = os.path.join('.', 'libz80.dylib')
else: # Linux etc
    lib_path = os.path.join('.', 'libz80.so')

if not os.path.exists(lib_path):
    raise ImportError(f"Cannot find compiled Z80 library at {lib_path}")

try:
    z80_lib = ctypes.CDLL(lib_path)
except OSError as e:
     raise OSError(f"Error loading library {lib_path}: {e}")

# --- Setup function prototypes using the generated function ---
setup_prototypes(z80_lib)

# --- The Nice Python Class Wrapper (Now Simpler!) ---
class Z80:
    def __init__(self):
        # 1. Get the required size from the C library
        struct_size = z80_lib.z80_get_state_size()
        if struct_size == 0:
             raise RuntimeError("C library reported z80_t size as 0!")

        # 2. Allocate a raw buffer of the correct size
        #    We use a byte buffer which ctypes can manage.
        self._cpu_state_buffer = ctypes.create_string_buffer(struct_size)

        # 3. Get a pointer to this buffer, properly cast for C functions
        #    We store the pointer for convenience, but the buffer itself keeps memory alive.
        self._cpu_state_ptr = ctypes.cast(self._cpu_state_buffer, ctypes.POINTER(z80_t))

        # 4. Call the C init function, passing the correctly typed pointer
        self.pins = z80_lib.z80_init(self._cpu_state_ptr)

    # Use this internally whenever you need to pass the state to C
    @property
    def _state_ptr(self):
        # Optional: Add checks? Maybe not needed if init succeeded.
        return self._cpu_state_ptr

    
    
    def reset(self):
        self.pins = z80_lib.z80_reset(self._state_ptr)

    def tick(self, pins_in=None):
        """Performs one Z80 clock cycle."""
        current_pins = pins_in if pins_in is not None else self.pins
        self.pins = z80_lib.z80_tick(self._state_ptr, current_pins)
        return self.pins

    def prefetch(self, new_pc):
        """Forces the CPU to start fetching instructions from new_pc."""
        self.pins = z80_lib.z80_prefetch(self._state_ptr, new_pc)
        # Alternatively, if you add z80_set_pc:
        # z80_lib.z80_set_pc(self._state_ptr, new_pc)
        # self.pins = z80_lib.z80_prefetch(self._state_ptr, new_pc) # Still might need prefetch logic
        return self.pins

    def is_opdone(self):
        """Checks if the last instruction has completed."""
        return z80_lib.z80_opdone(self._state_ptr)

    # --- Pin Access ---
    # Use the generated helper functions directly
    @property
    def addr(self):
        return Z80_GET_ADDR(self.pins)

    @property
    def data(self):
        return Z80_GET_DATA(self.pins)

    def set_data(self, data_val):
        self.pins = Z80_SET_DATA(self.pins, data_val)

    def set_pins(self, mask):
        """Sets specific pin bits high."""
        self.pins |= mask

    def clear_pins(self, mask):
        """Sets specific pin bits low."""
        self.pins &= ~mask

    def test_pins(self, mask):
        """Checks if ALL pins in the mask are set."""
        return (self.pins & mask) == mask

    # Use generated constants for checks
    def is_mreq(self): return bool(self.pins & Z80_MREQ)
    def is_iorq(self): return bool(self.pins & Z80_IORQ)
    def is_rd(self):   return bool(self.pins & Z80_RD)
    def is_wr(self):   return bool(self.pins & Z80_WR)
    def is_m1(self):   return bool(self.pins & Z80_M1)
    def is_halt(self): return bool(self.pins & Z80_HALT)
    def is_rfsh(self): return bool(self.pins & Z80_RFSH)
    # Add more pin checks as needed...

    # --- Register Access (using C helpers) ---
    @property
    def pc(self): return z80_lib.z80_get_pc(self._state_ptr)
    @pc.setter
    def pc(self, value): z80_lib.z80_set_pc(self._state_ptr, value)
    
    @property
    def sp(self): return z80_lib.z80_get_sp(self._state_ptr)
    @sp.setter
    def sp(self, value): z80_lib.z80_set_sp(self._state_ptr, value)
    
    @property
    def af(self): return z80_lib.z80_get_af(self._state_ptr)
    @af.setter
    def af(self, value): z80_lib.z80_set_af(self._state_ptr, value)
    
    @property
    def bc(self): return z80_lib.z80_get_bc(self._state_ptr)
    @bc.setter
    def bc(self, value): z80_lib.z80_set_bc(self._state_ptr, value)
    
    @property
    def de(self): return z80_lib.z80_get_de(self._state_ptr)
    @de.setter
    def de(self, value): z80_lib.z80_set_de(self._state_ptr, value)
    
    @property
    def hl(self): return z80_lib.z80_get_hl(self._state_ptr)
    @hl.setter
    def hl(self, value): z80_lib.z80_set_hl(self._state_ptr, value)
    
    @property
    def ix(self): return z80_lib.z80_get_ix(self._state_ptr)
    @ix.setter
    def ix(self, value): z80_lib.z80_set_ix(self._state_ptr, value)
    
    @property
    def iy(self): return z80_lib.z80_get_iy(self._state_ptr)
    @iy.setter
    def iy(self, value): z80_lib.z80_set_iy(self._state_ptr, value)
    
    @property
    def af_prime(self): return z80_lib.z80_get_af_prime(self._state_ptr)
    @af_prime.setter
    def af_prime(self, value): z80_lib.z80_set_af_prime(self._state_ptr, value)
    
    @property
    def bc_prime(self): return z80_lib.z80_get_bc_prime(self._state_ptr)
    @bc_prime.setter
    def bc_prime(self, value): z80_lib.z80_set_bc_prime(self._state_ptr, value)
    
    @property
    def de_prime(self): return z80_lib.z80_get_de_prime(self._state_ptr)
    @de_prime.setter
    def de_prime(self, value): z80_lib.z80_set_de_prime(self._state_ptr, value)
    
    @property
    def hl_prime(self): return z80_lib.z80_get_hl_prime(self._state_ptr)
    @hl_prime.setter
    def hl_prime(self, value): z80_lib.z80_set_hl_prime(self._state_ptr, value)
    
    @property
    def i(self): return z80_lib.z80_get_i(self._state_ptr)
    @i.setter
    def i(self, value): z80_lib.z80_set_i(self._state_ptr, value)
    
    @property
    def r(self): return z80_lib.z80_get_r(self._state_ptr)
    @r.setter
    def r(self, value): z80_lib.z80_set_r(self._state_ptr, value)
    
    @property
    def im(self): return z80_lib.z80_get_im(self._state_ptr)
    @im.setter
    def im(self, value): z80_lib.z80_set_im(self._state_ptr, value)
    
    @property
    def iff1(self): return z80_lib.z80_get_iff1(self._state_ptr)
    @iff1.setter
    def iff1(self, value): z80_lib.z80_set_iff1(self._state_ptr, value)
    
    @property
    def iff2(self): return z80_lib.z80_get_iff2(self._state_ptr)
    @iff2.setter
    def iff2(self, value): z80_lib.z80_set_iff2(self._state_ptr, value)
    
    @property
    def wz(self): return z80_lib.z80_get_wz(self._state_ptr) # If needed

    # Convenience accessors for flags (derived from AF)
    @property
    def f(self): return self.af & 0xFF
    @property
    def sf(self): return bool(self.f & Z80_SF)
    @property
    def zf(self): return bool(self.f & Z80_ZF)
    @property
    def yf(self): return bool(self.f & Z80_YF) # Undocumented bit 5
    @property
    def hf(self): return bool(self.f & Z80_HF)
    @property
    def xf(self): return bool(self.f & Z80_XF) # Undocumented bit 3
    @property
    def pf(self): return bool(self.f & Z80_PF) # Parity/Overflow
    @property
    def vf(self): return bool(self.f & Z80_VF) # Alias for PF
    @property
    def nf(self): return bool(self.f & Z80_NF)
    @property
    def cf(self): return bool(self.f & Z80_CF)

    # Optional: Add setters using C helpers if defined
    # def set_pc(self, value): z80_lib.z80_set_pc(self._state_ptr, value)
    # def set_sp(self, value): z80_lib.z80_set_sp(self._state_ptr, value)

    def state_dict(self):
        """Returns a dictionary representing the current CPU state."""
        return {
            "PC": f"{self.pc:04X}", "SP": f"{self.sp:04X}",
            "AF": f"{self.af:04X}", "BC": f"{self.bc:04X}",
            "DE": f"{self.de:04X}", "HL": f"{self.hl:04X}",
            "IX": f"{self.ix:04X}", "IY": f"{self.iy:04X}",
            "AF'": f"{self.af_prime:04X}", "BC'": f"{self.bc_prime:04X}",
            "DE'": f"{self.de_prime:04X}", "HL'": f"{self.hl_prime:04X}",
            "I": f"{self.i:02X}", "R": f"{self.r:02X}", "IM": self.im,
            "IFF1": self.iff1, "IFF2": self.iff2,
            "WZ": f"{self.wz:04X}", # If wz helper exists
            "Flags": f"{'S' if self.sf else '-'}{'Z' if self.zf else '-'}{'Y' if self.yf else '-'}{'H' if self.hf else '-'}{'X' if self.xf else '-'}{'P' if self.pf else '-'}{'N' if self.nf else '-'}{'C' if self.cf else '-'}" ,
            "Pins": f"0x{self.pins:0{16}X}" # Show full pin state
        }

    def __str__(self):
        """String representation of the CPU state."""
        state = self.state_dict()
        return (f"PC:{state['PC']} SP:{state['SP']} AF:{state['AF']} BC:{state['BC']} DE:{state['DE']} HL:{state['HL']} "
                f"IX:{state['IX']} IY:{state['IY']} I:{state['I']} R:{state['R']} IM:{state['IM']} "
                f"Flags:{state['Flags']} IFF1:{state['IFF1']} IFF2:{state['IFF2']}")


# --- Example Usage (mostly unchanged, but now more robust) ---
if __name__ == "__main__":
    print("Initializing Z80...")
    cpu = Z80()
    memory = bytearray(65536) # 64K RAM filled with NOPs (0x00)

    # Example: Load a simple program (LD A, 0x42; HALT)
    memory[0x0000] = 0x3E # LD A, n
    memory[0x0001] = 0x42 # value 0x42
    memory[0x0002] = 0x76 # HALT

    print(f"Starting emulation loop...")
    print(f"Initial state: {cpu}")
    pins = cpu.pins # Get initial pins

    halted = False
    max_ticks = 1000
    try:
        for i in range(max_ticks):
            # --- CPU Tick ---
            # Set pins high *before* tick if needed (e.g. WAIT, INT, NMI)
            # Example: cpu.set_pins(Z80_INT)
            pins = cpu.tick(pins)

            # --- Peripheral/Memory Handling ---
            if cpu.is_mreq():
                addr = cpu.addr
                if cpu.is_rd():
                    data = memory[addr]
                    # print(f"Tick {i}: MREQ|RD Addr: {addr:04X} Data: {data:02X}")
                    pins = Z80_SET_DATA(pins, data) # Put data on bus for *next* tick
                elif cpu.is_wr():
                    data = cpu.data # Use property getter
                    # print(f"Tick {i}: MREQ|WR Addr: {addr:04X} Data: {data:02X}")
                    memory[addr] = data
            elif cpu.is_iorq():
                addr = cpu.addr
                if cpu.is_m1(): # Interrupt Acknowledge
                    print(f"Tick {i}: Interrupt Acknowledge! (Addr: {addr:04X})")
                    pins = Z80_SET_DATA(pins, 0xFF) # Respond with RST 38h
                elif cpu.is_rd():
                     # print(f"Tick {i}: IO RD Addr: {addr:04X}")
                     pins = Z80_SET_DATA(pins, 0x00) # Read 0 from any port
                elif cpu.is_wr():
                     data = cpu.data
                     print(f"Tick {i}: IO WR Addr: {addr:04X} Data: {data:02X}")
                     # Handle IO write (e.g., print to console)

            # --- Check CPU State ---
            if cpu.is_halt():
                print(f"Tick {i}: CPU Halted.")
                halted = True
                break # Stop simulation on HALT

            # --- Post-Tick Pin Handling ---
            # Clear pins that should only be active for one cycle externally?
            # Example: pins = cpu.clear_pins(Z80_INT) # If INT was asserted externally
            # The Z80 core itself drives MREQ, RD, WR etc. so don't clear those.

            # Optional: Print state every op
            # if cpu.is_opdone():
            #    print(f"Tick {i}: Op Done. {cpu}")

        print(f"Emulation finished after {i+1} ticks.")
        if not halted and i == max_ticks - 1:
            print("Warning: Reached max ticks limit.")

    except KeyboardInterrupt:
        print("\nEmulation stopped by user.")

    print(f"Final CPU state:")
    print(cpu)
    print(f"Value at 0x0010 in RAM: {memory[0x0010]:02X}") # Example memory inspection
    af_reg = cpu.af
    print(f"Register A: {(af_reg >> 8):02X}")
