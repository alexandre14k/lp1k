# src/app/adept.py

import struct
import time

from app.usbdev import *


class AppAdept:
    adept_timeout_ms = 2000
    adept_settle_s = 0.0
    adept_hold_s = 0.05
    adept_spi_hz = 2000000
    adept_recv_size = 64
    adept_txn_max = 256
    adept_fill = 0xFF
    adept_keep_hold = False
    adept_hold_fpga = True
    adept_sub_gpio = 0x03
    adept_sub_spi = 0x06
    adept_op_gpio_open = 0x00
    adept_op_gpio_dir = 0x04
    adept_op_gpio_val = 0x06
    adept_op_spi_open = 0x00
    adept_op_spi_close = 0x01
    adept_op_spi_speed = 0x03
    adept_op_spi_mode = 0x05
    adept_op_spi_cs = 0x06
    adept_op_spi_io = 0x07
    adept_op_spi_end = 0x87
    adept_flag_wr = 0x80
    adept_flag_rd = 0x40
    adept_empty = ""
    adept_sep_hex = " "
    adept_fmt_hex = "{:02x}"
    adept_fmt_u32 = "<I"
    adept_fmt_pending = "0x{:02x}:[{}]"
    adept_err_short = "adept short reply"
    adept_fmt_status = "adept status 0x{:02x} rx=[{}] pending: {}"
    adept_fmt_short_end = "adept short io end [{}]"
    adept_fmt_io_end = "adept io end wr={} rd={} want {} rx=[{}]"
    adept_err_rx_len = "spi rx length mismatch"
    adept_fmt_range = "spi transaction of {} bytes out of range"

    def __init__(self, usb):
        self.usb = usb
        self.adept_held = False

    def adept_hex(self, data):
        return self.adept_sep_hex.join(
            self.adept_fmt_hex.format(b) for b in data
        )

    def adept_quiet(self, fn, *args):
        try:
            fn(*args)
        except RuntimeError:
            pass

    def adept_drain(self):
        info = self.usb.info
        found = []
        for ep in (info.ep_in, info.ep_data_in):
            while True:
                try:
                    rx = self.usb.usb_read(ep, 64, 200)
                except RuntimeError:
                    break
                if not rx:
                    break
                found.append(
                    self.adept_fmt_pending.format(
                        ep, self.adept_hex(rx)
                    )
                )
        return self.adept_sep_hex.join(found)

    def adept_packet(self, subsys, cmd, body=b""):
        body = bytes(body)
        return bytes([3 + len(body), subsys, cmd, 0]) + body

    def adept_xfer(self, pkt, resp):
        info = self.usb.info
        self.usb.usb_write(info.ep_out, pkt, self.adept_timeout_ms)
        size = 2 + resp + 16
        rx = self.usb.usb_read(info.ep_in, size, self.adept_timeout_ms)
        if len(rx) < 2:
            raise AppUsbError(self.adept_err_short)
        return rx

    def adept_cmd(self, subsys, cmd, payload=b"", resp=0, drain=True):
        pkt = self.adept_packet(subsys, cmd, payload)
        time.sleep(self.adept_settle_s)
        rx = self.adept_xfer(pkt, resp)
        if rx[1] != 0:
            pend = self.adept_drain() if drain else self.adept_empty
            raise AppUsbError(
                self.adept_fmt_status.format(
                    rx[1], self.adept_hex(rx), pend
                )
            )
        count = max(rx[0] - 1, 0)
        return rx[2 : 2 + count]

    def adept_fpga_hold(self):
        sub = self.adept_sub_gpio
        zero = bytes(4)
        self.adept_quiet(
            self.adept_cmd, sub, self.adept_op_gpio_open, b"", 0, False
        )
        self.adept_cmd(
            sub, self.adept_op_gpio_dir, bytes([1, 0, 0, 0]), 4
        )
        self.adept_cmd(sub, self.adept_op_gpio_val, zero)
        self.adept_held = True
        time.sleep(self.adept_hold_s)

    def adept_fpga_release(self):
        self.adept_held = False
        self.adept_cmd(
            self.adept_sub_gpio,
            self.adept_op_gpio_dir,
            bytes(4),
            4,
            drain=False,
        )

    def adept_spi_enable(self):
        self.adept_quiet(self.adept_spi_disable, False)
        if self.adept_hold_fpga:
            self.adept_fpga_hold()
        sub = self.adept_sub_spi
        self.adept_cmd(sub, self.adept_op_spi_open)
        speed = struct.pack(self.adept_fmt_u32, self.adept_spi_hz)
        self.adept_cmd(sub, self.adept_op_spi_speed, speed, 4)
        self.adept_cmd(sub, self.adept_op_spi_mode, bytes([0]))

    def adept_spi_disable(self, drain=True):
        try:
            self.adept_cmd(
                self.adept_sub_spi,
                self.adept_op_spi_close,
                drain=drain,
            )
        finally:
            if self.adept_held and not self.adept_keep_hold:
                self.adept_quiet(self.adept_fpga_release)

    def adept_hold_keep(self, keep):
        self.adept_keep_hold = keep

    def adept_spi_cs(self, level):
        self.adept_cmd(
            self.adept_sub_spi, self.adept_op_spi_cs, bytes([level])
        )

    def adept_spi_io_head(self, read_follows, wlen):
        tail = struct.pack(self.adept_fmt_u32, wlen)
        return bytes([0, 0, read_follows]) + tail

    def adept_spi_io_start(self, read_follows, wlen):
        head = self.adept_spi_io_head(read_follows, wlen)
        self.adept_cmd(self.adept_sub_spi, self.adept_op_spi_io, head)

    def adept_spi_counts(self, rx, read_follows):
        need = 10 if read_follows else 6
        if len(rx) < need:
            raise AppUsbError(
                self.adept_fmt_short_end.format(self.adept_hex(rx))
            )
        wr = None
        rd = None
        if rx[1] & self.adept_flag_wr:
            wr = struct.unpack_from(self.adept_fmt_u32, rx, 2)[0]
        if read_follows and rx[1] & self.adept_flag_rd:
            rd = struct.unpack_from(self.adept_fmt_u32, rx, 6)[0]
        return wr, rd

    def adept_spi_io_end(self, read_follows, total):
        pkt = self.adept_packet(self.adept_sub_spi, self.adept_op_spi_end)
        rx = self.adept_xfer(pkt, 8)
        wr, rd = self.adept_spi_counts(rx, read_follows)
        bad = wr != total or (read_follows and rd != total)
        if bad:
            raise AppUsbError(
                self.adept_fmt_io_end.format(
                    wr, rd, total, self.adept_hex(rx)
                )
            )

    def adept_spi_recv(self, count):
        info = self.usb.info
        out = bytearray()
        while len(out) < count:
            rx = self.usb.usb_read(
                info.ep_data_in,
                self.adept_recv_size,
                self.adept_timeout_ms,
            )
            if not rx:
                break
            out += rx
        if len(out) < count:
            raise AppUsbError(self.adept_err_rx_len)
        return bytes(out[:count])

    def adept_spi_frame(self, buf, wlen, read_follows):
        self.adept_spi_io_start(read_follows, wlen)
        info = self.usb.info
        self.usb.usb_write(info.ep_data_out, buf, self.adept_timeout_ms)
        rx = b""
        if read_follows:
            rx = self.adept_spi_recv(len(buf))
        self.adept_spi_io_end(read_follows, len(buf))
        return rx

    def adept_spi_check(self, total):
        if total == 0 or total > self.adept_txn_max:
            raise AppUsbError(self.adept_fmt_range.format(total))

    def adept_spi_txn(self, tx, count):
        tx = bytes(tx)
        self.adept_spi_check(len(tx) + count)
        buf = tx + bytes([self.adept_fill]) * count
        self.adept_spi_cs(0)
        try:
            rx = self.adept_spi_frame(buf, len(tx), 1 if count else 0)
        except RuntimeError:
            self.adept_quiet(self.adept_spi_cs, 1)
            raise
        self.adept_spi_cs(1)
        return rx[len(tx):]