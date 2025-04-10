// z80_impl.c (or z80_wrapper.c linked with z80.h implementation)
//
// Compile with:
//    clang -O2 -dynamiclib -o libz80.dylib z80_impl.c

#define CHIPS_IMPL
// Optionally add your own assert if needed
// #define CHIPS_ASSERT(x) assert(x)
#include "z80.h" // Assuming the actual .h file now

// Include the implementation first if this is the same file
// #ifdef CHIPS_IMPL
// ... (original implementation goes here) ...
// #endif // CHIPS_IMPL


// --- Helper Accessor Functions ---

// Make sure z80_t is defined before these helpers

uint16_t z80_get_pc(z80_t* cpu) { return cpu->pc; }
uint16_t z80_get_sp(z80_t* cpu) { return cpu->sp; }
uint16_t z80_get_af(z80_t* cpu) { return cpu->af; }
uint16_t z80_get_bc(z80_t* cpu) { return cpu->bc; }
uint16_t z80_get_de(z80_t* cpu) { return cpu->de; }
uint16_t z80_get_hl(z80_t* cpu) { return cpu->hl; }
uint16_t z80_get_ix(z80_t* cpu) { return cpu->ix; }
uint16_t z80_get_iy(z80_t* cpu) { return cpu->iy; }
uint16_t z80_get_wz(z80_t* cpu) { return cpu->wz; } // Might be useful for debug

uint16_t z80_get_af_prime(z80_t* cpu) { return cpu->af2; }
uint16_t z80_get_bc_prime(z80_t* cpu) { return cpu->bc2; }
uint16_t z80_get_de_prime(z80_t* cpu) { return cpu->de2; }
uint16_t z80_get_hl_prime(z80_t* cpu) { return cpu->hl2; }

uint8_t z80_get_i(z80_t* cpu) { return cpu->i; }
uint8_t z80_get_r(z80_t* cpu) { return cpu->r; }
uint8_t z80_get_im(z80_t* cpu) { return cpu->im; }
bool z80_get_iff1(z80_t* cpu) { return cpu->iff1; }
bool z80_get_iff2(z80_t* cpu) { return cpu->iff2; }

// Optional: Setters if needed for testing/setup
void z80_set_pc(z80_t* cpu, uint16_t val) { cpu->pc = val; }
void z80_set_sp(z80_t* cpu, uint16_t val) { cpu->sp = val; }

// Add the missing setters for registers
void z80_set_af(z80_t* cpu, uint16_t val) { cpu->af = val; }
void z80_set_bc(z80_t* cpu, uint16_t val) { cpu->bc = val; }
void z80_set_de(z80_t* cpu, uint16_t val) { cpu->de = val; }
void z80_set_hl(z80_t* cpu, uint16_t val) { cpu->hl = val; }
void z80_set_ix(z80_t* cpu, uint16_t val) { cpu->ix = val; }
void z80_set_iy(z80_t* cpu, uint16_t val) { cpu->iy = val; }

void z80_set_af_prime(z80_t* cpu, uint16_t val) { cpu->af2 = val; }
void z80_set_bc_prime(z80_t* cpu, uint16_t val) { cpu->bc2 = val; }
void z80_set_de_prime(z80_t* cpu, uint16_t val) { cpu->de2 = val; }
void z80_set_hl_prime(z80_t* cpu, uint16_t val) { cpu->hl2 = val; }

void z80_set_i(z80_t* cpu, uint8_t val) { cpu->i = val; }
void z80_set_r(z80_t* cpu, uint8_t val) { cpu->r = val; }
void z80_set_im(z80_t* cpu, uint8_t val) { cpu->im = val; }
void z80_set_iff1(z80_t* cpu, bool val) { cpu->iff1 = val; }
void z80_set_iff2(z80_t* cpu, bool val) { cpu->iff2 = val; }

// Legacy function - can be used if the above individual setters are not available
void z80_set_reg16(z80_t* cpu, int reg_id, uint16_t val) {
    // Could use an enum/defines for reg_id (0=AF, 1=BC, etc.)
    switch(reg_id) {
        case 0: cpu->af = val; break; // AF
        case 1: cpu->bc = val; break; // BC
        // ... etc ...
        case 8: cpu->sp = val; break; // SP
    }
}

// Function to return the size of the z80_t struct
size_t z80_get_state_size(void) {
    return sizeof(z80_t);
}
