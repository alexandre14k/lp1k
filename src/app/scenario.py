# src/app/scenario.py

import ast
import re
from pathlib import Path


class AppScenarioDoc:
    def __init__(self, path, pins, verilog, top):
        self.path = path
        self.pins = pins
        self.verilog = verilog
        self.top = top


class AppScenario:
    sc_ext = ".py"
    sc_glob_all = "*"
    sc_hdr_pin = "pinout"
    sc_hdr_logic = "logic"
    sc_pin_sep = "--"
    sc_empty = ""
    sc_pat_line = r"^\s*#(.*)$"
    sc_pat_top = r"\bmodule\s+([A-Za-z_]\w*)"
    sc_re_line = re.compile(sc_pat_line)
    sc_re_top = re.compile(sc_pat_top)
    sc_err_syntax = "script syntax error: {}"
    sc_err_no_verilog = "no verilog string found"
    sc_err_empty_verilog = "empty verilog string"
    sc_err_no_module = "no module declaration found"
    sc_err_no_pins = "no pinout entries found"

    def __init__(self, folder):
        self.folder = Path(folder)

    def scenario_list(self):
        if not self.folder.is_dir():
            return []
        return sorted(self.folder.glob(self.sc_glob_all + self.sc_ext))

    def scenario_comment(self, line):
        found = self.sc_re_line.match(line)
        if found is None:
            return None
        return found.group(1).strip()

    def scenario_pair(self, note):
        left, right = note.split(self.sc_pin_sep, 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            return (left, right)
        return None

    def scenario_pins(self, text):
        pins = []
        mode = self.sc_empty
        for line in text.splitlines():
            note = self.scenario_comment(line)
            if note is None:
                if line.strip():
                    mode = self.sc_empty
                continue
            low = note.lower()
            if low in (self.sc_hdr_pin, self.sc_hdr_logic):
                mode = low
                continue
            if mode != self.sc_hdr_pin:
                continue
            if self.sc_pin_sep not in note:
                continue
            pair = self.scenario_pair(note)
            if pair is not None:
                pins.append(pair)
        return pins

    def scenario_tree(self, text):
        try:
            return ast.parse(text)
        except SyntaxError as e:
            raise ValueError(self.sc_err_syntax.format(e))

    def scenario_verilog(self, text):
        code = ast.get_docstring(self.scenario_tree(text), clean=False)
        if code is None:
            raise ValueError(self.sc_err_no_verilog)
        code = code.strip()
        if not code:
            raise ValueError(self.sc_err_empty_verilog)
        return code

    def scenario_top(self, code):
        found = self.sc_re_top.search(code)
        if found is None:
            raise ValueError(self.sc_err_no_module)
        return found.group(1)

    def scenario_load(self, path):
        text = Path(path).read_text()
        pins = self.scenario_pins(text)
        if not pins:
            raise ValueError(self.sc_err_no_pins)
        code = self.scenario_verilog(text)
        return AppScenarioDoc(
            Path(path), pins, code, self.scenario_top(code)
        )