// lsdl_adder_wrap.v — LSDL adder64 + dual-rail boundary.
//
// The tester is single-rail (identical for LSDL and CMOS). The LSDL
// adder needs complement operand rails; those inverters live HERE, not
// in the tester, so the two tester instances stay gate-identical.
// 129 inverters (a[63:0], b[63:0], cin) synthesize to stock CMOS
// inv_1 cells in the always-on tester domain.

`timescale 1ns/1ps

module lsdl_adder_wrap (
    input  wire        c1,
    input  wire        c2,
    input  wire [63:0] a,
    input  wire [63:0] b,
    input  wire        cin,
    output wire [64:0] result    // {cout, sum}
);

    wire [63:0] an = ~a;
    wire [63:0] bn = ~b;
    wire        cinn = ~cin;
    wire        coutn_nc;

    lsdl_adder64 u_core (
        .c1   (c1),
        .c2   (c2),
        .a    (a),
        .an   (an),
        .b    (b),
        .bn   (bn),
        .cin  (cin),
        .cinn (cinn),
        .sum  (result[63:0]),
        .cout (result[64]),
        .coutn(coutn_nc)
    );

endmodule
