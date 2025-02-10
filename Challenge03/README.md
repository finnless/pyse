# Challenge 03

We could implement [Conway's Game of Life](https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life) on the ZX Spectrum.

This may be a Rust implementation: https://github.com/zademn/game-of-life-rust/
This may be a Z80 ASM implementation: https://github.com/rand0musername/cgol-asm/

This guide provides good tooling for writing Z80 ASM and compiling for ZX spectrum:
https://benjamin.computer/posts/2022-04-22-ZX-coding.html

Primarily [pasmo](https://pasmo.speccy.org/) and [bin2tap](https://sourceforge.net/p/zxspectrumutils/wiki/bin2tap/) which I tested and are working (on x86). I tested using this repo: https://github.com/OniDaito/speccy


It continues with an explination for graphics:
https://benjamin.computer/posts/2022-06-08-youwouldnt.html

Seconds per step with current code:
10-17