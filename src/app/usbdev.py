# src/app/usbdev.py

import ctypes
import fcntl
import os
import struct
from pathlib import Path


class AppUsbError(RuntimeError):
    pass


class AppUsbBulk(ctypes.Structure):
    _fields_ = [
        ("ep", ctypes.c_uint),
        ("len", ctypes.c_uint),
        ("timeout", ctypes.c_uint),
        ("data", ctypes.c_void_p),
    ]


class AppUsbSub(ctypes.Structure):
    _fields_ = [
        ("ifno", ctypes.c_int),
        ("ioctl_code", ctypes.c_int),
        ("data", ctypes.c_void_p),
    ]


class AppUsbInfo:
    usbinfo_fmt_label = "{:04x}:{:04x} {:03d}:{:03d}"

    def __init__(self, vid, pid, bus, dev, eps, desc, name):
        self.vid = vid
        self.pid = pid
        self.bus = bus
        self.dev = dev
        self.ep_out, self.ep_in = eps[0], eps[1]
        self.ep_data_out, self.ep_data_in = eps[2], eps[3]
        self.desc = desc
        self.name = name
        self.iface = 0

    def usbinfo_label(self):
        return self.usbinfo_fmt_label.format(
            self.vid, self.pid, self.bus, self.dev
        )


class AppUsb:
    usb_sysfs = Path("/sys/bus/usb/devices")
    usb_node_fmt = "/dev/bus/usb/{:03d}/{:03d}"
    usb_fmt_u32 = "I"
    usb_empty = ""
    usb_sep_desc = " "
    usb_colon = ":"
    usb_if_suffix = ":1.0"
    usb_glob_ep = "ep_*"
    usb_file_type = "type"
    usb_file_addr = "bEndpointAddress"
    usb_file_vid = "idVendor"
    usb_file_pid = "idProduct"
    usb_file_bus = "busnum"
    usb_file_dev = "devnum"
    usb_file_mfg = "manufacturer"
    usb_file_prod = "product"
    usb_kind_bulk = "Bulk"
    usb_fmt_ep_desc = "0x{:02x}:{}"
    usb_err_already = "already connected"
    usb_fmt_open_fail = "open failed: {} (try udev setup)"
    usb_fmt_claim_fail = "claim failed: {}"
    usb_fmt_reset_fail = "usb reset failed: {}"
    usb_fmt_write_fail = "usb bulk write failed ep=0x{:02x}: {}"
    usb_fmt_read_fail = "usb bulk read failed ep=0x{:02x}: {}"

    def __init__(self, board):
        self.board = board
        self.fd = -1
        self.info = None

    def usb_ioc(self, direction, nr, size):
        return (direction << 30) | (size << 16) | (0x55 << 8) | nr

    def usb_req_bulk(self):
        return self.usb_ioc(3, 2, ctypes.sizeof(AppUsbBulk))

    def usb_req_claim(self):
        return self.usb_ioc(2, 15, 4)

    def usb_req_release(self):
        return self.usb_ioc(2, 16, 4)

    def usb_req_sub(self):
        return self.usb_ioc(3, 18, ctypes.sizeof(AppUsbSub))

    def usb_req_reset(self):
        return self.usb_ioc(0, 20, 0)

    def usb_code_disconnect(self):
        return self.usb_ioc(0, 22, 0)

    def usb_connected(self):
        return self.fd >= 0

    def usb_present(self):
        if self.fd < 0 or self.info is None:
            return False
        node = self.usb_node_fmt.format(
            self.info.bus, self.info.dev
        )
        return os.path.exists(node)

    def usb_read_text(self, path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None

    def usb_read_hex(self, path):
        txt = self.usb_read_text(path)
        if txt is None:
            return None
        try:
            return int(txt, 16)
        except ValueError:
            return None

    def usb_read_int(self, path):
        txt = self.usb_read_text(path)
        if txt is None or not txt.isdigit():
            return None
        return int(txt)

    def usb_probe_eps(self, entry):
        if_dir = entry / (entry.name + self.usb_if_suffix)
        found = []
        if if_dir.is_dir():
            for ep in if_dir.glob(self.usb_glob_ep):
                kind = self.usb_read_text(ep / self.usb_file_type)
                kind = kind or self.usb_empty
                addr = self.usb_read_hex(ep / self.usb_file_addr)
                if addr is not None:
                    found.append((addr, kind))
        found.sort(key=lambda t: (t[0] & 0x0F, t[0]))
        bulk = self.usb_kind_bulk
        outs = [a for a, k in found if k == bulk and not a & 0x80]
        ins = [a for a, k in found if k == bulk and a & 0x80]
        ep_out = outs[0] if outs else 0x01
        ep_in = ins[0] if ins else 0x82
        d_out = outs[1] if len(outs) > 1 else ep_out
        d_in = ins[1] if len(ins) > 1 else ep_in
        desc = self.usb_sep_desc.join(
            self.usb_fmt_ep_desc.format(a, k) for a, k in found
        )
        return (ep_out, ep_in, d_out, d_in), desc

    def usb_scan(self):
        out = []
        if not self.usb_sysfs.is_dir():
            return out
        for entry in self.usb_sysfs.iterdir():
            if self.usb_colon in entry.name:
                continue
            vid = self.usb_read_hex(entry / self.usb_file_vid)
            pid = self.usb_read_hex(entry / self.usb_file_pid)
            if vid != self.board.usb_vid or pid != self.board.usb_pid:
                continue
            bus = self.usb_read_int(entry / self.usb_file_bus)
            dev = self.usb_read_int(entry / self.usb_file_dev)
            if bus is None or dev is None:
                continue
            eps, desc = self.usb_probe_eps(entry)
            name = self.usb_name(entry)
            out.append(
                AppUsbInfo(vid, pid, bus, dev, eps, desc, name)
            )
        out.sort(key=lambda i: (i.bus, i.dev))
        return out

    def usb_detach(self, fd, iface):
        arg = AppUsbSub(iface, self.usb_code_disconnect(), None)
        try:
            fcntl.ioctl(fd, self.usb_req_sub(), arg)
        except OSError:
            pass

    def usb_claim(self, fd, iface):
        packed = struct.pack(self.usb_fmt_u32, iface)
        try:
            fcntl.ioctl(fd, self.usb_req_claim(), packed)
            return
        except OSError:
            self.usb_detach(fd, iface)
        fcntl.ioctl(fd, self.usb_req_claim(), packed)

    def usb_open(self, info):
        if self.fd >= 0:
            raise AppUsbError(self.usb_err_already)
        node = self.usb_node_fmt.format(info.bus, info.dev)
        try:
            fd = os.open(node, os.O_RDWR)
        except OSError as e:
            raise AppUsbError(self.usb_fmt_open_fail.format(e))
        try:
            self.usb_claim(fd, info.iface)
        except OSError as e:
            os.close(fd)
            raise AppUsbError(self.usb_fmt_claim_fail.format(e))
        self.fd = fd
        self.info = info

    def usb_close(self):
        if self.fd < 0:
            return
        packed = struct.pack(self.usb_fmt_u32, self.info.iface)
        try:
            fcntl.ioctl(self.fd, self.usb_req_release(), packed)
        except OSError:
            pass
        os.close(self.fd)
        self.fd = -1
        self.info = None

    def usb_reset(self):
        try:
            fcntl.ioctl(self.fd, self.usb_req_reset(), 0)
        except OSError as e:
            raise AppUsbError(self.usb_fmt_reset_fail.format(e))

    def usb_write(self, ep, data, timeout):
        data = bytes(data)
        buf = ctypes.create_string_buffer(data)
        req = AppUsbBulk(ep, len(data), timeout, ctypes.addressof(buf))
        try:
            return fcntl.ioctl(self.fd, self.usb_req_bulk(), req)
        except OSError as e:
            raise AppUsbError(self.usb_fmt_write_fail.format(ep, e))

    def usb_read(self, ep, size, timeout):
        buf = ctypes.create_string_buffer(size)
        req = AppUsbBulk(ep, size, timeout, ctypes.addressof(buf))
        try:
            n = fcntl.ioctl(self.fd, self.usb_req_bulk(), req)
        except OSError as e:
            raise AppUsbError(self.usb_fmt_read_fail.format(ep, e))
        return buf.raw[:n]

    def usb_name(self, entry):
        mfg = self.usb_read_text(entry / self.usb_file_mfg) or ""
        prod = self.usb_read_text(entry / self.usb_file_prod) or ""
        if mfg and prod.lower().startswith(mfg.lower()):
            return prod
        parts = [p for p in (mfg, prod) if p]
        if not parts:
            return self.board.name
        return self.usb_sep_desc.join(parts)