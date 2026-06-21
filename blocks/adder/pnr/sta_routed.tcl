set PNR /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder/pnr
read_lef ${PNR}/gf180mcu_lsdl.tlef
read_lef ${PNR}/lsdl_fd_sc_9t5v0.lef
read_liberty /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/lib/lsdl_fd_sc_9t5v0__tt_5v_25c.lib
read_def ${PNR}/lsdl_adder64.def
set_wire_rc -signal -layer Metal2
set_wire_rc -clock  -layer Metal3
create_clock -name C1 -period 1.0 [get_ports c1]
create_clock -name C2 -period 1.0 -waveform {0.5 1.0} [get_ports c2]
set_input_delay  -clock C2 0.05 [get_ports {a[*] an[*] b[*] bn[*] cin cinn}]
set_output_delay -clock C1 0.10 [get_ports {sum[*] cout coutn}]
estimate_parasitics -placement
puts "worst setup slack: [worst_slack -max]"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS: [total_negative_slack -max]"
exit
