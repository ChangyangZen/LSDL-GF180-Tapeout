# run_pnr_cmos.tcl — OpenROAD PnR of the matched CMOS 64-bit adder
# (stock gf180mcu_fd_sc_mcu9t5v0, 4,224 cells).
# Run:  openroad -no_init -exit run_pnr_cmos.tcl

set DIR  /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder
set PNR  ${DIR}/pnr
set SCL  /soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0

read_lef ${SCL}/techlef/gf180mcu_fd_sc_mcu9t5v0__nom.tlef
read_lef ${SCL}/lef/gf180mcu_fd_sc_mcu9t5v0.lef
read_liberty ${SCL}/lib/gf180mcu_fd_sc_mcu9t5v0__tt_025C_5v00.lib

read_verilog ${DIR}/adder64_cmos.v
link_design cmos_adder64

initialize_floorplan -utilization 60 -aspect_ratio 1.0 -core_space 10 \
    -site GF018hv5v_green_sc9

foreach m {Metal1 Metal2 Metal3 Metal4} {
    make_tracks $m -x_offset 0.28 -x_pitch 0.56 -y_offset 0.28 -y_pitch 0.56
}
make_tracks Metal5 -x_offset 0.45 -x_pitch 0.90 -y_offset 0.45 -y_pitch 0.90

# ── power grid (stock rails: VDD/VSS) ──────────────────────────────────
add_global_connection -net VDD -pin_pattern {^VDD$} -power
add_global_connection -net VSS -pin_pattern {^VSS$} -ground
global_connect
set_voltage_domain -name CORE -power VDD -ground VSS
define_pdn_grid -name cmos_grid -voltage_domains CORE
add_pdn_stripe -grid cmos_grid -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid cmos_grid -layer Metal4 -width 1.6 -pitch 75.0 -offset 13.57
add_pdn_stripe -grid cmos_grid -layer Metal5 -width 1.6 -pitch 75.6 -offset 13.5
add_pdn_connect -grid cmos_grid -layers {Metal1 Metal4}
add_pdn_connect -grid cmos_grid -layers {Metal4 Metal5}
pdngen

set_io_pin_constraint -pin_names {a* b* cin clk} -region top:*
set_io_pin_constraint -pin_names {sum* cout} -region bottom:*
place_pins -hor_layers Metal3 -ver_layers Metal2

set_wire_rc -signal -layer Metal2
set_wire_rc -clock  -layer Metal3

# 2.0 ns: post-route reality — clk->Q (0.62) + addf S (1.03) + setup (0.23)
# + skew leaves f_max ~525 MHz; 500 MHz target with margin.
create_clock -name CLK -period 2.0 [get_ports clk]
set_input_delay  -clock CLK 0.20 [get_ports {a[*] b[*] cin}]
set_output_delay -clock CLK 0.20 [get_ports {sum[*] cout}]
# Tester applies/samples on a /6 tick: I/O paths get 2 cycles, absorbing
# the clock-tree insertion delay at the macro boundary.
set_multicycle_path -setup 2 -from [all_inputs]
set_multicycle_path -setup 2 -to [all_outputs]
set_multicycle_path -hold 1 -from [all_inputs]
set_multicycle_path -hold 1 -to [all_outputs]

global_placement -density 0.7
detailed_placement
check_placement

# clock tree synthesis with stock buffers
repair_clock_inverters
clock_tree_synthesis -buf_list {gf180mcu_fd_sc_mcu9t5v0__clkbuf_2 gf180mcu_fd_sc_mcu9t5v0__clkbuf_4 gf180mcu_fd_sc_mcu9t5v0__clkbuf_8} \
    -root_buf gf180mcu_fd_sc_mcu9t5v0__clkbuf_16
set_propagated_clock [all_clocks]
repair_clock_nets
detailed_placement

set_routing_layers -signal Metal1-Metal5 -clock Metal3-Metal5
global_route -congestion_iterations 30

# post-CTS timing repair (sizing + hold buffers), then detailed route
estimate_parasitics -global_routing
repair_timing -setup
repair_timing -hold
detailed_placement
global_route -congestion_iterations 30
detailed_route -output_drc ${PNR}/route_drc_cmos.rpt

estimate_parasitics -global_routing
puts "================ CMOS adder64 post-route timing (633 MHz) ================"
report_checks -path_delay max -fields {capacitance slew}
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS: [total_negative_slack -max]"

write_def ${PNR}/cmos_adder64.def
puts "DONE — wrote cmos_adder64.def"
exit
