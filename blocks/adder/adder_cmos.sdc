# adder_cmos.sdc — single-clock constraints for the matched-architecture
# CMOS systolic adder. Period set by CMOS_PERIOD env in run_sta_cmos.tcl
# (placeholder here; the TCL overrides via create_clock before this loads
# I/O constraints).

set_input_delay  -clock CLK 0.20 [get_ports {a[*] b[*] cin}]
set_output_delay -clock CLK 0.20 [all_outputs]
