// SPDX-FileCopyrightText: © 2025 LSDL Tapeout Authors
// SPDX-License-Identifier: Apache-2.0
//
// Phase B (TPL-4): the 64-bit adder pair benchmark.
//   - u_lsdl_adder64  (LSDL, dual-rail, C1/C2)  driven+checked by u_tester_lsdl
//   - u_cmos_adder64  (matched static-CMOS)      driven+checked by u_tester_cmos
// Identical tester macro per adder (TST spec). Each tester drives operands a/b/cin
// into its adder and samples {cout,sum} back as `result`, lighting correct/incorrect
// LEDs. The LSDL adder's complement rails (an/bn/cinn) are made by inverters here
// (synthesizable glue) — LSDL needs both polarities; CMOS is single-rail.

`default_nettype none

module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
    `ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
    `endif

    input  wire clk,       // clock 1 (C1) — tester + both adders
    input  wire rst_n,     // reset (active low) — registers the LED outputs

    input  wire [NUM_INPUT_PADS-1:0] input_in,
    output wire [NUM_INPUT_PADS-1:0] input_pu,
    output wire [NUM_INPUT_PADS-1:0] input_pd,

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,

    inout  wire [NUM_ANALOG_PADS-1:0] analog
);

    // ── pad static config ────────────────────────────────────────────────
    assign input_pu = '0;
    assign input_pd = '0;
    assign bidir_cs = '0;
    assign bidir_sl = '0;
    assign bidir_pu = '0;
    assign bidir_pd = '0;
    assign bidir_oe = '1;            // all bidir as outputs
    assign bidir_ie = ~bidir_oe;

    // ── two clock phases ─────────────────────────────────────────────────
    // C1 = chip clock; C2 = second phase from an input pad (Phase C: on-chip clkgen).
    wire c1 = clk;
    wire c2 = input_in[0];

    // ══ LSDL adder + its tester ══════════════════════════════════════════
    wire [63:0] l_a, l_b;
    wire        l_cin;
    wire [63:0] l_sum;
    wire        l_cout, l_coutn;
    wire        l_correct, l_incorrect;
    // dual-rail complements (inverter glue): LSDL needs both polarities.
    wire [63:0] l_an  = ~l_a;
    wire [63:0] l_bn  = ~l_b;
    wire        l_cinn = ~l_cin;
    wire [64:0] l_result = {l_cout, l_sum};

    adder_tester u_tester_lsdl (
        `ifdef USE_POWER_PINS .VDD(VDD), .VSS(VSS), `endif
        .c1(c1), .c2(c2), .result(l_result),
        .a(l_a), .b(l_b), .cin(l_cin),
        .correct(l_correct), .incorrect(l_incorrect)
    );
    lsdl_adder64 u_lsdl_adder64 (
        `ifdef USE_POWER_PINS .VPWR(VDD), .VGND(VSS), `endif
        .c1(c1), .c2(c2),
        .a(l_a), .an(l_an), .b(l_b), .bn(l_bn),
        .cin(l_cin), .cinn(l_cinn),
        .sum(l_sum), .cout(l_cout), .coutn(l_coutn)
    );

    // ══ CMOS adder + its tester ══════════════════════════════════════════
    wire [63:0] c_a, c_b;
    wire        c_cin;
    wire [63:0] c_sum;
    wire        c_cout;
    wire        c_correct, c_incorrect;
    wire [64:0] c_result = {c_cout, c_sum};

    adder_tester u_tester_cmos (
        `ifdef USE_POWER_PINS .VDD(VDD), .VSS(VSS), `endif
        .c1(c1), .c2(c2), .result(c_result),
        .a(c_a), .b(c_b), .cin(c_cin),
        .correct(c_correct), .incorrect(c_incorrect)
    );
    cmos_adder64 u_cmos_adder64 (
        `ifdef USE_POWER_PINS .VDD(VDD), .VSS(VSS), `endif
        .clk(c1), .a(c_a), .b(c_b), .cin(c_cin),
        .sum(c_sum), .cout(c_cout)
    );

    // ── registered go/no-go LEDs (uses clk + rst_n so both pads stay live) ─
    logic l_correct_q, l_incorrect_q, c_correct_q, c_incorrect_q;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            l_correct_q <= 1'b0; l_incorrect_q <= 1'b0;
            c_correct_q <= 1'b0; c_incorrect_q <= 1'b0;
        end else begin
            l_correct_q <= l_correct; l_incorrect_q <= l_incorrect;
            c_correct_q <= c_correct; c_incorrect_q <= c_incorrect;
        end
    end

    // bidir[0]=LSDL correct, [1]=LSDL incorrect, [2]=CMOS correct, [3]=CMOS incorrect
    assign bidir_out = { {(NUM_BIDIR_PADS-4){1'b0}},
                         c_incorrect_q, c_correct_q, l_incorrect_q, l_correct_q };

    // consume unused inputs
    logic _unused;
    assign _unused = &{bidir_in, input_in[NUM_INPUT_PADS-1:1], 1'b0};

endmodule

`default_nettype wire
