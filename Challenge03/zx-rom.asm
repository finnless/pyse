;; ZX ROM routines, callable from sdcc (assumes v1 calling convention).

;; Note: This ISN'T the same assembler syntax used by sjasmplus, it's a bit
;; of an oddball format used by sdcc's tooling.

        .globl  _init_stdio
        .globl  _putchar
        .globl  _beep
        .globl  _keyscan
        .globl  _inkey
        .globl  _waitkey
        .globl  _setpixel
        .globl  _pixeladdr

_init_stdio::
        ld      a,#2
        call    0x1601
        ret

_putchar::
        ld      a, l
        cp      #10
        jr      nz, pc_skip
        ld      a, #13
pc_skip:
        rst     0x10
        ret

_beep::
        jp     0x3b5

_keyscan::
        jp    0x028e          ; Fetch a key-value in DE.

_inkey::
        call    0x028e          ; Fetch a key-value in DE.
        jr      nz, ks_nokey
        call    0x031e          ; Test the key value
        jr      nc, ks_nokey
        dec     d               ; +FF to D for L made (bit 3 set).
        ld      e, a            ; Key-value to E for decoding.
        call    0x0333          ; Decode the key-value.
        ld      e, a            ; ASCII value to E.
        ld      d, #0           ; Set high byte of DE to 0.
        ret
ks_nokey:
        ld      de, #0xffff     ; No key pressed.
        ret

_waitkey::
        ld    b, h
        ld    c, l
        jp    0x1f3d

_setpixel::
        ld     b, l
        ld     c, a
        jp     0x22e5

_pixeladdr::
        ld     b, l
        ld     c, a
        ld     a, b
        call   0x22b0
        ex     de, hl
        ret