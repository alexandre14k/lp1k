# src/app/flow.py

import re
import shutil
import tempfile
from pathlib import Path


class AppFlow:
    flow_lc_tag = "ICESTORM_LC:"
    flow_lbl_pins = (
        "[1/4] using tool internal\n"
        "converting .py to .v .pcf"
    )
    flow_lbl_yosys = (
        "[2/4] using tool yosys (external)\n"
        "converting .v to .json"
    )
    flow_lbl_pnr = (
        "[3/4] using tool nextpnr (external)\n"
        "converting .json .pcf to .asc"
    )
    flow_lbl_pack = (
        "[4/4] using tool packer (internal)\n"
        "converting .asc to .bin"
    )
    flow_fmt_pins = "using {} pins: {}"
    flow_fmt_pin = "{}={}"
    flow_fmt_scenario = "scenario {}"
    flow_fmt_size = "output size {} bytes"
    flow_fmt_setio = "set_io {} {}"
    flow_fmt_script = (
        'read_verilog "{}"; synth_ice40 -top {} -json "{}"'
    )
    flow_pat_items = re.compile(r"\s*[,;]\s*")
    flow_fmt_type = "type {}"
    flow_mark_mid = "├── "
    flow_mark_end = "└── "
    flow_sep_pins = ", "
    flow_sep_space = " "
    flow_sep_lines = "\n"
    flow_sep_tree = "\n"
    flow_txt_end = "\n"
    flow_txt_empty = ""
    flow_file_v = "top.v"
    flow_file_pcf = "top.pcf"
    flow_file_json = "top.json"
    flow_file_asc = "top.asc"
    flow_ext_bin = ".bin"
    flow_tmp_prefix = "lp1k-"
    flow_bin_yosys = "yosys"
    flow_arg_quiet = "-q"
    flow_arg_script = "-p"
    flow_bin_pnr = "nextpnr-ice40"
    flow_arg_dev = "--lp1k"
    flow_arg_package = "--package"
    flow_arg_json = "--json"
    flow_arg_pcf = "--pcf"
    flow_arg_asc = "--asc"
    flow_arg_freq = "--freq"
    flow_err_size = "bitstream exceeds flash size"

    def __init__(self, board, tool, packer, outdir):
        self.board = board
        self.tool = tool
        self.packer = packer
        self.outdir = Path(outdir)

    def flow_stage(self, label, detail, gap=True):
        if gap:
            print(self.flow_txt_empty)
        print(label)
        if detail:
            print(detail)

    def flow_pcf(self, pins):
        lines = []
        for port, pin in pins:
            lines.append(
                self.flow_fmt_setio.format(
                    port, self.board.board_resolve(pin)
                )
            )
        return self.flow_sep_lines.join(lines) + self.flow_txt_end

    def flow_write(self, work, doc):
        (work / self.flow_file_v).write_text(
            doc.verilog + self.flow_txt_end
        )
        (work / self.flow_file_pcf).write_text(self.flow_pcf(doc.pins))

    def flow_cmd_yosys(self, work, top):
        script = self.flow_fmt_script.format(
            (work / self.flow_file_v).as_posix(),
            top,
            (work / self.flow_file_json).as_posix(),
        )
        return [
            self.flow_bin_yosys,
            self.flow_arg_quiet,
            self.flow_arg_script,
            script,
        ]

    def flow_cmd_nextpnr(self, work):
        return [
            self.flow_bin_pnr,
            self.flow_arg_dev,
            self.flow_arg_package, self.board.package,
            self.flow_arg_json, str(work / self.flow_file_json),
            self.flow_arg_pcf, str(work / self.flow_file_pcf),
            self.flow_arg_asc, str(work / self.flow_file_asc),
            self.flow_arg_freq, self.board.board_clk_mhz(),
        ]

    def flow_pack(self, work):
        text = (work / self.flow_file_asc).read_text()
        return self.packer.packer_pack(text)

    def flow_usage_tree(self, line):
        flat = self.flow_sep_space.join(line.split())
        tail = flat.split(self.flow_lc_tag, 1)[1].strip()
        items = [p for p in self.flow_pat_items.split(tail) if p]
        rows = [self.flow_fmt_type.format(self.flow_lc_tag)]
        last = len(items) - 1
        for idx, item in enumerate(items):
            mark = self.flow_mark_end if idx == last else self.flow_mark_mid
            rows.append(mark + item)
        return self.flow_sep_tree.join(rows)

    def flow_usage(self, log):
        for line in reversed(log.splitlines()):
            if self.flow_lc_tag in line:
                return self.flow_usage_tree(line)
        return self.flow_txt_empty

    def flow_pins_text(self, pins):
        names = self.flow_sep_pins.join(
            self.flow_fmt_pin.format(port, pin) for port, pin in pins
        )
        return self.flow_fmt_pins.format(len(pins), names)

    def flow_build_in(self, work, doc):
        self.flow_stage(
            self.flow_lbl_pins, self.flow_pins_text(doc.pins), False
        )
        self.flow_write(work, doc)
        self.tool.tool_run(self.flow_cmd_yosys(work, doc.top))
        self.flow_stage(
            self.flow_lbl_yosys,
            self.flow_fmt_scenario.format(doc.top),
        )
        log = self.tool.tool_run(self.flow_cmd_nextpnr(work))
        self.flow_stage(self.flow_lbl_pnr, self.flow_usage(log))
        data = self.flow_pack(work)
        if len(data) > self.board.flash_size:
            raise RuntimeError(self.flow_err_size)
        self.flow_stage(
            self.flow_lbl_pack,
            self.flow_fmt_size.format(len(data)),
        )
        self.outdir.mkdir(parents=True, exist_ok=True)
        dst = self.outdir / (doc.path.stem + self.flow_ext_bin)
        dst.write_bytes(data)
        return dst

    def flow_build(self, doc):
        work = Path(tempfile.mkdtemp(prefix=self.flow_tmp_prefix))
        try:
            return self.flow_build_in(work, doc)
        finally:
            shutil.rmtree(work, ignore_errors=True)