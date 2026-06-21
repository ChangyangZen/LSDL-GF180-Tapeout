// tb_tester_cmos.v — end-to-end: adder_tester driving the REAL
// cmos_adder64 netlist (stock gf180mcu_fd_sc_mcu9t5v0 verilog models).
//
//   iverilog -g2005 -DFUNCTIONAL -o tb_cmos.vvp \
//       tb_tester_cmos.v adder_tester.v ../adder64_cmos.v \
//       $PDK/verilog/gf180mcu_fd_sc_mcu9t5v0.v && vvp tb_cmos.vvp
//
// Pass criterion: correct=1, incorrect=0 by the end of loop 2.
// With +corrupt the testbench drives a wrong cin so the result stream
// mismatches: expect incorrect=1 (negative control).

`timescale 1ns/1ps

module tb_tester_cmos;

    reg c1 = 0;
    always #1.0 c1 = ~c1;            // 500 MHz functional sim clock

    wire [63:0] a, b;
    wire cin;
    wire [64:0] result;
    wire correct, incorrect;

    reg corrupt = 0;
    wire cin_eff = cin ^ corrupt;    // negative control: flip cin

    adder_tester u_tester (
        .c1(c1), .c2(1'b0), .result(result),
        .a(a), .b(b), .cin(cin),
        .correct(correct), .incorrect(incorrect)
    );

    cmos_adder64 u_dut (
        .clk(c1), .a(a), .b(b), .cin(cin_eff),
        .sum(result[63:0]), .cout(result[64])
    );

    // Silicon self-heals from any power-up state; simulation needs the
    // Johnson counter X-state broken once.
    initial begin
        force u_tester.jc = 3'b000;
        #10 release u_tester.jc;
    end

    initial begin
        if ($test$plusargs("corrupt")) corrupt = 1;
        // two full loops: 2 * 10 vectors * 96 cycles * 2ns = 3.84 us
        #4000;
        $display("RESULT correct=%b incorrect=%b", correct, incorrect);
        if (!corrupt && correct === 1'b1 && incorrect === 1'b0)
            $display("TB PASS");
        else if (corrupt && incorrect === 1'b1)
            $display("TB PASS (negative control)");
        else
            $display("TB FAIL");
        $finish;
    end

endmodule
