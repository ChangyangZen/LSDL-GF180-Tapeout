# Lean jumper-only antenna repair, resume from routed odb. No standalone
# check_antennas (slow ~30min on the flat 16,832-sink clock nets) — repair runs
# its own internal check; verify the result via the fast KLayout antenna deck on
# the re-streamed GDS. No diode cell needed (-jumper_only).
set PNR /mada/users/czeng14/projects/brainstorm/domino/lsdl_lib/blocks/adder/pnr
read_db ${PNR}/lsdl_adder64.odb
puts "=== repair_antennas jumper-only (iterations 1) ==="
repair_antennas -jumper_only -iterations 1
puts "=== writing antfix DEF/DB ==="
write_def ${PNR}/lsdl_adder64_antfix.def
write_db  ${PNR}/lsdl_adder64_antfix.odb
puts "DONE antenna_fix"
