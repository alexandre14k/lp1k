# src/main.py

import os
import sys
import traceback
from pathlib import Path

from app.board import *
from app.deps import *
from app.scenario import *
from app.tool import *
from app.flow import *
from app.udev import *
from app.packer.tool import *

main_os_posix = "posix"
main_os_nt = "nt"
main_enc_utf8 = "utf-8"

if os.name == main_os_posix:
    from app.usbdev import *
    from app.session import *


class MainApp:
    main_key_list = "l"
    main_key_build = "s"
    main_key_connect = "c"
    main_key_disconnect = "d"
    main_key_flash = "f"
    main_key_reset = "r"
    main_key_udev = "u"
    main_key_clear = "k"
    main_key_menu = "m"
    main_key_sleep = "p"
    main_key_unsleep = "e"
    main_key_exit = "x"
    main_child_keys = ("f", "r", "p", "e")
    main_yes_answers = ("y", "yes")

    main_lbl_list = "list scenarios"
    main_lbl_build = "synth scenario"
    main_lbl_connect = "connect"
    main_lbl_disconnect = "disconnect"
    main_lbl_flash = "flash"
    main_lbl_reset = "reset"
    main_lbl_udev = "udev"
    main_lbl_clear = "clear screen"
    main_lbl_menu = "show menu"
    main_lbl_sleep = "deep sleep"
    main_lbl_unsleep = "exit sleep"
    main_lbl_exit = "exit"

    main_dir_script = "script"
    main_dir_out = "out"
    main_glob_bin = "*.bin"
    main_mod_readline = "readline"

    main_mark_mid = "├── "
    main_mark_end = "└── "

    main_txt_empty = ""
    main_sep_lines = "\n"
    main_shell_cls = "cls"
    main_shell_clear = "clear"
    main_fmt_row = "{} -- {}"
    main_fmt_item = "[{}] {}"
    main_fmt_found = "[{}] found"
    main_fmt_vidpid = "{:04x}:{:04x}"
    main_fmt_dev_row = "device : {} {:03d}:{:03d}"
    main_fmt_name_row = "name : {}"
    main_fmt_status_up = "[ connected {} ]"
    main_fmt_failed = "failed: {}"
    main_fmt_build_failed = "build failed: {}"
    main_fmt_saved = "saved: {}"
    main_fmt_connected = "connected: {}"
    main_fmt_flash_ask = "flash {} [y/N]> "

    main_status_down = "[ disconnected ]"
    main_prompt_down = "> "
    main_prompt_up = "(connected)> "
    main_prompt_index = "choice> "

    main_msg_invalid_index = "invalid index"
    main_msg_reconnect = "!! please reconnect"
    main_msg_no_scenarios = "no scenarios in script/"
    main_msg_no_bins = "no bins in out/"
    main_msg_no_device = "no device found"
    main_msg_disconnected = "disconnected"
    main_msg_aborted = "aborted"
    main_msg_reset_done = "usb reset complete, connect again"

    def __init__(self):
        src = Path(__file__).resolve().parent
        proj = src.parent
        self.main_proj = proj
        self.main_board = AppBoard()
        self.main_deps = AppDeps()
        self.main_scen = AppScenario(src / self.main_dir_script)
        self.main_tool = AppTool()
        self.main_packer = AppPacker()
        self.main_flow = AppFlow(
            self.main_board,
            self.main_tool,
            self.main_packer,
            proj / self.main_dir_out,
        )
        self.main_udev = AppUdev(self.main_board)
        self.main_session = None
        if os.name == main_os_posix:
            self.main_session = AppSession(self.main_board)
        self.main_history_enable()

    def main_history_enable(self):
        try:
            __import__(self.main_mod_readline)
        except ImportError:
            pass

    def main_is_up(self):
        return (
            self.main_session is not None
            and self.main_session.session_connected()
        )

    def main_actions_session(self, acts):
        if not self.main_is_up():
            acts[self.main_key_connect] = (
                self.main_lbl_connect,
                self.main_cmd_connect,
            )
        else:
            acts[self.main_key_disconnect] = (
                self.main_lbl_disconnect,
                self.main_cmd_disconnect,
            )
            acts[self.main_key_flash] = (
                self.main_lbl_flash,
                self.main_cmd_flash,
            )
            acts[self.main_key_reset] = (
                self.main_lbl_reset,
                self.main_cmd_reset,
            )
            acts[self.main_key_sleep] = (
                self.main_lbl_sleep,
                self.main_cmd_sleep,
            )
            acts[self.main_key_unsleep] = (
                self.main_lbl_unsleep,
                self.main_cmd_unsleep,
            )
        acts[self.main_key_udev] = (
            self.main_lbl_udev,
            self.main_cmd_udev,
        )

    def main_actions(self):
        acts = {
            self.main_key_list: (
                self.main_lbl_list,
                self.main_cmd_list,
            ),
            self.main_key_build: (
                self.main_lbl_build,
                self.main_cmd_build,
            ),
        }
        if self.main_session is not None:
            self.main_actions_session(acts)
        acts[self.main_key_clear] = (
            self.main_lbl_clear,
            self.main_cmd_clear,
        )
        acts[self.main_key_menu] = (
            self.main_lbl_menu,
            self.main_show_menu,
        )
        return acts

    def main_status(self):
        if self.main_session is None:
            return self.main_txt_empty
        if not self.main_is_up():
            return self.main_status_down
        return self.main_fmt_status_up.format(
            self.main_session.session_label()
        )

    def main_prompt(self):
        if not self.main_is_up():
            return self.main_prompt_down
        return self.main_prompt_up

    def main_branch(self, last):
        return self.main_mark_end if last else self.main_mark_mid

    def main_menu_rows(self):
        rows = [(k, v[0]) for k, v in self.main_actions().items()]
        rows.append((self.main_key_exit, self.main_lbl_exit))
        return rows

    def main_row_text(self, row):
        return self.main_fmt_row.format(row[0], row[1])

    def main_row_child(self, rows, idx):
        if idx < 0 or idx >= len(rows):
            return False
        return rows[idx][0] in self.main_child_keys

    def main_row_line(self, rows, idx):
        text = self.main_row_text(rows[idx])
        if not self.main_is_up():
            return text
        if not self.main_row_child(rows, idx):
            return text
        last = not self.main_row_child(rows, idx + 1)
        return self.main_branch(last) + text

    def main_show_menu(self):
        status = self.main_status()
        if status:
            print(status)
        rows = self.main_menu_rows()
        for idx in range(len(rows)):
            print(self.main_row_line(rows, idx))

    def main_read(self, prompt):
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    def main_ask_yes(self, prompt):
        ans = self.main_read(prompt)
        return ans is not None and ans.lower() in self.main_yes_answers

    def main_index(self, count):
        pick = self.main_read(self.main_prompt_index)
        if not pick:
            return None
        if not pick.isdigit() or int(pick) >= count:
            print(self.main_msg_invalid_index)
            return None
        return int(pick)

    def main_lost(self):
        self.main_session.session_disconnect()
        print(self.main_msg_reconnect)

    def main_watch(self):
        if not self.main_is_up():
            return
        if not self.main_session.session_alive():
            self.main_lost()

    def main_guard(self, fn):
        try:
            res = fn()
        except AppUsbError as e:
            print(self.main_fmt_failed.format(e))
            self.main_watch()
            return None
        except (ValueError, RuntimeError, OSError) as e:
            print(self.main_fmt_failed.format(e))
            return None
        return True if res is None else res

    def main_rel(self, path):
        try:
            return (
                Path(path).resolve()
                .relative_to(self.main_proj)
                .as_posix()
            )
        except ValueError:
            return str(path)

    def main_cmd_list(self):
        items = self.main_scen.scenario_list()
        if not items:
            print(self.main_msg_no_scenarios)
        for idx, path in enumerate(items):
            print(self.main_fmt_item.format(idx, path.name))
        return items

    def main_pick(self):
        items = self.main_cmd_list()
        if not items:
            return None
        idx = self.main_index(len(items))
        return None if idx is None else items[idx]

    def main_build_path(self):
        path = self.main_pick()
        if path is None:
            return None
        try:
            doc = self.main_scen.scenario_load(path)
            return self.main_flow.flow_build(doc)
        except (ValueError, RuntimeError, OSError) as e:
            print(self.main_fmt_build_failed.format(e))
            return None

    def main_bin_list(self):
        folder = self.main_proj / self.main_dir_out
        if not folder.is_dir():
            return []
        return sorted(folder.glob(self.main_glob_bin))

    def main_pick_bin(self):
        items = self.main_bin_list()
        if not items:
            print(self.main_msg_no_bins)
            return None
        for idx, path in enumerate(items):
            print(self.main_fmt_item.format(idx, path.name))
        idx = self.main_index(len(items))
        return None if idx is None else items[idx]

    def main_cmd_build(self):
        out = self.main_build_path()
        if out is not None:
            print(self.main_fmt_saved.format(self.main_rel(out)))

    def main_device_text(self, idx, d):
        ids = self.main_fmt_vidpid.format(d.vid, d.pid)
        rows = [
            self.main_fmt_found.format(idx),
            self.main_mark_mid
            + self.main_fmt_dev_row.format(ids, d.bus, d.dev),
            self.main_mark_end + self.main_fmt_name_row.format(d.name),
        ]
        return self.main_sep_lines.join(rows)

    def main_cmd_connect(self):
        devs = self.main_session.session_scan()
        if not devs:
            print(self.main_msg_no_device)
            return
        for idx, d in enumerate(devs):
            print(self.main_device_text(idx, d))
        idx = self.main_index(len(devs))
        if idx is None:
            return
        info = devs[idx]
        if self.main_guard(
            lambda: self.main_session.session_connect(info)
        ):
            print(self.main_fmt_connected.format(info.usbinfo_label()))

    def main_cmd_disconnect(self):
        self.main_session.session_disconnect()
        print(self.main_msg_disconnected)

    def main_cmd_flash(self):
        path = self.main_pick_bin()
        if path is None:
            return
        prompt = self.main_fmt_flash_ask.format(path.name)
        if not self.main_ask_yes(prompt):
            print(self.main_msg_aborted)
            return
        self.main_guard(lambda: self.main_session.session_flash(path))

    def main_cmd_reset(self):
        if self.main_guard(self.main_session.session_reset):
            print(self.main_msg_reset_done)

    def main_cmd_sleep(self):
        self.main_guard(self.main_session.session_sleep)

    def main_cmd_unsleep(self):
        self.main_guard(self.main_session.session_unsleep)

    def main_cmd_udev(self):
        self.main_udev.udev_install()

    def main_clear_shell(self):
        if os.name == main_os_nt:
            return self.main_shell_cls
        return self.main_shell_clear

    def main_cmd_clear(self):
        os.system(self.main_clear_shell())

    def main_dispatch(self, cmd):
        entry = self.main_actions().get(cmd)
        if entry is not None:
            entry[1]()

    def main_loop(self):
        self.main_show_menu()
        state = self.main_is_up()
        while True:
            cmd = self.main_read(self.main_prompt())
            if cmd is None or cmd == self.main_key_exit:
                break
            self.main_watch()
            self.main_dispatch(cmd)
            if self.main_is_up() != state:
                state = self.main_is_up()
                self.main_show_menu()


def main_utf8():
    try:
        sys.stdout.reconfigure(encoding=main_enc_utf8)
    except (AttributeError, ValueError, OSError):
        pass


def main_trace_text(exc_type, exc, tb, root):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    return text.replace(str(root) + os.sep, "")


def main_trace_install(root):
    def hook(exc_type, exc, tb):
        sys.stderr.write(main_trace_text(exc_type, exc, tb, root))

    sys.excepthook = hook


def main_entry():
    main_utf8()
    main_trace_install(Path(__file__).resolve().parent.parent)
    app = MainApp()
    if not app.main_deps.deps_check():
        return 1
    app.main_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main_entry())