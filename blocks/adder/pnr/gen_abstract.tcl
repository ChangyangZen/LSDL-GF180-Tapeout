# gen_abstract.tcl — generate a block-level abstract LEF for a hardened macro
# from its routed DEF, for integration as a macro in the wafer.space template.
# Emits an abstract LEF (outline, signal pins, PG pins, over-cell metal
# obstructions) so the top-level router treats the macro as a hard black box.
#
# Run (in the IIC-OSIC-TOOLS container), inputs via env vars:
#   AB_TECHLEF=... AB_CELLLEF=... AB_DEF=... AB_OUTLEF=... \
#     openroad -no_init -exit gen_abstract.tcl

# AB_LEFS = space-separated list of LEF files (tech first, then cell/support).
# (Back-compat: AB_TECHLEF + AB_CELLLEF still honored if AB_LEFS unset.)
if { [info exists ::env(AB_LEFS)] } {
    foreach lef $::env(AB_LEFS) { read_lef $lef }
} else {
    read_lef $::env(AB_TECHLEF)
    read_lef $::env(AB_CELLLEF)
}
read_def $::env(AB_DEF)

# write_abstract_lef pulls pin geometry from the DEF PINS section and bloats
# over-cell routing into obstructions so the macro is opaque to the top router.
write_abstract_lef $::env(AB_OUTLEF)

puts "DONE — wrote abstract LEF $::env(AB_OUTLEF)"
exit
