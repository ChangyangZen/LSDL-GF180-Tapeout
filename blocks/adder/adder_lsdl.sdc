# adder_lsdl.sdc — 1 GHz two-phase clocking for the LSDL pipelined adder.
# C1 and C2 are both 1.0 ns, 50% duty, 180 deg apart (Belluomini Fig. 2a).
# Every stage-to-stage transfer (C1->C2 or C2->C1) gets one half period.

create_clock -name C1 -period 1.0 [get_ports c1]
create_clock -name C2 -period 1.0 -waveform {0.5 1.0} [get_ports c2]

# Data inputs are launched by the upstream (static-CMOS LFSR) driver on the
# C2 edge; stage-1 cells (C1) capture them a half period later.
set_input_delay -clock C2 0.05 [get_ports {a[*] an[*] b[*] bn[*] cin cinn}]

# Outputs (all launched by even/C2 stages) are captured by the static-CMOS
# capture register on the next C1 edge.
set_output_delay -clock C1 0.10 [all_outputs]
