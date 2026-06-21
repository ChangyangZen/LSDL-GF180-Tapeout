# Toolchain & PDK versions

This tapeout is built against the versions below. Pin these to reproduce
the signed-off chip.

| Component | Version | Notes |
|---|---|---|
| Template | `wafer-space/gf180mcu-project-template` | <tag> — fork | This repo |
| LSDL cell library | `lsdl-fd-sc-gf180` | submodule at `lib/lsdl-fd-sc-gf180` | Pinned to a commit/tag |
| PDK | **GF180MCU `gf180mcuD`** | commit `019cf7a3` | installed separately (not vendored) |
| Container | `hpretl/iic-osic-tools` | **pin a digest** for reproducibility |
| OpenROAD | `26Q2-1164-g08f67ee5e` | PnR + antenna repair + abstract LEF |
| KLayout | `0.30.8` | DRC sign-off (GF180 `run_drc.py`) |
| Magic + Netgen | (from IIC-OSIC-TOOLS) | cell-level ext2spice + LVS |
| ngspice | (from IIC-OSIC-TOOLS) | PVT characterization |

## Slot

This tapeout targets the wafer.space **0.5×1 slot**.
- `make librelane SLOT=0p5x1`
- DIE_AREA: `[0, 0, 1936, 5122]` µm (1.94 × 5.12 mm)
- CORE_AREA: `[442, 442, 1494, 4680]` µm (1.05 × 4.24 mm)

## Sign-off gates (per block, pre-submission)
- KLayout DRC: **0** (all rules, flat).
- KLayout Antenna: **0**.
- Netgen LVS: "match uniquely."
- OpenROAD STA: functional closure at benchmark target frequency.
