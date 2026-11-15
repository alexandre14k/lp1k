# src/app/flash.py

import time


class AppFlash:
    flash_op_wren = 0x06
    flash_op_rdsr = 0x05
    flash_op_read = 0x03
    flash_op_pp = 0x02
    flash_op_rdid = 0x9F
    flash_op_wake = 0xAB
    flash_op_erase = 0xC7
    flash_op_sleep = 0xB9
    flash_chunk = 252
    flash_page = 256
    flash_erase_polls = 150
    flash_page_polls = 1000
    flash_erase_poll_s = 0.2
    flash_page_poll_s = 0.001
    flash_lbl_read = "read "
    flash_lbl_erase = "erase"
    flash_lbl_write = "write"
    flash_err_ready = "spi flash ready timeout"

    def __init__(self, adept, progress):
        self.adept = adept
        self.progress = progress

    def flash_addr_cmd(self, op, addr):
        return bytes(
            [op, (addr >> 16) & 0xFF, (addr >> 8) & 0xFF, addr & 0xFF]
        )

    def flash_cmd_read(self, cmd, count):
        return self.adept.adept_spi_txn(cmd, count)

    def flash_cmd_send(self, cmd):
        self.adept.adept_spi_txn(cmd, 0)

    def flash_wake(self):
        self.flash_cmd_send(bytes([self.flash_op_wake]))

    def flash_jedec(self):
        self.flash_wake()
        return self.flash_cmd_read(bytes([self.flash_op_rdid]), 3)

    def flash_status(self):
        rx = self.flash_cmd_read(bytes([self.flash_op_rdsr]), 1)
        return rx[0]

    def flash_id_valid(self, ident):
        blank = bytes(len(ident))
        full = bytes([0xFF] * len(ident))
        return ident != blank and ident != full

    def flash_wait_ready(self, polls, delay):
        for _ in range(polls):
            if (self.flash_status() & 0x01) == 0:
                return
            time.sleep(delay)
        raise RuntimeError(self.flash_err_ready)

    def flash_wren(self):
        self.flash_cmd_send(bytes([self.flash_op_wren]))

    def flash_read(self, addr, length):
        out = bytearray()
        while len(out) < length:
            n = min(length - len(out), self.flash_chunk)
            cmd = self.flash_addr_cmd(self.flash_op_read, addr + len(out))
            out += self.flash_cmd_read(cmd, n)
            self.progress(self.flash_lbl_read, len(out), length)
        return bytes(out)

    def flash_erase(self):
        self.progress(self.flash_lbl_erase, 0, 1)
        self.flash_wren()
        self.flash_cmd_send(bytes([self.flash_op_erase]))
        self.flash_wait_ready(
            self.flash_erase_polls, self.flash_erase_poll_s
        )
        self.progress(self.flash_lbl_erase, 1, 1)

    def flash_page_room(self, cur, left):
        room = self.flash_page - (cur % self.flash_page)
        return min(left, room, self.flash_chunk)

    def flash_write(self, addr, data):
        total = len(data)
        off = 0
        while off < total:
            cur = addr + off
            n = self.flash_page_room(cur, total - off)
            self.flash_wren()
            head = self.flash_addr_cmd(self.flash_op_pp, cur)
            self.flash_cmd_send(head + data[off : off + n])
            self.flash_wait_ready(
                self.flash_page_polls, self.flash_page_poll_s
            )
            off += n
            self.progress(self.flash_lbl_write, off, total)

    def flash_sleep(self):
        self.flash_cmd_send(bytes([self.flash_op_sleep]))