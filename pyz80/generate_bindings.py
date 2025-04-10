import re
import sys
import os

# --- Configuration ---
HEADER_FILE = 'z80.h'  # Path to the Z80 header file
OUTPUT_FILE = '_z80_bindings.py'
LIB_FUNCTIONS = [ # List C functions to create prototypes for
    # Original functions
    "uint64_t z80_init(z80_t* cpu)",
    "uint64_t z80_reset(z80_t* cpu)",
    "uint64_t z80_tick(z80_t* cpu, uint64_t pins)",
    "uint64_t z80_prefetch(z80_t* cpu, uint16_t new_pc)",
    "bool z80_opdone(z80_t* cpu)",
    # Added Helper functions (copy signatures exactly from C)
    "uint16_t z80_get_pc(z80_t* cpu)",
    "uint16_t z80_get_sp(z80_t* cpu)",
    "uint16_t z80_get_af(z80_t* cpu)",
    "uint16_t z80_get_bc(z80_t* cpu)",
    "uint16_t z80_get_de(z80_t* cpu)",
    "uint16_t z80_get_hl(z80_t* cpu)",
    "uint16_t z80_get_ix(z80_t* cpu)",
    "uint16_t z80_get_iy(z80_t* cpu)",
    "uint16_t z80_get_wz(z80_t* cpu)",
    "uint16_t z80_get_af_prime(z80_t* cpu)",
    "uint16_t z80_get_bc_prime(z80_t* cpu)",
    "uint16_t z80_get_de_prime(z80_t* cpu)",
    "uint16_t z80_get_hl_prime(z80_t* cpu)",
    "uint8_t z80_get_i(z80_t* cpu)",
    "uint8_t z80_get_r(z80_t* cpu)",
    "uint8_t z80_get_im(z80_t* cpu)",
    "bool z80_get_iff1(z80_t* cpu)",
    "bool z80_get_iff2(z80_t* cpu)",
    # Add setters for all registers
    "void z80_set_pc(z80_t* cpu, uint16_t val)",
    "void z80_set_sp(z80_t* cpu, uint16_t val)",
    "void z80_set_af(z80_t* cpu, uint16_t val)",
    "void z80_set_bc(z80_t* cpu, uint16_t val)",
    "void z80_set_de(z80_t* cpu, uint16_t val)",
    "void z80_set_hl(z80_t* cpu, uint16_t val)",
    "void z80_set_ix(z80_t* cpu, uint16_t val)",
    "void z80_set_iy(z80_t* cpu, uint16_t val)",
    "void z80_set_af_prime(z80_t* cpu, uint16_t val)",
    "void z80_set_bc_prime(z80_t* cpu, uint16_t val)",
    "void z80_set_de_prime(z80_t* cpu, uint16_t val)",
    "void z80_set_hl_prime(z80_t* cpu, uint16_t val)",
    "void z80_set_i(z80_t* cpu, uint8_t val)",
    "void z80_set_r(z80_t* cpu, uint8_t val)",
    "void z80_set_im(z80_t* cpu, uint8_t val)",
    "void z80_set_iff1(z80_t* cpu, bool val)",
    "void z80_set_iff2(z80_t* cpu, bool val)",
    # Size function
    "size_t z80_get_state_size(void)",
]

# --- Regex Patterns ---
# #define Z80_PIN_xxx (number)
PIN_DEF_RE = re.compile(r'#define\s+(Z80_PIN_\w+)\s+\(?(\d+)\)?')
# #define Z80_xxx (1ULL << Z80_PIN_yyy) or (1 << Z80_PIN_yyy)
MASK_DEF_RE = re.compile(r'#define\s+(Z80_\w+)\s+\(?\(1(ULL)?\s*<<\s*(\w+)\)\)?')
# #define Z80_xxx (FlagVal)  e.g. #define Z80_CF (1<<0)
FLAG_DEF_RE = re.compile(r'#define\s+(Z80_[CNPVHXZS]F)\s+\(?(\(1<<\d+\)|0x[0-9a-fA-F]+)\)?')
# #define Z80_PF Z80_VF
ALIAS_DEF_RE = re.compile(r'#define\s+(Z80_\w+)\s+(Z80_\w+)')
# Simple value defines like #define Z80_CTRL_PIN_MASK (...)
SIMPLE_VAL_RE = re.compile(r'#define\s+(Z80_\w+)\s+\(?(.*?)\)?\s*$') # Less specific

# C type to ctypes mapping
CTYPES_MAP = {
    'uint64_t': 'ctypes.c_uint64',
    'uint32_t': 'ctypes.c_uint32',
    'uint16_t': 'ctypes.c_uint16',
    'uint8_t': 'ctypes.c_uint8',
    'int64_t': 'ctypes.c_int64',
    'int32_t': 'ctypes.c_int32',
    'int16_t': 'ctypes.c_int16',
    'int8_t': 'ctypes.c_int8',
    'int': 'ctypes.c_int',
    'bool': 'ctypes.c_bool',
    'void': 'None',
    'size_t': 'ctypes.c_size_t',
    # Pointers
    'z80_t*': 'ctypes.POINTER(z80_t)',
    # Add other types if needed
}

# --- Helper Functions ---
def parse_c_expr(expr):
    """Rudimentary C expression to Python translator for defines."""
    expr = expr.replace('ULL', '')
    expr = expr.replace('ULL', '')
    expr = expr.replace('|', ' | ')
    # Add more replacements if needed (e.g., for specific defines used in expressions)
    return expr.strip()

def parse_func_signature(sig_str):
    """Parses C function signature to get name, restype, argtypes."""
    match = re.match(r'([\w\s\*]+?)\s+(\w+)\s*\((.*)\)', sig_str.strip())
    if not match:
        print(f"Warning: Could not parse function signature: {sig_str}", file=sys.stderr)
        return None, None, []

    return_type_str, func_name, args_str = match.groups()
    return_type_str = return_type_str.strip()

    arg_types = []
    if args_str.strip() and args_str.strip() != 'void':
        args = [a.strip() for a in args_str.split(',')]
        for arg in args:
            # Split argument type and name (optional)
            parts = arg.split()
            arg_type_str = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
            # Handle pointers specifically
            if arg_type_str.endswith('*'):
                 arg_type_str = arg_type_str.replace(' ','') # Remove space like 'z80_t *' -> 'z80_t*'

            arg_types.append(arg_type_str)

    return func_name, return_type_str, arg_types

# --- Main Generation Logic ---
def generate_bindings():
    print(f"Parsing {HEADER_FILE}...")
    try:
        with open(HEADER_FILE, 'r') as f:
            header_content = f.read()
    except FileNotFoundError:
        print(f"Error: Header file '{HEADER_FILE}' not found.", file=sys.stderr)
        sys.exit(1)

    py_code = [
        "# -*- coding: utf-8 -*-",
        "# Auto-generated by generate_bindings.py. DO NOT EDIT.",
        "import ctypes",
        "",
        "# --- Define z80_t as an opaque structure ---",
        "# We don't need its internal layout in Python anymore",
        "class z80_t(ctypes.Structure):",
        "    pass # Opaque structure",
        "",
        "# --- Constants from header ---",
    ]

    constants = {}
    aliases = {}

    for line in header_content.splitlines():
        line = line.strip()

        # Pin definitions
        m = PIN_DEF_RE.match(line)
        if m:
            name, value = m.groups()
            constants[name] = int(value)
            py_code.append(f"{name} = {value}")
            continue

        # Pin masks
        m = MASK_DEF_RE.match(line)
        if m:
            name, _, pin_name = m.groups()
            constants[name] = f"(1 << {pin_name})" # Store expression
            py_code.append(f"{name} = {constants[name]}")
            continue

        # Flags
        m = FLAG_DEF_RE.match(line)
        if m:
            name, value_expr = m.groups()
            value = eval(value_expr) # Evaluate simple (1<<n)
            constants[name] = value
            py_code.append(f"{name} = {value} # {value_expr}")
            continue

        # Aliases
        m = ALIAS_DEF_RE.match(line)
        if m:
            alias, original = m.groups()
            aliases[alias] = original
            py_code.append(f"{alias} = {original}")
            continue

        # Other simple value defines (attempt)
        m = SIMPLE_VAL_RE.match(line)
        if m:
            name, expr = m.groups()
            # Avoid redefining things we already parsed more specifically
            if name not in constants and name not in aliases:
                try:
                    # Try to evaluate if it looks simple, otherwise store string
                    py_expr = parse_c_expr(expr)
                    # Evaluate in a context with already defined constants
                    eval_context = {k: (eval(v) if isinstance(v, str) else v) for k, v in constants.items()}
                    value = eval(py_expr, eval_context)
                    constants[name] = value
                    py_code.append(f"{name} = {value} # Parsed from: {expr}")
                except Exception:
                     # Store as string if evaluation fails (might be complex)
                     constants[name] = py_expr # Store the expression string
                     py_code.append(f"# WARNING: Could not evaluate: {name} = {py_expr}")
                     py_code.append(f"{name} = \"{py_expr}\" # C EXPR: {expr}")


    py_code.extend([
        "",
        "# --- Pin Access Helper Functions (translated from C macros) ---",
        "def Z80_MAKE_PINS(ctrl, addr, data):",
        "    return ctrl | ((data & 0xFF) << Z80_PIN_D0) | (addr & 0xFFFF)",
        "",
        "def Z80_GET_ADDR(p):",
        "    return p & 0xFFFF",
        "",
        "def Z80_SET_ADDR(p, a):",
        "    return (p & ~0xFFFF) | (a & 0xFFFF)",
        "",
        "def Z80_GET_DATA(p):",
        f"    return (p >> Z80_PIN_D0) & 0xFF", # Use defined pin offset
        "",
        "def Z80_SET_DATA(p, d):",
        f"    return (p & ~(0xFF << Z80_PIN_D0)) | ((d & 0xFF) << Z80_PIN_D0)",
        "",
        "# --- Library Function Prototypes ---",
        "def setup_prototypes(lib):",
        "    \"\"\"Sets up ctypes function prototypes on the loaded library object.\"\"\"",
        "    # z80_t structure needed for pointer types",
        "    global z80_t" # Allow modification if needed, though unlikely
    ])

    for func_sig in LIB_FUNCTIONS:
        func_name, ret_type, arg_types_str = parse_func_signature(func_sig)
        if func_name is None:
            continue

        try:
            py_ret_type = CTYPES_MAP[ret_type]
            py_arg_types = [CTYPES_MAP[arg] for arg in arg_types_str]
        except KeyError as e:
            print(f"Warning: Unknown C type '{e}' in function '{func_name}'. Skipping.", file=sys.stderr)
            continue

        py_code.append(f"    lib.{func_name}.argtypes = [{', '.join(py_arg_types)}]")
        py_code.append(f"    lib.{func_name}.restype = {py_ret_type}")
        py_code.append("") # Add newline for readability

    # --- Write Output File ---
    try:
        with open(OUTPUT_FILE, 'w') as f:
            f.write('\n'.join(py_code))
        print(f"Successfully generated bindings file: {OUTPUT_FILE}")
    except IOError as e:
        print(f"Error writing output file '{OUTPUT_FILE}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    generate_bindings()
