# run_pnr_tester.tcl — OpenROAD PnR of the adder tester macro (stock 9T).
# Demonstrates that repair_design/repair_timing close the fanout paths the
# raw Yosys netlist could not (see tester/README.md).
# Run:  openroad -no_init -exit run_pnr_tester.tcl

set DIR  /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder
set PNR  ${DIR}/pnr
set SCL  /soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0

read_lef ${SCL}/techlef/gf180mcu_fd_sc_mcu9t5v0__nom.tlef
read_lef ${SCL}/lef/gf180mcu_fd_sc_mcu9t5v0.lef
read_liberty ${SCL}/lib/gf180mcu_fd_sc_mcu9t5v0__tt_025C_5v00.lib

read_verilog ${DIR}/tester/tester_netlist.v
link_design adder_tester

initialize_floorplan -utilization 50 -aspect_ratio 1.0 -core_space 10 \
    -site GF018hv5v_green_sc9

foreach m {Metal1 Metal2 Metal3 Metal4} {
    make_tracks $m -x_offset 0.28 -x_pitch 0.56 -y_offset 0.28 -y_pitch 0.56
}
make_tracks Metal5 -x_offset 0.45 -x_pitch 0.90 -y_offset 0.45 -y_pitch 0.90

add_global_connection -net VDD -pin_pattern {^VDD$} -power
add_global_connection -net VSS -pin_pattern {^VSS$} -ground
global_connect
set_voltage_domain -name CORE -power VDD -ground VSS
define_pdn_grid -name tgrid -voltage_domains CORE
add_pdn_stripe -grid tgrid -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid tgrid -layer Metal4 -width 1.6 -pitch 50.0 -offset 12.0
add_pdn_connect -grid tgrid -layers {Metal1 Metal4}
pdngen

place_pins -hor_layers Metal3 -ver_layers Metal2

set_wire_rc -signal -layer Metal2
set_wire_rc -clock  -layer Metal3

create_clock -name C1 -period 0.9 [get_ports c1]
set_input_delay  -clock C1 0.10 [get_ports {result[*] c2}]
set_output_delay -clock C1 0.10 [all_outputs]

# Tick-gated FSM registers get DIV=6 cycles; Johnson divider is full-rate.
set all_regs [get_cells -filter "ref_name == gf180mcu_fd_sc_mcu9t5v0__dffq_1"]
set_multicycle_path -setup 6 -to $all_regs
set_multicycle_path -hold  5 -to $all_regs
# I/O: result sampled once per 6 ticks; LEDs are quasi-static.
set_multicycle_path -setup 6 -from [get_ports {result[*]}]
set_multicycle_path -hold  5 -from [get_ports {result[*]}]
set_multicycle_path -setup 6 -to [all_outputs]
set_multicycle_path -hold  5 -to [all_outputs]

global_placement -density 0.6
# THE step Yosys lacks: buffer high-fanout nets + size cells.
repair_design
detailed_placement

repair_clock_inverters
clock_tree_synthesis -buf_list {gf180mcu_fd_sc_mcu9t5v0__clkbuf_2 gf180mcu_fd_sc_mcu9t5v0__clkbuf_4 gf180mcu_fd_sc_mcu9t5v0__clkbuf_8} \
    -root_buf gf180mcu_fd_sc_mcu9t5v0__clkbuf_16
set_propagated_clock [all_clocks]
detailed_placement

global_route -congestion_iterations 30
estimate_parasitics -global_routing
repair_timing -setup
repair_timing -hold
detailed_placement
global_route -congestion_iterations 30
detailed_route -output_drc ${PNR}/route_drc_tester.rpt

estimate_parasitics -global_routing
puts "================ tester post-route timing (0.9 ns / 1.11 GHz) ================"
report_checks -path_delay max -fields {capacitance slew}
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS: [total_negative_slack -max]"

write_def ${PNR}/adder_tester.def
puts "DONE — wrote adder_tester.def"
exit
