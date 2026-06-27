#!/usr/bin/env python3
"""heal_pplus_close.py — deterministic, marker-driven local PPLUS morphological
close to clear residual PP.1 (thin-neck pinch) + PP.2 (sub-0.4um gap) implant
artifacts left by def2gds on a hardened block.

For each PP.1/PP.2 DRC marker, take a window around it (+halo). Compute a GLOBAL
PPLUS close = grow(r) then shrink(r) (no clip artifacts), then keep the closed
result ONLY inside the marker windows (rest of PPLUS unchanged). close(r) fills
every concave pinch / gap narrower than ~2r WITHOUT creating new min-width
slivers (unlike additive box patches). Finally subtract NPLUS to keep N+/P+
mutually exclusive.

Reproducible: same input GDS + same DRC lyrdb dir -> identical output.

  heal_pplus_close.py <in.gds> <out.gds> <drc_lyrdb_dir> [r_um=0.21] [halo_um=3.0]
"""
import sys, glob, re, xml.etree.ElementTree as ET
import pya

GDS, OUT, DRC = sys.argv[1], sys.argv[2], sys.argv[3]
R    = float(sys.argv[4]) if len(sys.argv) > 4 else 0.21   # 2R=0.42 > 0.40 PP rule
HALO = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0

ly = pya.Layout(); ly.read(GDS); top = ly.top_cell(); dbu = ly.dbu
def u(v): return int(round(v / dbu))
L_PP = ly.layer(31, 0); L_NP = ly.layer(32, 0)
NUM = re.compile(r'[-+]?\d+\.?\d*')

windows = pya.Region(); pp1_widen = pya.Region(); nm = {'PP.1': 0, 'PP.2': 0}
PW = 0.40   # PP.1 widen half-size (0.80um box) — widens a thin neck to >= rule
for f in glob.glob(DRC + '/*.lyrdb'):
    for it in ET.parse(f).iter('item'):
        cat = (it.findtext('category') or '').strip("'\"")
        if cat not in ('PP.1', 'PP.2'):
            continue
        for v in it.iter('value'):
            t = v.text or ''
            if t.startswith(('edge-pair', 'polygon', 'edge', 'box')):
                n = [float(x) for x in NUM.findall(t)]; xs = n[0::2]; ys = n[1::2]
                cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
                windows.insert(pya.Box(u(min(xs)-HALO), u(min(ys)-HALO),
                                       u(max(xs)+HALO), u(max(ys)+HALO)))
                if cat == 'PP.1':                          # widen thin necks
                    pp1_widen.insert(pya.Box(u(cx-PW), u(cy-PW), u(cx+PW), u(cy+PW)))
                nm[cat] += 1; break
windows.merge()
print(f"  markers: PP.1={nm['PP.1']} PP.2={nm['PP.2']} -> {windows.size()} windows (halo {HALO}um)")

pp = pya.Region(top.shapes(L_PP)); pp.merge()
np_ = pya.Region(top.shapes(L_NP))
# 1. widen thin PP.1 necks (additive boxes at PP.1 markers)
pp = (pp + pp1_widen).merged()
# 2. close within marker windows: merges the gaps the widen creates + original
#    PP.2 gaps (grow(r) then shrink(r) fills <2r features, adds no new slivers)
closed = pp.sized(u(R)).sized(-u(R))
pp_new = ((pp - windows) | (closed & windows)) - np_       # close only in windows; N+/P+ exclusive
top.shapes(L_PP).clear(); top.shapes(L_PP).insert(pp_new)
ly.write(OUT)
print(f"  wrote {OUT}  (widen {pp1_widen.size()} PP.1 + close r={R}um)")
