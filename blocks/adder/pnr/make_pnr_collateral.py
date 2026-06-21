#!/usr/bin/env python3
"""make_pnr_collateral.py — build OpenROAD-ready PnR collateral for the
lsdl_fd_sc_9t5v0 library from frozen signoff LEFs.

Transforms (signoff LEF -> PnR LEF):
  * MACRO names lowercased (netlist instances are lsdl_*; signoff LEFs
    carry LSDL_* from lclayout).
  * Layers mapped to PDK names: met1->Metal1, met2->Metal2, via1->Via1.
  * Non-routing layers dropped (FEOL contacts/diffusion).
Outputs one merged LEF for all cells + a custom 11T site declaration to
append to the PDK tech LEF (SITE unit 0.56 x 6.16).

Usage: make_pnr_collateral.py
"""

from __future__ import annotations
import re
import shutil
from pathlib import Path

ROOT = Path('/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib')
SIGNOFF = ROOT / 'librecell'
OUT = ROOT / 'blocks' / 'adder' / 'pnr'

CELLS = [
    'lsdl_inv_x1', 'lsdl_nand2_x1', 'lsdl_nand3_x1', 'lsdl_nand4_x1',
    'lsdl_nor2_x1', 'lsdl_nor3_x1', 'lsdl_nor4_x1',
    'lsdl_aoi21_x1', 'lsdl_aoi22_x1',
]

LAYER_MAP = {'met1': 'Metal1', 'met2': 'Metal2', 'via1': 'Via1'}
DROP_LAYERS = {'ndiffc', 'pdiffc', 'polycont', 'poly', 'ndiff', 'pdiff'}

TECH_TLEF = ('/soe/czeng14/software/pdk/gf180mcuD/libs.ref/'
             'gf180mcu_fd_sc_mcu9t5v0/techlef/gf180mcu_fd_sc_mcu9t5v0__nom.tlef')

SITE_BLOCK = """
SITE unit
  SYMMETRY X Y ;
  CLASS core ;
  SIZE 0.56 BY 6.16 ;
END unit
"""


GRID = 0.005  # GF180 manufacturing grid (um)


def snap_rect(m: re.Match) -> str:
    """Snap RECT to the manufacturing grid, shrinking (lo up, hi down)."""
    import math
    x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
    x0 = math.ceil(x0 / GRID - 1e-6) * GRID
    y0 = math.ceil(y0 / GRID - 1e-6) * GRID
    x1 = math.floor(x1 / GRID + 1e-6) * GRID
    y1 = math.floor(y1 / GRID + 1e-6) * GRID
    return f'RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;'


def transform_macro(lef_text: str, cell: str) -> str:
    upper = cell.upper()
    out = []
    drop = False
    for line in lef_text.splitlines():
        m = re.match(r'(\s*)LAYER\s+(\S+)\s*;', line)
        if m:
            layer = m.group(2)
            if layer in DROP_LAYERS:
                drop = True
                continue
            drop = False
            line = f'{m.group(1)}LAYER {LAYER_MAP.get(layer, layer)} ;'
        elif drop:
            if re.match(r'\s*RECT\b', line):
                continue
            drop = False
        line = re.sub(r'RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;',
                      snap_rect, line)
        line = line.replace(upper, cell)
        out.append(line)
    return '\n'.join(out)


def main():
    OUT.mkdir(exist_ok=True)
    merged = ['VERSION 5.7 ;', 'BUSBITCHARS "[]" ;', 'DIVIDERCHAR "/" ;', '']
    for cell in CELLS:
        lef = SIGNOFF / f'signoff_{cell}' / f'{cell}.lef'
        merged.append(transform_macro(lef.read_text(), cell))
        merged.append('')
    merged.append('END LIBRARY')
    out_lef = OUT / 'lsdl_fd_sc_9t5v0.lef'
    out_lef.write_text('\n'.join(merged) + '\n')
    print(f'wrote {out_lef} ({len(CELLS)} macros)')

    # tech LEF: PDK nom + custom 11T site, inserted before PROPERTYDEFINITIONS
    tech = Path(TECH_TLEF).read_text()
    tech = tech.replace('PROPERTYDEFINITIONS', SITE_BLOCK + '\nPROPERTYDEFINITIONS', 1)
    out_tlef = OUT / 'gf180mcu_lsdl.tlef'
    out_tlef.write_text(tech)
    print(f'wrote {out_tlef} (added SITE unit 0.56 x 6.16)')


if __name__ == '__main__':
    main()
