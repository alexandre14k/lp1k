# src/app/session.py

import sys
from pathlib import Path

from app.usbdev import *
from app.adept import *
from app.flash import *


class AppSession:
    session_fmt_progress = "\r{} [{}] {:3d}%"
    session_txt_fill = "#"
    session_txt_rest = "."
    session_txt_nl = "\n"
    session_empty = ""
    session_err_conn = "not connected"
    session_err_size = "image exceeds flash size"
    session_fmt_id = "flash id [{}] invalid, flash untouched"
    session_fmt_verify = "verify failed at 0x{:05x}"
    session_fmt_done = "verified {} bytes"
    session_msg_cycle = "power-cycle the board to boot the image"
    session_msg_sleep = "flash in deep power-down, fpga held"
    session_msg_wake = "flash awake, fpga released"

    def __init__(self, board):
        self.board = board
        self.usb = AppUsb(board)
        self.adept = AppAdept(self.usb)
        self.flash = AppFlash(self.adept, self.session_progress)

    def session_progress(self, label, done, total):
        width = 24
        fill = width if total == 0 else (done * width) // total
        pct = 100 if total == 0 else (done * 100) // total
        bar = self.session_txt_fill * fill
        bar += self.session_txt_rest * (width - fill)
        sys.stdout.write(
            self.session_fmt_progress.format(label, bar, pct)
        )
        if done >= total:
            sys.stdout.write(self.session_txt_nl)
        sys.stdout.flush()

    def session_connected(self):
        return self.usb.usb_connected()

    def session_alive(self):
        return self.usb.usb_present()

    def session_label(self):
        info = self.usb.info
        if info is None:
            return self.session_empty
        return info.usbinfo_label()

    def session_need(self):
        if not self.session_connected():
            raise RuntimeError(self.session_err_conn)

    def session_scan(self):
        return self.usb.usb_scan()

    def session_connect(self, info):
        self.usb.usb_open(info)

    def session_disconnect(self):
        self.usb.usb_close()

    def session_reset(self):
        self.session_need()
        self.usb.usb_reset()
        self.usb.usb_close()

    def session_wake(self):
        self.flash.flash_wake()

    def session_spi(self, job):
        self.session_need()
        self.adept.adept_spi_enable()
        try:
            if not self.adept.adept_keep_hold:
                self.session_wake()
            return job()
        finally:
            try:
                self.adept.adept_spi_disable(False)
            except RuntimeError:
                pass

    def session_guard_id(self):
        jedec = self.flash.flash_jedec()
        if not self.flash.flash_id_valid(jedec):
            raise RuntimeError(
                self.session_fmt_id.format(self.adept.adept_hex(jedec))
            )

    def session_verify(self, data):
        back = self.flash.flash_read(0, len(data))
        for i, (a, b) in enumerate(zip(data, back)):
            if a != b:
                raise RuntimeError(self.session_fmt_verify.format(i))

    def session_sleep(self):
        self.adept.adept_hold_keep(True)
        try:
            self.session_spi(self.flash.flash_sleep)
        finally:
            self.adept.adept_hold_keep(False)
        print(self.session_msg_sleep)

    def session_unsleep(self):
        self.session_spi(self.session_guard_id)
        print(self.session_msg_wake)

    def session_flash(self, path):
        data = Path(path).read_bytes()
        if len(data) > self.board.flash_size:
            raise RuntimeError(self.session_err_size)

        def job():
            self.session_guard_id()
            self.flash.flash_erase()
            self.flash.flash_write(0, data)
            self.session_verify(data)

        self.session_spi(job)
        print(self.session_fmt_done.format(len(data)))
        print(self.session_msg_cycle)