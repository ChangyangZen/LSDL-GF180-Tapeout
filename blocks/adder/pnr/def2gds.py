#!/usr/bin/env python3
"""def2gds.py — stream the routed LSDL adder DEF to a merged GDS (KLayout).

1. Read the DEF with the macro LEFs + the official PDK layer map, producing
   routing/PDN geometry on real GF180 GDS layers and abstract cells for the
   lsdl_* macros.
2. Read each signoff cell GDS into the same layout with OverwriteCell, so
   every abstract macro is replaced by the DRC/LVS-clean real layout.
3. Write <top>.gds.

Run inside the container (needs klayout pymod):
    python3 def2gds.py <design.def> <out.gds> <top_name>
"""

import sys
from pathlib import Path

import pya

PNR = Path('/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder/pnr')
SIGNOFF = Path('/mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/librecell')
MAP = '/soe/czeng14/software/pdk/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map'

CELL_GDS = {}
for d in SIGNOFF.glob('signoff_lsdl_*'):
    name = d.name.replace('signoff_', '')
    g = d / f'{name}.gds'
    if g.exists():
        CELL_GDS[name] = g
for g in (SIGNOFF / 'signoff_support_11t').glob('lsdl_*.gds'):
    CELL_GDS[g.stem] = g


def extend_implant_bands(ly: pya.Layout, cell: pya.Cell) -> None:
    """Extend NPLUS/PPLUS shapes near the cell's top/bottom edge exactly TO
    it. Cells were signed off standalone with bands stopping 0.1 um short
    of the boundary; stacked rows (alternating N/FS) then leave 0.2 um
    same-layer gaps at every row seam -> NP.2/PP.2. Extending to the edge
    makes abutting bands merge edge-on-edge. (Extending BEYOND the edge is
    wrong: where the neighbor row has no implant at that x, the overshoot
    tab creates NP.1/PP.1 sliver-width and new spacing violations.)"""
    dbu = ly.dbu
    b63 = ly.layer(63, 0)
    bnd = pya.Region(cell.begin_shapes_rec(b63)).bbox()
    if bnd.empty():
        return
    margin = int(0.15 / dbu)        # "near edge" tolerance (vertical)
    wide = int(0.8 * bnd.width())   # "band" = spans >=80% of cell width
    for lnum in (31, 32):      # PPLUS, NPLUS
        li = ly.layer(lnum, 0)
        new_boxes = []
        for s in cell.shapes(li).each():
            bb = s.bbox()
            lo, hi = bb.bottom, bb.top
            left, right = bb.left, bb.right
            if bb.bottom - bnd.bottom <= margin:
                lo = bnd.bottom
            if bnd.top - bb.top <= margin:
                hi = bnd.top
            # Bands also extend horizontally to the cell edges so they
            # merge into continuous row-length stripes (stock-library
            # convention); islands (taps) are left untouched.
            if bb.width() >= wide:
                left, right = bnd.left, bnd.right
            if (lo, hi, left, right) != (bb.bottom, bb.top, bb.left, bb.right):
                new_boxes.append(pya.Box(left, lo, right, hi))
        for b in new_boxes:
            cell.shapes(li).insert(b)


def fix_contact_enclosure(ly: pya.Layout, cell: pya.Cell) -> None:
    """Guarantee CO.6 (Metal1 encloses contact by >= 0.005): the tap cell
    has one contact whose M1 cover is ~2 nm short (off-grid build
    geometry). Add a 10 nm M1 halo around every contact."""
    li_con, li_m1 = ly.layer(33, 0), ly.layer(34, 0)
    con = pya.Region(cell.shapes(li_con))
    if con.is_empty():
        return
    cell.shapes(li_m1).insert(con.sized(int(0.01 / ly.dbu)))


def heal_implants(ly: pya.Layout, top_name: str) -> None:
    """Flatten NPLUS/PPLUS to the top cell and apply a morphological close
    (+0.2/-0.2 um): tapcell staggers taps between rows, so band gaps and
    band starts meet corner-on-corner at row seams (NP/PP.1/.2 pinches).
    Closing fills any sub-0.4 um notch; tap gaps (1.68 um) stay open.
    The opposite layer's original region is subtracted afterwards so the
    heal can never create N+/P+ overlaps (butted junctions preserved)."""
    top = [c for c in ly.top_cells() if c.name == top_name][0]
    # tapcell staggers taps between rows, so implant bands meet CORNER-ON-
    # CORNER at seam/tap corners ("checkerboard kiss"): zero-width contact
    # violates NP/PP.1/.2 euclidean width/space. Morphological closing
    # cannot fix a point contact (dilate-erode adds measure-zero material),
    # and a real bridge would overlap the tap's opposite-polarity island.
    # Resolution: PULL BACK — subtract a bite square at every kiss vertex,
    # cleanly separating the two regions (space >= 0.4 passes).
    bite = int(0.4 / ly.dbu)
    li_np, li_pp = ly.layer(32, 0), ly.layer(31, 0)

    def debite(region: pya.Region) -> pya.Region:
        from collections import Counter
        region = region.merged()
        seen = Counter()
        for poly in region.each():
            for pt in poly.each_point_hull():
                seen[(pt.x, pt.y)] += 1
            for h in range(poly.holes()):
                for pt in poly.each_point_hole(h):
                    seen[(pt.x, pt.y)] += 1
        bites = pya.Region()
        n = 0
        for (x, y), cnt in seen.items():
            if cnt >= 2:        # kiss vertex (non-manifold contact)
                bites.insert(pya.Box(x - bite, y - bite, x + bite, y + bite))
                n += 1
        print(f'  {n} kiss vertices bitten')
        # opening pass: a bite edge grazing an existing band edge can leave
        # a sub-0.4 sliver (PP.1); erode/dilate 0.19 deletes anything
        # thinner than 0.38 while preserving >=0.4 rectilinear features.
        o = int(0.19 / ly.dbu)
        return (region - bites).sized(-o).sized(o)

    np_r = pya.Region(top.begin_shapes_rec(li_np))
    pp_r = pya.Region(top.begin_shapes_rec(li_pp))
    np_h = debite(np_r) - pp_r
    pp_h = debite(pp_r) - np_r

    # Thin PPLUS features that survived the bite+opening pass are placement-
    # specific artifacts (tap-stagger corner slivers, 0.38-0.40 um).  Auto-
    # detect them (erode by 0.2 um — anything < 0.4 um disappears) and widen
    # each locally to >= 0.44 um.  Replaces the old hardcoded neck-coordinate
    # list (valid only for one placement; stale on reharden/0.5x1).
    o2 = int(0.20 / ly.dbu)
    eroded = pp_h.sized(-o2).sized(o2)      # morph. opening: keeps >=0.4um
    thin = pp_h - eroded                      # what the opening removes (< 0.4um)
    if not thin.is_empty():
        # widen each thin fragment to a legal stem (0.44 um → 0.22 radius)
        patches = thin.sized(int(0.22 / ly.dbu))
        pp_h = (pp_h + patches).merged()
        print(f'  auto-widened {thin.size()} thin PPLUS slivers')
    else:
        patches = pya.Region()
    for c in ly.each_cell():
        c.shapes(li_np).clear()
        c.shapes(li_pp).clear()
    top.shapes(li_np).insert(np_h)
    top.shapes(li_pp).insert(pp_h)
    print(f'implants healed: NPLUS {np_h.count()} polys, '
          f'PPLUS {pp_h.count()}')


def main(def_path: str, out_gds: str, top: str) -> int:
    # NB: opt.lefdef_config returns a COPY — configure once, assign back.
    opt = pya.LoadLayoutOptions()
    cfg = opt.lefdef_config
    cfg.dbu = 0.0005                 # match DEF UNITS 2000
    cfg.map_file = MAP
    cfg.lef_files = [
        str(PNR / 'gf180mcu_lsdl.tlef'),
        str(PNR / 'lsdl_fd_sc_9t5v0.lef'),
        str(PNR / 'lsdl_support_11t.lef'),
    ]
    cfg.read_lef_with_def = False
    cfg.produce_blockages = False
    cfg.produce_cell_outlines = False
    opt.lefdef_config = cfg

    ly = pya.Layout()
    ly.read(def_path, opt)
    print(f'DEF read: {ly.cells()} cells, top='
          f'{[c.name for c in ly.top_cells()]}, reader dbu={ly.dbu}')

    # The LEFDEF reader keeps raw DEF integers regardless of the configured
    # dbu (observed: dbu stays at its 0.005 default). DEF UNITS is 2000, so
    # the true dbu of those integers is 0.0005 — force it.
    ly.dbu = 0.0005

    # Convert the ENTIRE DEF layout to the PDK-standard dbu 0.001 *up front* —
    # before merging the native cells and before implant healing. This is the
    # whole fix for the Magic hang: Magic (and the wafer.space precheck) hard-
    # require dbu 1e-9; a 0.0005-dbu GDS makes Magic rescale by a non-integer
    # factor relative to its lambda grid, rounding the LSDL cells' 1 nm-grid
    # geometry off-grid -> hundreds of thousands of width/contact DRC markers
    # (the 21.7 h "hang"). DEF routing is on the 5 nm manufacturing grid
    # (= multiples of 10 units @0.0005) so the ×0.5 scale is exact (10 -> 5
    # units @0.001). Doing the conversion HERE, not after healing, means:
    #   (a) the native signoff cells (dbu 0.001) merge at *equal* dbu, so
    #       copy_tree reproduces them bit-for-bit -> the merged macro is
    #       identical to the standalone-Magic-clean cells, and
    #   (b) heal_implants runs at dbu 0.001, so every healed band/bite/patch
    #       lands on the real 1 nm grid by construction (no later rounding).
    ly.transform(pya.ICplxTrans(0.5))
    ly.dbu = 0.001
    print(f'converted layout to dbu {ly.dbu} (×0.5, Magic/precheck standard)')

    # Replace abstract macro cells with the real signoff layouts. The layout is
    # now at dbu 0.001; the signoff cell GDS are also dbu 0.001, so copy_tree is
    # a verbatim same-dbu copy (the merged macros are bit-identical to the
    # standalone DRC/LVS-clean cells). Support cells at dbu 0.005 scale ×5
    # exactly (dbu-aware copy_tree; their geometry is on the 5 nm grid).
    n = 0
    present = {c.name: c for c in ly.each_cell()}
    for name, gds in sorted(CELL_GDS.items()):
        if name in present:
            tmp = pya.Layout()
            tmp.read(str(gds))
            tgt = present[name]
            tgt.clear()
            tgt.copy_tree(tmp.top_cell())
            extend_implant_bands(ly, tgt)
            fix_contact_enclosure(ly, tgt)
            n += 1
    print(f'merged {n} cell GDS (dbu-aware, implant bands extended)')

    heal_implants(ly, top)

    # sanity: no remaining empty referenced macros
    empty = [c.name for c in ly.each_cell()
             if c.name.startswith('lsdl_') and c.bbox().empty()]
    if empty:
        print(f'WARNING: empty cells remain: {empty[:10]}')

    top_cell = None
    for c in ly.top_cells():
        if c.name == top:
            top_cell = c
    if top_cell is None:
        print(f'ERROR: top {top} not found among '
              f'{[c.name for c in ly.top_cells()]}')
        return 1

    # Strip lclayout border markers (142/1 = l_border_vertical, 142/2 =
    # l_border_horizontal): non-mask routing-region annotation that KLayout
    # ignores but Magic's GF180 tech cannot map (fatal "Unknown layer/datatype"
    # on GDS read during full-chip Magic DRC/LVS). Not a mask layer — safe to drop.
    for (lnum, dt) in ((142, 1), (142, 2)):
        li = ly.find_layer(lnum, dt)
        if li is not None:
            ly.delete_layer(li)
            print(f'stripped lclayout border layer {lnum}/{dt}')

    # Snap every cell onto the GF180 5 nm manufacturing grid. LibreCell emits the
    # poly/contact/metal/via stack with a systematic +2 nm offset relative to the
    # on-grid COMP/well (an lclayout device-layer-vs-routing-grid coordinate
    # mismatch — ~8-13% of cell coords sit at ≡2 mod 5 nm). KLayout DRC with
    # --no_offgrid tolerated it, but Magic snaps off-grid geometry on GDS read and
    # shatters each cell into hundreds of spurious width/contact markers (the
    # 969,912-marker "hang"); the wafer.space precheck also enforces the grid.
    # Each off-grid feature is a *rigid* +2 nm translate, so round-to-nearest-5 nm
    # is lossless — verified KLayout(off-grid ON) + Magic + Netgen-LVS clean on the
    # cells: routing-stack widths/spacings are preserved and enclosures to COMP
    # shift ≤2 nm (rule margins ≫2 nm). Routing + healed implants are already
    # on-grid (snap = no-op there). Text labels are preserved (snap shapes only).
    gu = int(round(0.005 / ly.dbu))      # 5 nm in dbu units
    snapped = 0
    for c in ly.each_cell():
        for li in ly.layer_indexes():
            shp = c.shapes(li)
            r = pya.Region(shp)
            if r.is_empty():
                continue                  # text-only / empty layer: leave as-is
            texts = [s.text for s in shp.each(pya.Shapes.STexts)]  # value copies
            rs = r.snapped(gu, gu)
            shp.clear()
            shp.insert(rs)
            for t in texts:
                shp.insert(t)
            snapped += 1
    print(f'snapped all cells to the {gu*ly.dbu*1000:.0f} nm grid '
          f'({snapped} cell-layers)')

    # (dbu conversion to 0.001 already done up front, before the cell merge and
    # healing — see top of main(). No post-processing rescale needed here.)
    ly.write(out_gds)
    bb = top_cell.dbbox()
    print(f'wrote {out_gds}: top {top}, bbox {bb.width():.1f} x '
          f'{bb.height():.1f} um')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
