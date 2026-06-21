# pdn.tcl — power grid for the LSDL adder macro.
# Row rails: Metal1 follow-pins 0.48 um (matches lsdl_* rail geometry).
# Mesh: Metal4 vertical + Metal5 horizontal straps.

add_global_connection -net VPWR -pin_pattern {^VPWR$} -power
add_global_connection -net VGND -pin_pattern {^VGND$} -ground
global_connect
set_voltage_domain -name CORE -power VPWR -ground VGND

define_pdn_grid -name lsdl_grid -voltage_domains CORE
# Followpins on Metal2 ONLY. The physical M1 rails are drawn inside every
# cell, and each cell's internal rail vias bond M1<->M2 — so the mesh can
# hook at M2. PDN via1 stacks at rail/strap crossings would otherwise merge
# with cell-internal via1 cuts into >0.26 unions (V1.1/V1.2a, ~15k hits).
add_pdn_stripe -grid lsdl_grid -layer Metal2 -width 0.48 -followpins
add_pdn_stripe -grid lsdl_grid -layer Metal4 -width 1.6 -pitch 75.0 -offset 13.57
add_pdn_stripe -grid lsdl_grid -layer Metal5 -width 1.6 -pitch 75.6 -offset 13.5

add_pdn_connect -grid lsdl_grid -layers {Metal2 Metal4}
add_pdn_connect -grid lsdl_grid -layers {Metal4 Metal5}

pdngen
