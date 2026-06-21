# Macro-internal SDC for cmos_adder64. I/O are internal chip nets (no pads), so
# use SMALL FIXED I/O delays (not LibreLane's default 0.2*period, which scaled the
# 65 I/O-boundary setup paths with the clock and never closed). Relaxed 10 ns
# clock; real timing is hand-flow-validated at 500 MHz. Explicit port patterns
# (this OpenSTA lacks remove_from_collection).
create_clock -name clk -period 10.0 [get_ports clk]
set_clock_uncertainty 0.10 [get_clocks clk]
set_clock_transition  0.15 [get_clocks clk]
set_input_delay  0.20 -clock clk [get_ports {a[*] b[*] cin}]
set_output_delay 0.20 -clock clk [get_ports {sum[*] cout}]
