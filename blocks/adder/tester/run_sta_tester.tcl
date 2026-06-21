# run_sta_tester.tcl — tester timing at 1.25 GHz external clock.
# Full-rate paths: clock divider + tick distribution into FSM enables.
# FSM register-to-register work happens once per DIV=6 ticks -> multicycle 6/5.
# Divider next-state stays single-cycle.

set dir /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder/tester

read_liberty /soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/lib/gf180mcu_fd_sc_mcu9t5v0__tt_025C_5v00.lib
read_verilog ${dir}/tester_netlist.v
link_design adder_tester

create_clock -name C1 -period 0.9 [get_ports c1]
set_input_delay  -clock C1 0.1 [get_ports {result[*] c2}]
set_output_delay -clock C1 0.1 [all_outputs]

# Tick-gated FSM registers: 6 cycles between active edges.
set all_regs [get_cells -filter "ref_name == gf180mcu_fd_sc_mcu9t5v0__dffq_1"]
set_multicycle_path -setup 6 -to $all_regs
set_multicycle_path -hold  5 -to $all_regs

# Divider flops run full-rate: the 3-stage Johnson counter (named insts).
set div_regs [get_cells {u_ring0 u_ring1 u_ring2}]
set_multicycle_path -setup 1 -to $div_regs
set_multicycle_path -hold  0 -to $div_regs

puts "=== worst full-rate divider path ==="
report_checks -path_delay max -to $div_regs

puts "=== worst path (FSM multicycle applied) ==="
report_checks -path_delay max

puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
exit
