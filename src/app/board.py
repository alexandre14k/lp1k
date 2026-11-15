# src/app/board.py

class AppBoard:
    name = "iCEblink40-LP1K"
    chip = "iCE40-LP1K-QN84"
    package = "qn84"
    clk_hz = 3333333
    usb_vid = 0x1443
    usb_pid = 0x0007
    flash_size = 131072
    pin_map = {}
    board_fmt_mhz = "{:.3f}"

    def board_resolve(self, label):
        key = label.strip()
        return self.pin_map.get(key.upper(), key)

    def board_clk_mhz(self):
        return self.board_fmt_mhz.format(self.clk_hz / 1000000.0)