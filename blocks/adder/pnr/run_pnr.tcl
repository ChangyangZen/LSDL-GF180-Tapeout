# run_pnr.tcl — OpenROAD PnR of the LSDL 64-bit adder macro.
# 16,832 LSDL cells on the custom 11-track site (unit, 0.56 x 6.16 um).
# Run:  openroad -no_init -exit run_pnr.tcl

set DIR  /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder
set PNR  ${DIR}/pnr
set LIBD /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib

read_lef ${PNR}/gf180mcu_lsdl.tlef
read_lef ${PNR}/lsdl_fd_sc_9t5v0.lef
read_lef ${PNR}/lsdl_support_11t.lef
read_liberty ${LIBD}/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib
# static-CMOS clock-tree buffer (for CTS)
read_liberty ${LIBD}/lib/lsdl_clkbuf__tt_5v_25c.lib

read_verilog ${DIR}/adder64_lsdl.v
link_design lsdl_adder64

# ── floorplan: narrow + dense for the 0.5x1 slot ───────────────────────
# 0.5x1 core is 1052 um WIDE x 4238 um TALL. The square 60%/AR1.0 floorplan
# was 1568 um -> too wide. Re-shape tall+narrow (AR = height/width) so the
# block fits the 1052 um width with side halo, and denser (70%) to free
# vertical budget for the 3 other macros stacked above it. (1x1 default was
# -utilization 60 -aspect_ratio 1.0.) Target ~907 x ~2268 um core.
initialize_floorplan -utilization 70 -aspect_ratio 2.5 -core_space 10 \
    -site unit

# routing tracks (PDK tracks.info: offset 0.28, pitch 0.56; Metal5 0.45/0.90)
foreach m {Metal1 Metal2 Metal3 Metal4} {
    make_tracks $m -x_offset 0.28 -x_pitch 0.56 -y_offset 0.28 -y_pitch 0.56
}
make_tracks Metal5 -x_offset 0.45 -x_pitch 0.90 -y_offset 0.45 -y_pitch 0.90

# Well taps + endcaps BEFORE placement: DF.13/14 require a tap within
# 15 um of every FET -> 25 um pitch leaves margin (cells are tapless).
# 25 um pitch satisfies DF.13/14 mid-row (max lateral gap 12.5 um); the
# only violations were at row ENDS -> use the tap cell as endcap too, so
# every row starts and ends with a tap.
tapcell -tapcell_master lsdl_tap_11t -endcap_master lsdl_tap_11t \
        -distance 25

source ${PNR}/pdn.tcl

# ── pins on Metal3 (top/bottom edges) ──────────────────────────────────
set_io_pin_constraint -pin_names {a* an* b* bn* cin cinn c1 c2} \
    -region top:*
set_io_pin_constraint -pin_names {sum* cout coutn} -region bottom:*
place_pins -hor_layers Metal3 -ver_layers Metal2

# ── clocks ─────────────────────────────────────────────────────────────
set_wire_rc -signal -layer Metal2
set_wire_rc -clock  -layer Metal3

create_clock -name C1 -period 1.0 [get_ports c1]
create_clock -name C2 -period 1.0 -waveform {0.5 1.0} [get_ports c2]
set_input_delay  -clock C2 0.05 [get_ports {a[*] an[*] b[*] bn[*] cin cinn}]
set_output_delay -clock C1 0.10 [get_ports {sum[*] cout coutn}]

# ── placement ──────────────────────────────────────────────────────────
global_placement -density 0.7
detailed_placement
check_placement

# ── clock distribution (RTL buffer tree) ───────────────────────────────
# c1/c2 each fan out to ~8500 cell Clk pins; routed FLAT (one driver -> all
# sinks) that is ~30 pF on one net => tens-of-ns edges + ns-scale skew, which
# breaks LSDL's dynamic precharge/evaluate (the chip wouldn't run the benchmark)
# AND creates the antenna. The generator (gen_lsdl_adder.py) now emits a
# balanced lsdl_clkbuf_x1 fan-out tree (fanout<=32) on c1/c2, so the clock
# buffers are ordinary netlist instances already placed with the logic above.
# (CTS is not used: the LSDL cells aren't CTS-synthesizable and OpenROAD's
# clock_tree_synthesis won't accept a custom buffer cell — RSZ-22.) Just
# propagate the clock for timing and report the resulting skew.
set_propagated_clock [all_clocks]
estimate_parasitics -placement
report_clock_skew

# ── routing ────────────────────────────────────────────────────────────
# Signals on Metal2+ only: router Via1s on cell pins would merge with the
# cells' internal via1 cuts into >0.26 unions (V1.1 exact-size rule).
set_routing_layers -signal Metal2-Metal5 -clock Metal3-Metal5
global_route -guide_file ${PNR}/route.guide -congestion_iterations 30

# ── antenna repair (diode insertion) ───────────────────────────────────
# The flat, unbuffered clock nets c1/c2 fan out to ~8500 gate sinks each across
# the 1.55 mm macro -> 407 ANT.16 (M2/M3/M4) violations on the flat KLayout
# antenna deck. Insert lsdl_antenna_11t diodes (N+/p-well diode, CORE ANTENNACELL)
# on the violating gate nets so plasma-etch charge bleeds through the diode
# instead of the gate oxide. GRT-based insertion (fast, uses global-route
# estimate) between global_route and detailed_route; detailed_route then
# finalizes incl. the diode connections. ratio_margin over-fixes a bit so the
# independent KLayout antenna deck (which gates the precheck) also passes.
# repair_antennas uses OpenROAD's GLOBAL-route antenna estimate, which is looser
# than the KLayout flat deck (the precheck gate) -> leaves ~25 residual ANT.16.
# OpenROAD has no detailed-geometry repair mode, so we over-protect instead: the
# LSDL cells' ANTENNAGATEAREA is set deliberately small (0.1 um^2) so the computed
# metal/gate ratio is large -> repair flags + diode-protects more gate nets,
# covering the GRT-vs-flat gap. ratio_margin 50 adds further over-fix. The clock
# tree's reduced base antenna leaves placement room for the extra diodes.
# NOTE (0.5x1 reharden): the blunt GRT over-protection (4204 diodes) cannot
# legalize at 70% util in the narrow core (DPL-0036: ~96 logic cells displaced
# past the legalizer near bit 56). Antenna is now closed AFTER this run by the
# surgical filler-swap step (insert_diodes_fillerswap.tcl) which drops diodes
# into existing fill_11t_4 slots without displacing any logic -> legal at any
# utilization. So no repair_antennas here.
# repair_antennas lsdl_antenna_11t -iterations 2 -ratio_margin 50
detailed_route -output_drc ${PNR}/route_drc.rpt

# ── timing ─────────────────────────────────────────────────────────────
estimate_parasitics -global_routing
puts "================ post-route timing (1 GHz) ================"
report_checks -path_delay max -fields {capacitance slew}
report_checks -path_delay min
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS: [total_negative_slack -max]"

# row filling (DRC continuity: wells/implants/rails between cells)
filler_placement {lsdl_fill_11t_4 lsdl_fill_11t_2 lsdl_fill_11t_1}
check_placement

write_def ${PNR}/lsdl_adder64.def
write_db  ${PNR}/lsdl_adder64.odb
puts "DONE — wrote lsdl_adder64.def + .odb"
exit
