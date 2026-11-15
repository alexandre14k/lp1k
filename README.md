# lp1k
Synth, pack and flash tool for the iCEblink40-LP1K (iCE40-LP1K-QN84). <br>
Python script in, bitstream out, flashed over Digilent Adept USB.

## Status

The iCEblink40-LP1K is an obsolete board. This project is an attempt
to revive it: open toolchain, no vendor software, Linux only.

- Synth -- yosys and nextpnr replace iCEcube2
- Pack -- built-in packer replaces the vendor bitstream tool
- Flash -- built-in Adept protocol replaces the vendor programmer

## Requirements

- Linux
- python3
- yosys
- nextpnr-ice40

```bash
sudo apt install yosys nextpnr-ice40
```

## Run

```bash
./run_linux.sh
```

First use: press `u` to install the udev rule, then replug the board.

## Navigation

Type a key at the prompt, press Enter.

- `l` -- list scenarios in `src/script/`
- `s` -- synth scenario: pick one, build `out/<name>.bin`
- `c` -- connect: scan USB, pick a device (disconnected only)
- `u` -- udev: install the USB access rule, needs sudo
- `k` -- clear screen
- `m` -- show menu
- `x` -- exit

Shown only when connected:

- `d` -- disconnect: release the USB device
- `f` -- flash: pick a bin from `out/`, confirm, erase, write, verify
- `r` -- reset: reset the USB device, then connect again
- `p` -- deep sleep: flash power-down, FPGA held in reset
- `e` -- exit sleep: wake the flash, release the FPGA

Prompts:

- `choice>` -- enter an index, empty input skips
- `[y/N]>` -- `y` or `yes` confirms, anything else aborts
- Up/down -- recall previous input

## Hardware

iCEblink40-LP1K evalkit (Lattice board, Digilent USB controller).

- FPGA -- iCE40-LP1K, QN84 package, runs the user design
- SPI flash -- 1 Mbit (128 KB) configuration PROM, holds the bitstream
- USB controller -- Digilent Adept 2, USB id 1443:0007
- Adept SPI -- the path this tool uses to erase, write, verify flash
- Adept GPIO -- holds the FPGA in reset while flash is accessed
- Adept power -- board is powered over the same USB cable
- Clock -- 3.33 MHz oscillator on pin A9, drives the design
- User LEDs -- LD1 on A29, LD2 on B20, active high
- Power-good LED -- LD5 by the USB connector, lit when powered
- Touch buttons -- four capacitive pads, free for user designs
- Expansion I/O -- 63 user pins at 3.3 V for external modules

Boot path:

1. Power up or release from reset
2. FPGA reads the bitstream from the SPI flash
3. Design runs

This tool never loads the FPGA directly. It writes the flash, then
the board must be power-cycled or released from reset to boot it.

## Flow

1. Scenario `.py` is parsed into `.v` and `.pcf`
2. yosys: `.v` to `.json`
3. nextpnr: `.json` and `.pcf` to `.asc`
4. packer: `.asc` to `.bin` in `out/`

Then `c`, `f`, power-cycle the board to boot the image.

## Scenario format

File in `src/script/`, extension `.py`.

- `# pinout` -- header, lines below as `# PORT -- PIN`
- `# logic` -- header, free notes
- Module docstring -- the Verilog source

```python
# pinout
# CLK -- A9
# LD1 -- A29

"""
module top (input wire CLK, output reg LD1);
endmodule
"""
```

## Layout

- `src/main.py` -- menu and dispatch
- `src/app/scenario.py` -- script parser
- `src/app/flow.py` -- synth pipeline
- `src/app/packer/tool.py` -- `.asc` to `.bin`
- `src/app/session.py` -- connect, flash, sleep
- `src/app/adept.py` -- Adept protocol
- `src/app/usbdev.py` -- Linux usbfs access
- `src/app/flash.py` -- SPI flash commands
- `src/app/udev.py` -- udev rule install
- `src/script/` -- scenarios
- `out/` -- built bins

## License

This project is licensed under the BSD 3-Clause License - see the LICENSE
file for details.

Copyright (c) 2026 alexander14k28@gmail.com

See [LICENSE](LICENSE) for the license governing this project.
