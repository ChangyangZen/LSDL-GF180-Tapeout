#!/usr/bin/env python3
"""Phase A: marker-guided concave-corner classification + patch proposal.

For each of the 18 PP.1/PP.2/NW.1a_MV DRC markers:
1. Grow a 1.0um search window around the marker bbox.
2. Clip the relevant layer (PPLUS 31/0 or NWELL 21/0) to that window.
3. Find the nearest concave (reentrant) corner of the polygon.
4. Classify the pattern and propose a local patch bbox.
5. Print the proposal — NO patches applied yet.

  phase_a_classify.py <gds> <drc_lyrdb_dir>
"""
import sys, re, glob, xml.etree.ElementTree as ET
import pya

GDS = sys.argv[1]; LYR = sys.argv[2]
ly = pya.Layout(); ly.read(GDS); top = ly.top_cell(); dbu = ly.dbu
def u(v): return int(round(v/dbu))

LAY_RULE = {'PP.1': 31, 'PP.2': 31, 'NW.1a_MV': 21}
TARGET = {'PP.1': 0.44, 'PP.2': 0.44, 'NW.1a_MV': 0.92}
WINDOW_R = 1.2  # um — search radius around marker

NUM = re.compile(r'[-+]?\d+\.?\d*')

# ── parse DRC markers ──
markers = []
for ff in glob.glob(LYR+'/*.lyrdb'):
    for it in ET.parse(ff).iter('item'):
        cat = (it.findtext('category') or '?').strip("'\"")
        if cat not in LAY_RULE: continue
        for v in it.iter('value'):
            t = v.text or ''
            if t.startswith(('polygon','edge','box')):
                n = NUM.findall(t)
                if len(n) >= 4:
                    xs = [float(n[i]) for i in range(0, len(n), 2)]
                    ys = [float(n[i]) for i in range(1, len(n), 2)]
                    markers.append((cat, min(xs), min(ys), max(xs), max(ys)))
                elif len(n) >= 2:
                    markers.append((cat, float(n[0]), float(n[1]), float(n[0]), float(n[1])))
                    break; break
print(f"# loaded {len(markers)} markers")

# ── concave-corner detector for rectilinear polygons ──
def concave_corners(polygon, kind='all'):
    """Return list of (x_um, y_um, dx_toward, dy_toward) for concave (reentrant)
    corners of a rectilinear polygon. A concave corner = 270° inside turn:
    the polygon makes a right-angle bend INTO itself (convex = 90° bend OUT).

    For clockwise poly: a right turn = convex, left turn = concave.
    We detect by cross product regardless of winding order by checking which
    side of the L the interior lies on.
    """
    corners = []
    for hole_idx in range(polygon.holes() + 1):
        if hole_idx == 0:
            pts = [(p.x*dbu, p.y*dbu) for p in polygon.each_point_hull()]
        else:
            pts = [(p.x*dbu, p.y*dbu) for p in polygon.each_point_hole(hole_idx - 1)]
        if len(pts) < 4: continue
        n = len(pts)
        for i in range(n):
            p0 = pts[(i-1)%n]; p1 = pts[i]; p2 = pts[(i+1)%n]
            # edge directions
            e1 = (p1[0]-p0[0], p1[1]-p0[1])  # incoming edge
            e2 = (p2[0]-p1[0], p2[1]-p1[1])  # outgoing edge
            # cross product (z): e1 × e2
            cross = e1[0]*e2[1] - e1[1]*e2[0]
            if abs(cross) < 1e-9: continue  # collinear
            # For a rectilinear polygon, magnitude = |e1|*|e2|
            # Determine: is this convex (90° OUT) or concave (270° IN)?
            # Point slightly inward from the vertex along the angle bisector
            # and check if it's inside the polygon.
            mag1 = (e1[0]**2 + e1[1]**2)**0.5
            mag2 = (e2[0]**2 + e2[1]**2)**0.5
            u1 = (e1[0]/mag1, e1[1]/mag1) if mag1 > 0 else (0,0)
            u2 = (e2[0]/mag2, e2[1]/mag2) if mag2 > 0 else (0,0)
            # inward direction (rotate u1 90° toward the inside)
            # For concave corners, the inside is opposite the 'outside' direction.
            # Use the polygon's containment: test a point 0.1um inside the bend.
            inside = (-e1[1]/mag1, e1[0]/mag1) if mag1 > 0 else (0,0)  # rotate e1 CCW 90°
            # also try the other rotation
            inside2 = (e1[1]/mag1, -e1[0]/mag1) if mag1 > 0 else (0,0)
            test1 = (p1[0] + inside[0]*0.1, p1[1] + inside[1]*0.1)
            test2 = (p1[0] + inside2[0]*0.1, p1[1] + inside2[1]*0.1)
            ti1 = int(test1[0]/dbu); ti2 = int(test1[1]/dbu)
            ti3 = int(test2[0]/dbu); ti4 = int(test2[1]/dbu)
            inside_poly = polygon.inside(pya.Point(ti1, ti2))
            if inside_poly:
                # test1 is inside, so inside direction = toward test1 from the L
                corners.append((p1[0], p1[1], -e1[1]/mag1*0.5, e1[0]/mag1*0.5))
            else:
                inside_poly2 = polygon.inside(pya.Point(ti3, ti4))
                if inside_poly2:
                    corners.append((p1[0], p1[1], e1[1]/mag1*0.5, -e1[0]/mag1*0.5))
    return corners

# ── helper: find nearest concave corner in a region ──
def _find_nearest_concave(region, cx_target, cy_target):
    """Return (corner_xy, distance) or (None, inf)."""
    best_corner = None; best_dist = 1e9
    for poly in region.each():
        for (cx_um, cy_um, *_rest) in concave_corners(poly):
            d = ((cx_um - cx_target)**2 + (cy_um - cy_target)**2)**0.5
            if d < best_dist: best_dist = d; best_corner = (cx_um, cy_um)
    return best_corner, best_dist

# ── load per-layer regions ──
pp_r = pya.Region(top.shapes(ly.layer(31,0))) if ly.find_layer(31,0) else pya.Region()
nw_r = pya.Region(top.shapes(ly.layer(21,0))) if ly.find_layer(21,0) else pya.Region()
pp_r.merge(); nw_r.merge()

# ── classify each marker ──
proposals = []
for rule, mx0, my0, mx1, my1 in markers:
    layer_num = LAY_RULE[rule]
    rgn = pp_r if rule.startswith('PP') else nw_r
    tgt = TARGET[rule]
    # expand window around marker
    win = pya.Box(u(mx0 - WINDOW_R), u(my0 - WINDOW_R), u(mx1 + WINDOW_R), u(my1 + WINDOW_R))
    local = rgn & pya.Region(win)

    # ── handle empty window: NW.1a needs wider search; others → unknown ──
    if local.is_empty():
        if rule == 'NW.1a_MV':
            win2 = pya.Box(u(mx0 - 3.0), u(my0 - 3.0), u(mx1 + 3.0), u(my1 + 3.0))
            local2 = rgn & pya.Region(win2)
            mx_cnt = (mx0+mx1)/2; my_cnt = (my0+my1)/2
            if local2.size() >= 2:
                cls = 'nwell_gap_bridge'
                patch = pya.Box(u(mx_cnt - 0.46), u(my_cnt - 0.46),
                                u(mx_cnt + 0.46), u(my_cnt + 0.46))
            elif not local2.is_empty():
                cls = 'thin_nwell_neck'
                patch = pya.Box(u(mx_cnt - 0.46), u(my_cnt - 0.46),
                                u(mx_cnt + 0.46), u(my_cnt + 0.46))
            else:
                cls = 'unknown (no NWELL in 3um)'
                patch = None
            proposals.append((rule, mx0, my0, mx1, my1, cls, patch))
            continue
        else:
            proposals.append((rule, mx0, my0, mx1, my1, 'unknown (no poly in window)', None))
            continue

    # find the polygon containing/near the marker
    marker_box = pya.Box(u(mx0-0.05), u(my0-0.05), u(mx1+0.05), u(my1+0.05))
    marker_hit = local & pya.Region(marker_box)

    # ── PP.2: spacing violation = TWO pieces too close ──
    if rule == 'PP.2':
        # how many separate PPLUS polys in the window?
        npieces = local.size()
        if npieces >= 2:
            cls = 'pplus_gap_bridge'
            mx_cnt = (mx0+mx1)/2; my_cnt = (my0+my1)/2
            patch = pya.Box(u(mx_cnt - 0.22), u(my_cnt - 0.22),
                            u(mx_cnt + 0.22), u(my_cnt + 0.22))
        else:
            # single piece — treat as thin neck
            cls = 'thin_pplus_neck'
            best_corner, best_dist = _find_nearest_concave(marker_hit, (mx0+mx1)/2, (my0+my1)/2)
            if best_corner:
                cx, cy = best_corner
                patch = pya.Box(u(cx - 0.22), u(cy - 0.22), u(cx + 0.22), u(cy + 0.22))
            else:
                patch = pya.Box(u(mx_cnt - 0.22), u(my_cnt - 0.22), u(mx_cnt + 0.22), u(my_cnt + 0.22))
        extra = ""
        proposals.append((rule, mx0, my0, mx1, my1, cls, patch, extra))
        continue

    # ── PP.1 / NW.1a: within a single polygon ──
    if marker_hit.is_empty():
        # marker is between pieces (gap — may have been bitten away)
        if rule == 'NW.1a_MV':
            # widen the window for NWELL — the marker may be at a debited gap
            win2 = pya.Box(u(mx0 - 3.0), u(my0 - 3.0), u(mx1 + 3.0), u(my1 + 3.0))
            local2 = rgn & pya.Region(win2)
            mx_cnt = (mx0+mx1)/2; my_cnt = (my0+my1)/2
            if local2.size() >= 2:
                cls = 'nwell_gap_bridge'
                patch = pya.Box(u(mx_cnt - 0.46), u(my_cnt - 0.46),
                                u(mx_cnt + 0.46), u(my_cnt + 0.46))
            elif not local2.is_empty():
                cls = 'thin_nwell_neck'
                patch = pya.Box(u(mx_cnt - 0.46), u(my_cnt - 0.46),
                                u(mx_cnt + 0.46), u(my_cnt + 0.46))
            else:
                cls = 'unknown (no NWELL in 3um)'
                patch = None
        else:
            cls = 'unknown (no poly in window)'
            patch = None
        proposals.append((rule, mx0, my0, mx1, my1, cls, patch))
        continue

    # PP.1 thin neck: find concave corner
    best_corner, best_dist = _find_nearest_concave(marker_hit, (mx0+mx1)/2, (my0+my1)/2)
    if best_corner:
        cx, cy = best_corner
        cls = 'thin_pplus_neck' if rule.startswith('PP') else 'thin_nwell_neck'
        hs = tgt / 2
        patch = pya.Box(u(cx - hs), u(cy - hs), u(cx + hs), u(cy + hs))
        proposals.append((rule, mx0, my0, mx1, my1, cls, patch, f"corner_at=({cx:.1f},{cy:.1f})"))
    else:
        cls = 'thin_pplus_neck (no corner)' if rule.startswith('PP') else 'thin_nwell_neck (no corner)'
        mx_cnt = (mx0+mx1)/2; my_cnt = (my0+my1)/2
        hs = tgt / 2
        patch = pya.Box(u(mx_cnt - hs), u(my_cnt - hs), u(mx_cnt + hs), u(my_cnt + hs))
        proposals.append((rule, mx0, my0, mx1, my1, cls, patch))

# ── print proposals ──
print()
for p in proposals:
    rule = p[0]; cls = p[5]; ptch = p[6]
    pt_str = ""
    if ptch:
        dbu2 = ly.dbu
        pt_str = f"patch=({ptch.left*dbu2:.1f},{ptch.bottom*dbu2:.1f})-({ptch.right*dbu2:.1f},{ptch.top*dbu2:.1f})"
    extra = p[7] if len(p) > 7 else ""
    print(f"  {rule:9s} marker=({p[1]:.1f},{p[2]:.1f})-({p[3]:.1f},{p[4]:.1f})  class={cls:35s} {pt_str} {extra}")

# ── summary ──
from collections import Counter
cls_counts = Counter(p[5] for p in proposals)
print()
for k,v in sorted(cls_counts.items()): print(f"  {k}: {v}")
unknown = [p for p in proposals if 'unknown' in p[5]]
if unknown:
    print(f"\n  WARNING: {len(unknown)} UNKNOWN markers — inspect manually before patching")
else:
    print(f"\n  All {len(proposals)} markers classified — ready for patching")
