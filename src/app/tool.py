# src/app/tool.py

import subprocess


class AppTool:
    tool_tail_lines = 20
    tool_sep_lines = "\n"
    tool_fmt_run = "tool not runnable: {}: {}"
    tool_fmt_fail = "tool failed: {} ({})\n{}"

    def tool_tail(self, log):
        tail = log.splitlines()[-self.tool_tail_lines:]
        return self.tool_sep_lines.join(tail)

    def tool_run(self, cmd):
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True
            )
        except OSError as e:
            raise RuntimeError(self.tool_fmt_run.format(cmd[0], e))
        log = res.stdout + res.stderr
        if res.returncode != 0:
            raise RuntimeError(
                self.tool_fmt_fail.format(
                    cmd[0], res.returncode, self.tool_tail(log)
                )
            )
        return log