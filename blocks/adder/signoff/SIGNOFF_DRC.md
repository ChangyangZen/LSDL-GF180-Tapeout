# lsdl_adder64 — DRC / antenna sign-off (0.5×1 reharden)

**Status:** KLayout full DRC = **0** (deep mode, all GF180 rules incl. DF.13/14),
Antenna = **0**. Block 926.6 × 2286.6 µm, 70 % util. Frozen GDS: `lsdl_adder64.gds`.

## Fix chain (from the routed DEF)

| Rule | start → final | how |
|---|---|---|
| Antenna | 384 → 0 | 1974 filler-swap diodes + 5 M3 jumpers |
| NP.2 | 662 → 0 | diode full-width NPLUS band (cell-library fix — see `lib/lsdl-fd-sc-gf180`) |
| M4.2a | 1 → 0 | a[19] middle M3-jumper cut shifted to x = 270 (clears neighbor M4) |
| PP.1 | 8 → 0 | 8 marker-guided concave-neck PPLUS widenings (additive 0.80 µm) |
| PP.2 | 7 → 0 | 7 gap-bridge PPLUS patches + 2 supplementary |
| NW.1a | 3 → 0 | deleted 3 well-overhang fingers + 2 spurious NWELL slivers; re-tiled LVPWELL |

## Reproduce (from `lsdl_adder64_ds.def`)
1. `def2gds.py lsdl_adder64_ds.def G.gds lsdl_adder64` — stream + implant heal + auto thin-sliver widen.
2. `patch_m3_jumpers.py G.gds` — 5 M3 antenna jumpers (a[19] middle cut @ x = 270).
3. Post-route PPLUS + NWELL/LVPWELL heal (coords below) → `lsdl_adder64.gds`.

### PPLUS heal — 17 additive 0.80 µm patches, no NPLUS subtraction
(sites classified by `../pnr/phase_a_classify.py`: gap-bridge vs concave-neck)
- gap-bridges: (265.8,880.9) (295.4,1583.1) (207.0,2088.2) (72.5,1829.5) (440.5,1164.2) (121.8,1151.9) (526.2,462.0)
- concave-necks: (451.4,1164.2) (536.5,2039.0) (554.0,1164.2) (259.1,1423.0) (328.2,2063.6) (328.2,2051.3) (186.9,1780.2) (75.5,2125.2)
- supplementary: (259.6,1422.7) (186.5,1780.6)

### NWELL/LVPWELL heal — flatten wells to top cell, then
- delete fingers (enclose no COMP): [381.92,382.48]×[950.86,951.72], [566.16,566.72]×[2189.88,2190.74], [442.40,442.96]×[243.32,244.18]
- delete spurious NWELL slivers: min bbox dim < 0.20 µm and no COMP under
- re-tile: `nw_new = nw − fingers − strays`; `lp_new = (lp + fingers) − nw_new`

> The PPLUS + NWELL heal is currently applied via the documented inline steps
> above; consolidating them into one validated `finalize_adder_drc.py` is a
> tracked follow-up (not yet committed — it would be unvalidated as a unit).

## Remaining block gates (not yet run on this GDS)
- **LVS** (Netgen, black-box at top level) — pending re-confirm; the M3 jumpers
  reroute through M4 (connectivity-neutral) and the implant/well heal is
  LVS-irrelevant, so it should still match.
- **opens** — passed on the routed `.odb`; re-confirm on this GDS.
- chip-level **density / zero-area** — deferred to the wafer.space precheck after
  macro integration into `chip_top`.
