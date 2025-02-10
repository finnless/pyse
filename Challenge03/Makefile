REQUIRED = crt0.rel zx-rom.rel
SDCC = sdcc --code-loc 0x8000  --data-loc 0xC000

C_TARGETS = cgol.tap
BASIC_TARGETS = generic-loader.tap
LOADERS = cgol-load.tap

all: $(REQUIRED) $(C_TARGETS) $(BASIC_TARGETS) $(LOADERS)

cgol.ihx: cgol.c zx-rom.rel crt0.rel
	SDCC_LIB="." $(SDCC) -mz80 $< zx-rom.rel

generic-loader.tap: generic-loader.bas
	speccy-basic --tap $@ $< --tap-line 10 --tap-name loader

cgol-load.tap: generic-loader.tap cgol.tap
	cat $^ > $@

# Generate TAP file from ihx file
%.tap: %.ihx
	ihex2tap -o $@ $<

.PHONY: all clean cleanish
cleanish:
	rm -f *.rel *.ihx *.lk *.lst *.map *.noi *.sym
clean:
	rm -f *.rel *.ihx *.lk *.lst *.map *.noi *.sym *.tap $(C_TARGETS:.tap=.asm)

# You probably don't want to change these files, but they need to be built

AS=sdasz80 
ASFLAGS=-plosgff

zx-rom.rel: zx-rom.asm
	$(AS) $(ASFLAGS) -o $@ $<

crt0.rel: crt0.asm
	$(AS) $(ASFLAGS) -o $@ $<
