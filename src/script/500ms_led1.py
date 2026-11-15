# src/script/500ms_led1.py

# pinout
# CLK -- A9
# LD1 -- A29

# logic
# clock: 3.33 MHz
# led: active high
# LD1 toggles every 500 ms

"""
module lp1k_led1_500ms (
    input  wire CLK,
    output reg  LD1 = 1'b0
);
    localparam [20:0] HALF = 21'd1666666;

    reg [20:0] cnt = 21'd0;

    always @(posedge CLK) begin
        if (cnt == HALF - 21'd1) begin
            cnt <= 21'd0;
            LD1 <= ~LD1;
        end else begin
            cnt <= cnt + 21'd1;
        end
    end
endmodule
"""