# src/app/deps.py

import shutil
import sys


class AppDepsItem:
    def __init__(self, binary, package):
        self.binary = binary
        self.package = package


class AppDeps:
    deps_bin_yosys = "yosys"
    deps_pkg_yosys = "yosys"
    deps_bin_pnr = "nextpnr-ice40"
    deps_pkg_pnr = "nextpnr-ice40"
    deps_items = (
        AppDepsItem(deps_bin_yosys, deps_pkg_yosys),
        AppDepsItem(deps_bin_pnr, deps_pkg_pnr),
    )
    deps_apt_cmd = "sudo apt install"
    deps_sep_names = ", "
    deps_sep_pkgs = " "
    deps_sep_lines = "\n"
    deps_txt_blank = ""
    deps_fmt_missing = "missing external tools: {}"
    deps_txt_install = "install on Debian/Ubuntu:"
    deps_fmt_install = "  {} {}"
    deps_txt_other_a = "other systems: install the packages that"
    deps_txt_other_b = "provide these binaries and add them to PATH,"
    deps_txt_other_c = "then start again."

    def deps_present(self, item):
        return shutil.which(item.binary) is not None

    def deps_missing(self):
        return [i for i in self.deps_items if not self.deps_present(i)]

    def deps_packages(self, missing):
        pkgs = []
        for item in missing:
            if item.package not in pkgs:
                pkgs.append(item.package)
        return pkgs

    def deps_help(self, missing):
        names = self.deps_sep_names.join(i.binary for i in missing)
        pkgs = self.deps_sep_pkgs.join(self.deps_packages(missing))
        lines = [
            self.deps_fmt_missing.format(names),
            self.deps_txt_blank,
            self.deps_txt_install,
            self.deps_fmt_install.format(self.deps_apt_cmd, pkgs),
            self.deps_txt_blank,
            self.deps_txt_other_a,
            self.deps_txt_other_b,
            self.deps_txt_other_c,
        ]
        return self.deps_sep_lines.join(lines)

    def deps_check(self):
        missing = self.deps_missing()
        if not missing:
            return True
        print(self.deps_help(missing), file=sys.stderr)
        return False