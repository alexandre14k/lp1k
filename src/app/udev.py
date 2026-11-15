# src/app/udev.py

import os
import subprocess


class AppUdev:
    udev_os_posix = "posix"
    udev_path = "/etc/udev/rules.d/52-lp1k.rules"
    udev_fmt_rule = (
        'SUBSYSTEM=="usb",ATTR{{idVendor}}=="{:04x}",'
        'ATTR{{idProduct}}=="{:04x}",MODE="0666",TAG+="uaccess"\n'
    )
    udev_fmt_trigger = "--attr-match=idVendor={:04x}"
    udev_fmt_ok = "udev ok: {}"
    udev_sep_cmd = " "
    udev_bin_sudo = "sudo"
    udev_bin_tee = "tee"
    udev_bin_udevadm = "udevadm"
    udev_arg_control = "control"
    udev_arg_reload = "--reload-rules"
    udev_arg_trigger = "trigger"

    def __init__(self, board):
        self.board = board

    def udev_rule(self):
        return self.udev_fmt_rule.format(
            self.board.usb_vid, self.board.usb_pid
        )

    def udev_exec(self, cmd, data=None, quiet=False):
        print(self.udev_sep_cmd.join(cmd))
        out = subprocess.DEVNULL if quiet else None
        return subprocess.run(cmd, input=data, stdout=out)

    def udev_steps(self, rule):
        trig = self.udev_fmt_trigger.format(self.board.usb_vid)
        write = [self.udev_bin_sudo, self.udev_bin_tee, self.udev_path]
        reload = [
            self.udev_bin_sudo,
            self.udev_bin_udevadm,
            self.udev_arg_control,
            self.udev_arg_reload,
        ]
        fire = [
            self.udev_bin_sudo,
            self.udev_bin_udevadm,
            self.udev_arg_trigger,
            trig,
        ]
        return [
            (write, rule.encode(), True),
            (reload, None, False),
            (fire, None, False),
        ]

    def udev_install(self):
        if os.name != self.udev_os_posix:
            return False
        rule = self.udev_rule()
        print(rule.strip())
        for cmd, data, quiet in self.udev_steps(rule):
            if self.udev_exec(cmd, data, quiet).returncode != 0:
                return False
        print(self.udev_fmt_ok.format(self.udev_path))
        return True