#!/usr/bin/env python3
"""M3 antenna jumper-split (GF180). For each long violating M3 wire: physically
CUT a gap in the routing M3 and bridge it V3 -> short M4 -> V3, breaking the M3
island into pieces each below the antenna ratio. KLayout's M3 antenna step sees
the islands before M4 connectivity exists, so the per-gate M3 area drops; the M4
bridge re-joins the net at the M4 step (short -> no M4 antenna). LVS still sees a
connected net (M3-V3-M4-V3-M3).

Operates on TOP-cell routing shapes only (cell internals untouched).
GDS: Metal3 42/0, Via3 40/0, Metal4 46/0.  Via3 cut 0.26; M3 enc 0.06(x)/0.01(y);
M4 enc generous 0.16. Gap 0.40 (> M3 spacing/EOL).
  patch_m3_jumpers.py <gds>
"""
import sys, pya
GDS = sys.argv[1]
ly = pya.Layout(); ly.read(GDS); top = ly.top_cell(); dbu = ly.dbu
L_M3 = ly.layer(42,0); L_V3 = ly.layer(40,0); L_M4 = ly.layer(46,0)
def u(v): return int(round(v/dbu))

# (name, x0,y0,x1,y1 of the long horizontal M3 wire, [cut-x positions] or ncuts)
VIOLS = [
    ("a[19]",  76.8, 1849.0, 538.7, 1851.0, [192.3, 270.0, 423.2]),  # middle shifted from 307.8 -> 270 for M4.2a
    ("an[47]", 210.0, 920.0, 534.2, 924.5, 1),
    ("a[20]",  185.4, 1910.0, 498.4, 1913.0, 1),
]
GAP=0.40; CUT=0.26; M3ENC=0.06; M4ENC=0.16

m3_top = pya.Region(top.shapes(L_M3))   # top-cell (routing) M3 only
gaps = pya.Region()
addV3 = []; addM4 = []
for name,x0,y0,x1,y1,cuts in VIOLS:
    if isinstance(cuts, int):
        span = x1 - x0
        xs = [x0 + span*(k+1)/(cuts+1) for k in range(cuts)]
    else:
        xs = cuts
    print(f"{name}: span {x1-x0:.0f}um, {len(xs)} cut(s) at x={[round(x,1) for x in xs]}")
    for xc in xs:
        # local wire y from a thin top-M3 slice at xc
        sl = m3_top & pya.Region(pya.Box(u(xc-1.0),u(y0),u(xc+1.0),u(y1)))
        if sl.is_empty():
            print(f"  WARN no M3 at x={xc:.1f}"); continue
        # cy = center of the WIDEST M3 piece in the slice (the long horizontal
        # wire) — the slice bbox center can sit on a stub and miss the wire.
        best=None; bw=-1
        for poly in sl.each():
            pb=poly.bbox(); w=pb.right-pb.left
            if w>bw: bw=w; best=pb
        cy = (best.bottom+best.top)/2.0*dbu
        # gap
        gaps.insert(pya.Box(u(xc-GAP/2),u(cy-0.20),u(xc+GAP/2),u(cy+0.20)))
        # via3 cuts on each island end (M3 encloses 0.06 in x)
        lxr = xc-GAP/2-M3ENC; lxl = lxr-CUT
        rxl = xc+GAP/2+M3ENC; rxr = rxl+CUT
        for vx0,vx1 in ((lxl,lxr),(rxl,rxr)):
            addV3.append((vx0,cy-CUT/2,vx1,cy+CUT/2))
        # short M4 bridge enclosing both via3 cuts by M4ENC
        addM4.append((lxl-M4ENC, cy-CUT/2-M4ENC, rxr+M4ENC, cy+CUT/2+M4ENC))

# apply: subtract gaps from routing M3, add via3 + M4
m3_top -= gaps
top.shapes(L_M3).clear(); top.shapes(L_M3).insert(m3_top)
for x0,y0,x1,y1 in addV3: top.shapes(L_V3).insert(pya.Box(u(x0),u(y0),u(x1),u(y1)))
for x0,y0,x1,y1 in addM4: top.shapes(L_M4).insert(pya.Box(u(x0),u(y0),u(x1),u(y1)))
ly.write(GDS)
print(f"patched: {len(addV3)//2} M3 gaps, {len(addV3)} Via3, {len(addM4)} M4 bridges")
