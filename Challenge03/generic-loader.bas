' - ZX CGOL -... a very original game for HMC CS181AR by
' Henry Merrilees
' Nolan Windham
' This is a generic loader for the programs compiled with SDCC.
'
' In ZX Spectrum BASIC, the `CLEAR` command can set the maximum address
' that BASIC is allowed to use. So `CLEAR 32767` will allow us to use
' addresses from 32768..65535 for our own purposes, such as machine code
' or special data.
'

GOTO @go
@setAddress:
LET Address = 32768:RETURN
@go:
GOSUB @setAddress: CLEAR (Address-1): GOSUB @setAddress
PRINT #0; "Loading machine code at "; Address
LOAD "" CODE
INPUT "": PRINT #0; "Loaded. Press a key to run...";
PAUSE 0

' DISABLE SCROLL
POKE 23692,255

' SPLASH SCREEN - THX-inspired Deep Note
BORDER 1: PAPER 6: INK 2: CLS

' Start with chaos
FOR x = -50 TO 0
    BEEP 0.01, x/2*1
    BEEP 0.01, -x/3*1
    BEEP 0.01, x/4*1
    
    PLOT 128, 150
    DRAW x*2,-120
NEXT x

' Converge to D major chord
FOR x = 0 TO 50
    BEEP 0.01, (x/2) * (-22/50)
    BEEP 0.01, (-x/3) * (-17/50)
    BEEP 0.01, (x/4) * (-15/50)
    
    PLOT 128, 150
    DRAW x*2,-120
NEXT x

PAPER 8: INK 1: BRIGHT 0

PRINT AT 11, 10; "- ZX CGOL -"
PRINT AT 13, 15; "by"
PRINT AT 14, 8; "Henry and Nolan"


' Sustain final chord
FOR y = 1 TO 25
    LET x = 53
    BEEP 0.01, (x/2) * (-22/50)
    BEEP 0.01, (-x/3) * (-17/50)
    BEEP 0.01, (x/4) * (-15/50)
    BEEP 0.01, (-x/3) * (-17/50) - 12
    POKE 23692,255
    POKE 23692,255
NEXT y

PAUSE 100

' DEFAULT BACKGROUND
BORDER 0: BRIGHT 0: PAPER 0: INK 7: CLS

LET ignored = USR Address

