# run_sta_adder.tcl — G5 gate: 1 GHz timing closure on the LSDL adder.
# Usage: sta -no_init -exit run_sta_adder.tcl
# Set ADDER_W in env to 4, 16 or 64 (default 4).

set w 4
if {[info exists ::env(ADDER_W)]} { set w $::env(ADDER_W) }
set dir /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder

read_liberty /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib
read_verilog /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_inv_x1.v
read_verilog /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/cells/lsdl_basic/lsdl_aoi22_x1.v
read_verilog ${dir}/adder${w}_lsdl.v
link_design  lsdl_adder${w}

read_sdc ${dir}/adder_lsdl.sdc

puts ""
puts "================== G5: SETUP (worst path, 1 GHz) =================="
report_checks -path_delay max -fields {capacitance slew} -group_path_count 4

puts ""
puts "================== G5: HOLD (worst path) =================="
report_checks -path_delay min -fields {capacitance slew}

puts ""
puts "================== G5: WORST SLACK SUMMARY =================="
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS (setup):       [total_negative_slack -max]"

puts ""
puts "================== G5 DONE =================="
exit
