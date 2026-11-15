# src/script/100ms_led2.py

# pinout
# CLK -- A9
# LD2 -- B20

# logic
# clock: 3.33 MHz
# led: active high
# LD2 toggles every 100 ms

"""
module lp1k_led2_100ms (
    input  wire CLK,
    output reg  LD2 = 1'b0
);
    localparam [18:0] HALF = 19'd333333;

    reg [18:0] cnt = 19'd0;

    always @(posedge CLK) begin
        if (cnt == HALF - 19'd1) begin
            cnt <= 19'd0;
            LD2 <= ~LD2;
        end else begin
            cnt <= cnt + 19'd1;
        end
    end
endmodule
"""