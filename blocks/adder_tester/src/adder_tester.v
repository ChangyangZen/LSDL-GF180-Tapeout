// adder_tester.v — identical go/no-go tester for the 64-bit adder pair.
//
// One module serves both adders (user spec: "completely same tester,
// just copy and paste"):
//   * LSDL instance: 5 pins (c1, c2, result, correct, incorrect).
//     c2 is consumed by the LSDL adder, not the tester core.
//   * CMOS instance: leave c2 unconnected (4-pin flavor).
//
// Operation: drives a fixed sequence of 10 numbers (vectors.vh).
// The tester FSM runs on c1 internally divided by 6 (DIV ticks).
// Each vector is held 16 ticks = 96 c1 cycles:
//   tick  0 : apply vector (registered -> adder sees it cycle 1)
//   tick 11 : sample result — cycle 66, the result's exact first
//             arrival in BOTH flavors (apply 1 + 65 pipeline; LSDL
//             2W+2 half-cycles = CMOS W+1 cycles). Exact-arrival
//             sampling catches at-speed corruption; a settled-only
//             check would mask CMOS setup failures.
//   tick 12 : compare, accumulate
//   tick 15 : advance vector; after the last: refresh LED outputs
// LEDs: correct = all 10 passed in the loop (refreshed each loop),
// incorrect = at least one mismatch. No reset pin — first loop after
// power-up is garbage; LEDs are valid from the second loop (< 2 us
// at 1 GHz) and refreshed continuously.

`timescale 1ns/1ps

module adder_tester (
    input  wire        c1,        // clock 1 — tester + both adders
    input  wire        c2,        // clock 2 — forwarded to LSDL adder only
    input  wire [64:0] result,    // adder output {cout, sum[63:0]}
    output reg  [63:0] a,         // operand drive to the adder
    output reg  [63:0] b,
    output reg         cin,
    output reg         correct,   // LED: sequence passed
    output reg         incorrect  // LED: sequence failed
);

`include "vectors.vh"

    localparam DIV = 6;
    localparam HOLD_TICKS = 16;
    localparam SAMPLE_TICK = 11;   // 11 * 6 = 66 = exact result arrival

    // unused inside the tester core (kept so both instances are the
    // same netlist; the LSDL adder consumes it externally)
    wire c2_nc = c2;

    // ÷6 as a 3-stage Johnson counter: one inverter between flops, so the
    // full-rate path stays flop-limited. High-drive dffq_4, instantiated
    // directly so synthesis cannot downsize. Self-starting: any power-up
    // state converges to the 6-state ring (000->100->110->111->011->001).
    // There is no reset pin; tester output is valid from the second loop.
    wire [2:0] jc;
    wire jc2_n;
    gf180mcu_fd_sc_mcu9t5v0__inv_4  u_jinv  (.I(jc[2]), .ZN(jc2_n));
    gf180mcu_fd_sc_mcu9t5v0__dffq_4 u_ring0 (.CLK(c1), .D(jc2_n), .Q(jc[0]));
    gf180mcu_fd_sc_mcu9t5v0__dffq_4 u_ring1 (.CLK(c1), .D(jc[0]), .Q(jc[1]));
    gf180mcu_fd_sc_mcu9t5v0__dffq_4 u_ring2 (.CLK(c1), .D(jc[1]), .Q(jc[2]));
    wire tick_pre = jc[0] & ~jc[1];   // one cycle per 6: state 100 only

    reg [3:0] tick_cnt = 0;

    // Registered, replicated tick for the control counters.
    (* keep *) reg [1:0] tick_q;
    always @(posedge c1)
        tick_q <= {2{tick_pre}};

    // Datapath enables are fully decoded one cycle early and registered
    // with replication: each copy drives at most ~32 register enables, so
    // no enable net fans out wide (the synthesizer does not buffer them).
    (* keep *) reg [7:0] apply_en;
    (* keep *) reg [3:0] sample_en;
    (* keep *) reg       accum_en;
    always @(posedge c1) begin
        apply_en  <= {8{tick_pre & (tick_cnt == 4'd0)}};
        sample_en <= {4{tick_pre & (tick_cnt == SAMPLE_TICK)}};
        accum_en  <=    tick_pre & (tick_cnt == SAMPLE_TICK + 1);
    end

    // Vector select: 4 replicated binary counters (self-wrapping from any
    // power-up state) decoded to one-hot and REGISTERED per 32-bit mux
    // group, so every select wire drives at most ~32 AND-OR loads and no
    // decode gate sees a fanout hot spot. No reset needed anywhere.
    reg [3:0] vc_a = 0, vc_b = 0, vc_c = 0, vc_d = 0;
    (* keep *) reg [9:0] oh_a = 1, oh_a2 = 1, oh_b = 1, oh_b2 = 1,
                         oh_c = 1, oh_c2 = 1, oh_d = 1;
    genvar gi;
    generate
        for (gi = 0; gi < 10; gi = gi + 1) begin : g_dec
            always @(posedge c1) begin
                oh_a [gi] <= (vc_a == gi);
                oh_a2[gi] <= (vc_a == gi);
                oh_b [gi] <= (vc_b == gi);
                oh_b2[gi] <= (vc_b == gi);
                oh_c [gi] <= (vc_c == gi);
                oh_c2[gi] <= (vc_c == gi);
                oh_d [gi] <= (vc_d == gi);
            end
        end
    endgenerate

    wire [63:0] a_mux;
    assign a_mux[31:0] =
        ({32{oh_a[0]}} & A0[31:0]) | ({32{oh_a[1]}} & A1[31:0]) |
        ({32{oh_a[2]}} & A2[31:0]) | ({32{oh_a[3]}} & A3[31:0]) |
        ({32{oh_a[4]}} & A4[31:0]) | ({32{oh_a[5]}} & A5[31:0]) |
        ({32{oh_a[6]}} & A6[31:0]) | ({32{oh_a[7]}} & A7[31:0]) |
        ({32{oh_a[8]}} & A8[31:0]) | ({32{oh_a[9]}} & A9[31:0]);
    assign a_mux[63:32] =
        ({32{oh_a2[0]}} & A0[63:32]) | ({32{oh_a2[1]}} & A1[63:32]) |
        ({32{oh_a2[2]}} & A2[63:32]) | ({32{oh_a2[3]}} & A3[63:32]) |
        ({32{oh_a2[4]}} & A4[63:32]) | ({32{oh_a2[5]}} & A5[63:32]) |
        ({32{oh_a2[6]}} & A6[63:32]) | ({32{oh_a2[7]}} & A7[63:32]) |
        ({32{oh_a2[8]}} & A8[63:32]) | ({32{oh_a2[9]}} & A9[63:32]);
    wire [63:0] b_mux;
    assign b_mux[31:0] =
        ({32{oh_b[0]}} & B0[31:0]) | ({32{oh_b[1]}} & B1[31:0]) |
        ({32{oh_b[2]}} & B2[31:0]) | ({32{oh_b[3]}} & B3[31:0]) |
        ({32{oh_b[4]}} & B4[31:0]) | ({32{oh_b[5]}} & B5[31:0]) |
        ({32{oh_b[6]}} & B6[31:0]) | ({32{oh_b[7]}} & B7[31:0]) |
        ({32{oh_b[8]}} & B8[31:0]) | ({32{oh_b[9]}} & B9[31:0]);
    assign b_mux[63:32] =
        ({32{oh_b2[0]}} & B0[63:32]) | ({32{oh_b2[1]}} & B1[63:32]) |
        ({32{oh_b2[2]}} & B2[63:32]) | ({32{oh_b2[3]}} & B3[63:32]) |
        ({32{oh_b2[4]}} & B4[63:32]) | ({32{oh_b2[5]}} & B5[63:32]) |
        ({32{oh_b2[6]}} & B6[63:32]) | ({32{oh_b2[7]}} & B7[63:32]) |
        ({32{oh_b2[8]}} & B8[63:32]) | ({32{oh_b2[9]}} & B9[63:32]);
    wire [64:0] exp_mux;
    assign exp_mux[31:0] =
        ({32{oh_c[0]}} & EXP0[31:0]) | ({32{oh_c[1]}} & EXP1[31:0]) |
        ({32{oh_c[2]}} & EXP2[31:0]) | ({32{oh_c[3]}} & EXP3[31:0]) |
        ({32{oh_c[4]}} & EXP4[31:0]) | ({32{oh_c[5]}} & EXP5[31:0]) |
        ({32{oh_c[6]}} & EXP6[31:0]) | ({32{oh_c[7]}} & EXP7[31:0]) |
        ({32{oh_c[8]}} & EXP8[31:0]) | ({32{oh_c[9]}} & EXP9[31:0]);
    assign exp_mux[64:32] =
        ({33{oh_c2[0]}} & EXP0[64:32]) | ({33{oh_c2[1]}} & EXP1[64:32]) |
        ({33{oh_c2[2]}} & EXP2[64:32]) | ({33{oh_c2[3]}} & EXP3[64:32]) |
        ({33{oh_c2[4]}} & EXP4[64:32]) | ({33{oh_c2[5]}} & EXP5[64:32]) |
        ({33{oh_c2[6]}} & EXP6[64:32]) | ({33{oh_c2[7]}} & EXP7[64:32]) |
        ({33{oh_c2[8]}} & EXP8[64:32]) | ({33{oh_c2[9]}} & EXP9[64:32]);
    wire cin_mux =
        (oh_d[0] & CIN0) | (oh_d[1] & CIN1) | (oh_d[2] & CIN2) |
        (oh_d[3] & CIN3) | (oh_d[4] & CIN4) | (oh_d[5] & CIN5) |
        (oh_d[6] & CIN6) | (oh_d[7] & CIN7) | (oh_d[8] & CIN8) |
        (oh_d[9] & CIN9);

    reg [64:0] sampled, expected;
    reg pass_acc;

    // Control: counters, accumulator, LEDs            (~16 loads on tick_q)
    always @(posedge c1) begin
        if (tick_q[0])
            tick_cnt <= (tick_cnt == HOLD_TICKS - 1) ? 4'd0 : tick_cnt + 4'd1;
        if (accum_en)
            pass_acc <= pass_acc & (sampled == expected);
        if (tick_q[1] & (tick_cnt == HOLD_TICKS - 1)) begin
            if (vc_d >= N_VEC - 1) begin
                correct   <=  pass_acc;
                incorrect <= ~pass_acc;
                pass_acc  <= 1'b1;
            end
            vc_a <= (vc_a >= N_VEC - 1) ? 4'd0 : vc_a + 4'd1;
            vc_b <= (vc_b >= N_VEC - 1) ? 4'd0 : vc_b + 4'd1;
            vc_c <= (vc_c >= N_VEC - 1) ? 4'd0 : vc_c + 4'd1;
            vc_d <= (vc_d >= N_VEC - 1) ? 4'd0 : vc_d + 4'd1;
        end
    end

    // Operand apply: one pre-registered enable copy per 32-bit group.
    always @(posedge c1) begin
        if (apply_en[0]) a[31:0]  <= a_mux[31:0];
        if (apply_en[1]) a[63:32] <= a_mux[63:32];
        if (apply_en[2]) b[31:0]  <= b_mux[31:0];
        if (apply_en[3]) b[63:32] <= b_mux[63:32];
        if (apply_en[4]) begin cin <= cin_mux; expected[31:0] <= exp_mux[31:0]; end
        if (apply_en[5]) expected[64:32] <= exp_mux[64:32];
    end

    // Result sampling at exact first arrival, 32 bits per enable copy.
    always @(posedge c1) begin
        if (sample_en[0]) sampled[31:0]  <= result[31:0];
        if (sample_en[1]) sampled[64:32] <= result[64:32];
    end

endmodule
