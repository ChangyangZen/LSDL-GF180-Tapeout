#!/usr/bin/env python3
"""def2gds_cmos.py — stream the CMOS adder/tester DEF to merged GDS.

Same recipe as def2gds.py but against the stock gf180mcu_fd_sc_mcu9t5v0
library: cells are pulled from the PDK's merged library GDS.

    python3 def2gds_cmos.py <design.def> <out.gds> <top_name>
"""

import sys
from pathlib import Path

import pya

SCL = Path('/soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0')
MAP = '/soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map'


def main(def_path: str, out_gds: str, top: str) -> int:
    opt = pya.LoadLayoutOptions()
    cfg = opt.lefdef_config
    cfg.map_file = MAP
    cfg.lef_files = [
        str(SCL / 'techlef' / 'gf180mcu_fd_sc_mcu9t5v0__nom.tlef'),
        str(SCL / 'lef' / 'gf180mcu_fd_sc_mcu9t5v0.lef'),
    ]
    cfg.read_lef_with_def = False
    cfg.produce_blockages = False
    cfg.produce_cell_outlines = False
    opt.lefdef_config = cfg

    ly = pya.Layout()
    ly.read(def_path, opt)
    print(f'DEF read: {ly.cells()} cells, dbu={ly.dbu}, '
          f'top={[c.name for c in ly.top_cells()]}')
    # NB: with the stock LEF (DATABASE MICRONS 1000 -> reader dbu 0.001)
    # the reader scales DEF units correctly — do NOT force dbu here
    # (contrast def2gds.py, where the mismatch left raw DEF integers).

    # library GDS holds every stock cell; load once
    lib = pya.Layout()
    lib.read(str(SCL / 'gds' / 'gf180mcu_fd_sc_mcu9t5v0.gds'))
    lib_cells = {c.name: c for c in lib.each_cell()}

    n = missing = 0
    for c in list(ly.each_cell()):
        if c.name.startswith('gf180mcu_fd_sc_') and c.bbox().empty():
            src = lib_cells.get(c.name)
            if src is None:
                print(f'  MISSING in library GDS: {c.name}')
                missing += 1
                continue
            c.copy_tree(src)
            n += 1
    print(f'merged {n} stock cells, {missing} missing')

    ly.write(out_gds)
    tc = [c for c in ly.top_cells() if c.name == top][0]
    bb = tc.dbbox()
    print(f'wrote {out_gds}: top {top}, bbox {bb.width():.1f} x '
          f'{bb.height():.1f} um')
    return 0 if missing == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
