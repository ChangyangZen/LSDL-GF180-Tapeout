# LSDL-vs-CMOS Benchmark Chip (GF180MCU, wafer.space 0.5×1)

A measurement-chip tapeout on the GF180MCU open PDK comparing **Limited Switch Dynamic
Logic (LSDL)** against **static CMOS** on three benchmark circuits (adder, priority
encoder, mux/rotator). Submitted through the wafer.space `gf180mcu-project-template`
(LibreLane Chip flow).

This is a **fork of `wafer-space/gf180mcu-project-template`**. The LSDL standard-cell
library lives in the separate repo [`lsdl-fd-sc-gf180`](https://github.com/ChangyangZen/LSDL-Standard-Cell-Library),
tracked here as a Git submodule at `lib/lsdl-fd-sc-gf180`.

## Slot: 0.5×1

```
make librelane SLOT=0p5x1
```

| | 0.5×1 |
|---|---|
| DIE_AREA | [0, 0, 1936, 5122] µm (1.94 × 5.12 mm) |
| CORE_AREA | [442, 442, 1494, 4680] µm (1.05 × 4.24 mm) |
| Signal pads | 4 inputs + 44 bidir + 6 analog |
| See | `librelane/slots/slot_0p5x1.yaml`, `src/slot_defines.svh` |

## Repository layout

```
src/                        chip_core.sv, chip_top.sv, slot_defines.svh
librelane/                  config.yaml, macros_5v.yaml, PDN, slot defs
blocks/<adder|mux32|priencoder32>/
    gen_lsdl_*.py           structural LSDL netlist generator
    gen_cmos_*.py           matched-architecture CMOS generator
    *.v, *.sdc              netlists + constraints
    tester/                 per-benchmark go/no-go tester (adder) or LFSR/capture
    pnr/                    OpenROAD scripts (run_pnr.tcl, def2gds.py, gen_abstract.tcl)
    signoff/                FROZEN views + DRC/LVS/antenna logs (LFS)
ip/<macro>/                 exported 4 views (gds, lef, lib, vh) — built from the
                            submodule + block PnR by `make views`
lib/lsdl-fd-sc-gf180/       Git submodule (pinned) = the LSDL cell library
docs/                       overview.md, phase1_cells*.md, tapeout plan
```

## Quick start

```bash
git clone --recurse-submodules https://github.com/ChangyangZen/LSDL-GF180-Tapeout.git
cd LSDL-GF180-Tapeout
make clone-pdk           # one-time: clone GF180MCU PDK
make views               # export macro views from the LSDL library submodule
make librelane SLOT=0p5x1   # synth → PnR → pad ring → DRC → LVS → GDS
```

## Benchmarks

1. **64-bit adder** (systolic ripple, LSDL + CMOS, go/no-go tester per flavor) —
   library proof-of-concept. Dual-rail LSDL on custom 11-track site; matched CMOS on
   stock 9T.
2. **32-bit priority encoder** — LSDL delay-advantage demonstrator: NMOS-only evaluate
   path on the deep OR chain. (CMOS counterpart gated by core budget; 16-bit encoder if
   space is tight.)
3. **32-way mux / rotator** — deferred to a second tapeout if needed (0.5×1 area budget).

## Toolchain + PDK versions

See [`versions.md`](versions.md). The GF180 PDK is cloned by `make clone-pdk`; the
`hpretl/iic-osic-tools` container is pulled locally. Pin a SHA for reproducibility.

## Precheck

```bash
git clone https://github.com/wafer-space/gf180mcu-precheck.git
cd gf180mcu-precheck && nix-shell
python3 precheck.py --input final/gds/chip_top.gds --top chip_top --slot 0p5x1 --cob
```

Must pass with **zero violations** before submission. `final/gds/chip_top.gds` is a
**GitHub Release asset** (166 MB), not checked into this repo.

---

*Original template README (below) retained for LibreLane/PDK reference:*

---

# gf180mcu Project Template (upstream)

## Dependencies

Too manage all dependencies, the project template includes a Nix shell with all the required tools.
Install Nix and LibreLane by following the Nix-based installation instructions: https://librelane.readthedocs.io/en/latest/installation/nix_installation/index.html

## Verification and Simulation

For the verification of the chip we use [cocotb](https://www.cocotb.org/).
```
make sim        # RTL simulation
make sim-gl     # gate-level (after copy-final)
make sim-view   # GTKWave
```

## Choosing a Different Slot Size

The template supports: `1x1`, `0p5x1`, `1x0p5`, `0p5x0p5`.
Set `SLOT=0p5x1 make librelane` or edit `DEFAULT_SLOT` in the Makefile.

## Select Different IP Libraries

| Env  | Values | Description |
|------|--------|-------------|
| SCL  | `gf180mcu_fd_sc_mcu7t5v0`, `_9t5v0`, `gf180mcu_as_sc_mcu7t3v3` | standard cells |
| PAD  | `gf180mcu_fd_io`, `gf180mcu_ocd_io` | I/O pads |
| SRAM | `gf180mcu_fd_ip_sram`, `gf180mcu_ocd_ip_sram` | SRAM |

## Building a Standalone Padring

```
make librelane-padring
SLOT=0p5x0p5 make librelane-padring
```
