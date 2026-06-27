# run_pnr.tcl — OpenROAD PnR of the LSDL 32-bit priority encoder macro (rev: simple).
# 570 LSDL cells (signed-off NOR4/NAND4/INV..) on the 11-track unit site.
# Reuses the adder's shared LEF/liberty/PDN. Flat c1/c2 clock (CTS deferred).
# Run:  openroad -no_init -exit run_pnr.tcl

set DIR  /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/priencoder32
set PNR  ${DIR}/pnr
set APNR /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder/pnr
set LIBD /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib

read_lef ${APNR}/gf180mcu_lsdl.tlef
read_lef ${APNR}/lsdl_fd_sc_9t5v0.lef
read_lef ${APNR}/lsdl_support_11t.lef
read_liberty ${LIBD}/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib

read_verilog ${DIR}/priencoder32.v
link_design lsdl_priencoder32

# ── floorplan: small square, easy first route (570 cells) ──────────────
initialize_floorplan -utilization 55 -aspect_ratio 1.0 -core_space 10 -site unit
foreach m {Metal1 Metal2 Metal3 Metal4} {
    make_tracks $m -x_offset 0.28 -x_pitch 0.56 -y_offset 0.28 -y_pitch 0.56
}
make_tracks Metal5 -x_offset 0.45 -x_pitch 0.90 -y_offset 0.45 -y_pitch 0.90

# Well taps + endcaps before placement (tapless cells; DF.13/14 within 15um)
tapcell -tapcell_master lsdl_tap_11t -endcap_master lsdl_tap_11t -distance 25
source ${APNR}/pdn.tcl

# ── IO pins ────────────────────────────────────────────────────────────
set_io_pin_constraint -pin_names {req* c1 c2} -region top:*
set_io_pin_constraint -pin_names {vld pos*}   -region bottom:*
place_pins -hor_layers Metal3 -ver_layers Metal2

# ── clocks (flat c1/c2) ────────────────────────────────────────────────
set_wire_rc -signal -layer Metal2
set_wire_rc -clock  -layer Metal3
create_clock -name C1 -period 1.0 [get_ports c1]
create_clock -name C2 -period 1.0 -waveform {0.5 1.0} [get_ports c2]
set_input_delay  -clock C2 0.05 [get_ports {req[*]}]
set_output_delay -clock C1 0.10 [get_ports {vld pos[*]}]

# ── placement ──────────────────────────────────────────────────────────
global_placement -density 0.55
detailed_placement
check_placement
set_propagated_clock [all_clocks]
estimate_parasitics -placement
report_clock_skew

# ── routing ────────────────────────────────────────────────────────────
set_routing_layers -signal Metal2-Metal5 -clock Metal3-Metal5
global_route -guide_file ${PNR}/route.guide -congestion_iterations 30
detailed_route -output_drc ${PNR}/route_drc.rpt

estimate_parasitics -global_routing
puts "================ post-route timing ================"
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"

filler_placement {lsdl_fill_11t_4 lsdl_fill_11t_2 lsdl_fill_11t_1}
check_placement
write_def ${PNR}/lsdl_priencoder32.def
write_db  ${PNR}/lsdl_priencoder32.odb
puts "DONE — wrote lsdl_priencoder32.def + .odb"
exit
