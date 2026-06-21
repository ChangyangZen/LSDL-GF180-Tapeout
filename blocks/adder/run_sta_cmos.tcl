# run_sta_cmos.tcl — timing closure / f_max for the matched-architecture
# CMOS systolic adder against the stock gf180mcu_fd_sc_mcu9t5v0 library.
# Usage: CMOS_PERIOD=2.0 ADDER_W=64 sta -no_init -exit run_sta_cmos.tcl

set w 64
if {[info exists ::env(ADDER_W)]} { set w $::env(ADDER_W) }
set period 2.0
if {[info exists ::env(CMOS_PERIOD)]} { set period $::env(CMOS_PERIOD) }
set dir /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder

read_liberty /soe/czeng14/software/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu9t5v0/lib/gf180mcu_fd_sc_mcu9t5v0__tt_025C_5v00.lib
read_verilog ${dir}/adder${w}_cmos.v
link_design  cmos_adder${w}

create_clock -name CLK -period $period [get_ports clk]
read_sdc ${dir}/adder_cmos.sdc

puts ""
puts "================== CMOS ADDER: SETUP (worst path @ ${period} ns) =================="
report_checks -path_delay max -fields {capacitance slew}

puts ""
puts "================== CMOS ADDER: HOLD (worst path) =================="
report_checks -path_delay min -fields {capacitance slew}

puts ""
puts "================== CMOS ADDER: SUMMARY =================="
set ws [worst_slack -max]
puts "period:            $period ns"
puts "worst setup slack: $ws"
puts "worst hold  slack: [worst_slack -min]"
puts "TNS (setup):       [total_negative_slack -max]"
puts "f_max estimate:    [expr {1.0 / ($period - $ws)}] GHz (pre-PnR, ideal clock, TT)"
exit
