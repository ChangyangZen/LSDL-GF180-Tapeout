// tb_tester_lsdl.v — adder_tester driving a behavioral LSDL adder64
// latency model: result = a + b + cin delayed 65 c1-cycles, matching
// lsdl_adder64 (sum[i] launched at half-cycle 2i+2; full vector valid
// 65 cycles after inputs change). Cell-true LSDL simulation is the
// gen_lsdl_adder.py selftest; this validates tester timing.
//
//   iverilog -g2005 -o tb_lsdl.vvp tb_tester_lsdl.v adder_tester.v && vvp tb_lsdl.vvp

`timescale 1ns/1ps

module lsdl_adder64_beh (
    input  wire        c1,
    input  wire        c2,
    input  wire [63:0] a,
    input  wire [63:0] b,
    input  wire        cin,
    output wire [64:0] result
);
    reg [64:0] pipe [0:64];
    integer k;
    always @(posedge c1) begin
        pipe[0] <= a + b + cin;
        for (k = 1; k <= 64; k = k + 1)
            pipe[k] <= pipe[k-1];
    end
    assign result = pipe[64];
endmodule

module tb_tester_lsdl;

    reg c1 = 0;
    always #0.5 c1 = ~c1;            // 1 GHz
    reg c2 = 0;
    initial begin #0.5; forever #0.5 c2 = ~c2; end   // 180 deg

    wire [63:0] a, b;
    wire cin;
    wire [64:0] result;
    wire correct, incorrect;

    adder_tester u_tester (
        .c1(c1), .c2(c2), .result(result),
        .a(a), .b(b), .cin(cin),
        .correct(correct), .incorrect(incorrect)
    );

    lsdl_adder64_beh u_dut (
        .c1(c1), .c2(c2), .a(a), .b(b), .cin(cin), .result(result)
    );

    // Break the Johnson counter's X state (silicon self-heals, sim can't).
    initial begin
        force u_tester.jc = 3'b000;
        #10 release u_tester.jc;
    end

    initial begin
        #2000;   // two loops at 1 GHz
        $display("RESULT correct=%b incorrect=%b", correct, incorrect);
        if (correct === 1'b1 && incorrect === 1'b0) $display("TB PASS");
        else $display("TB FAIL");
        $finish;
    end

endmodule
