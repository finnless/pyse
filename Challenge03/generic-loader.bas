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
LET ignored = USR Address

