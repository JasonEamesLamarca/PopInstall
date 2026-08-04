#!/usr/bin/env python3
"""
PopInstall interactive wizard.

Reads entries.json (the single source of truth) and lets you:
  1. pick which customizations to apply from a category-grouped menu, and
  2. answer prompts for any parameters those picks need (NAS host, git identity,
     an optional NAS password, ...),
then runs only the selected steps, in order.

Nothing here is generated -- it consumes the same entries.json that
tools/generate.py turns into install.sh and the Word guide, so the wizard can
never drift from the linear script.

Examples:
  ./install-wizard.py                      # interactive menu
  ./install-wizard.py --list               # just list everything and exit
  ./install-wizard.py --all --dry-run      # show resolved commands for all steps
  ./install-wizard.py --only 10,19,31      # preselect specific entries
  ./install-wizard.py --category Networking --category "CLI Tools"

Your selection and non-secret answers are remembered in
~/.config/popinstall/config.json and pre-populate the next run (override with
--config PATH, disable with --no-save). Secrets are never saved.
"""
from __future__ import annotations

import argparse
import getpass
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import json
except ImportError:  # pragma: no cover
    sys.exit("python3 with json support is required")

ROOT = Path(__file__).resolve().parent
ENTRIES_PATH = ROOT / "entries.json"
# The download's own directory. Exported to every step as POPINSTALL_DIR so that
# repo-relative steps (e.g. the wallpaper install, which copies files out of img/)
# work no matter which directory the wizard was launched from.
POPINSTALL_DIR = str(ROOT)


# ----------------------------------------------------------------------------- colour
def _supports_colour() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


class C:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.enabled else s

    def bold(self, s):   return self._wrap("1", s)
    def dim(self, s):    return self._wrap("2", s)
    def green(self, s):  return self._wrap("32", s)
    def yellow(self, s): return self._wrap("33", s)
    def blue(self, s):   return self._wrap("36", s)
    def red(self, s):    return self._wrap("31", s)


# ----------------------------------------------------------------------------- data
def load_entries() -> dict:
    if not ENTRIES_PATH.exists():
        sys.exit(f"entries.json not found next to this script ({ENTRIES_PATH})")
    with open(ENTRIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def parse_id_spec(spec: str) -> set[int]:
    """'1,3,10-12' -> {1,3,10,11,12}."""
    ids: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            ids.update(range(int(a), int(b) + 1))
        else:
            ids.add(int(part))
    return ids


def resolve(cmds: list[str], values: dict[str, str]) -> list[str]:
    """Replace {{TOKEN}} with the chosen value (non-secret params only)."""
    out = []
    for c in cmds:
        for tok, val in values.items():
            c = c.replace("{{" + tok + "}}", val)
        out.append(c)
    return out


# ----------------------------------------------------------------------------- config
# A small local config remembers your last selection and your (non-secret) answers
# so the next launch is pre-populated. Secrets (e.g. the NAS password) are NEVER
# written here -- they are prompted fresh every time.
CONFIG_VERSION = 1


def default_config_path() -> Path:
    """~/.config/popinstall/config.json, honouring XDG_CONFIG_HOME."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "popinstall" / "config.json"


def load_config(path: Path) -> dict:
    """Return the saved config, or {} if missing/unreadable/malformed."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # normalise the shapes we rely on
    sel = data.get("selection")
    data["selection"] = [int(i) for i in sel if isinstance(i, int)] if isinstance(sel, list) else []
    vals = data.get("values")
    data["values"] = {str(k): str(v) for k, v in vals.items()} if isinstance(vals, dict) else {}
    return data


def save_config(path: Path, selection: set[int], values: dict[str, str], c: C) -> None:
    """Persist selection + non-secret values with private (0600) permissions."""
    payload = {
        "version": CONFIG_VERSION,
        "selection": sorted(selection),
        "values": values,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        print(c.dim(f"  Saved your choices to {path} (secrets are never stored)"))
    except OSError as exc:
        print(c.yellow(f"  Could not save preferences to {path}: {exc}"))


# ----------------------------------------------------------------------------- logging
# Every run writes a plain-text transcript (metadata + the exact commands + their
# live output + exit codes) so it can be copied and pasted for troubleshooting.
# Secrets are never resolved into the logged commands (they arrive via the
# environment as ${TOKEN}) and are not written here.
_ANSI_RE = re.compile(rb"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")


def default_log_path() -> Path:
    """~/.local/state/popinstall/logs/run-YYYYmmdd-HHMMSS.log (XDG_STATE_HOME)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return base / "popinstall" / "logs" / f"run-{stamp}.log"


def _clean_for_log(data: bytes) -> bytes:
    """Strip ANSI escapes and normalise carriage returns for a readable log."""
    data = _ANSI_RE.sub(b"", data)
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


class RunLog:
    """Append-only transcript. A no-op stand-in when logging is disabled."""

    def __init__(self, path: Path | None):
        self.path = path
        self.f = None
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.f = open(path, "ab", buffering=0)
        except OSError as exc:
            print(f"  (could not open log file {path}: {exc}; continuing without a log)")
            self.path = None

    @property
    def enabled(self) -> bool:
        return self.f is not None

    def line(self, text: str = "") -> None:
        if self.f is not None:
            self.f.write((text + "\n").encode("utf-8", "replace"))

    def run_teed(self, argv: list[str], env: dict) -> int:
        """Run argv on a pty so it stays interactive (sudo prompts, colour),
        while teeing a sanitised copy of its output into the log."""
        try:
            import pty
        except Exception:
            # No pty (non-Unix): fall back to a plain interactive run, capturing
            # nothing but still recording that we ran and the exit code.
            proc = subprocess.run(argv, env=env)
            return proc.returncode

        f = self.f

        def master_read(fd: int) -> bytes:
            data = os.read(fd, 65536)
            if data and f is not None:
                f.write(_clean_for_log(data))
            return data

        saved = os.environ.copy()
        try:
            os.environ.clear()
            os.environ.update(env)
            status = pty.spawn(argv, master_read)
        finally:
            os.environ.clear()
            os.environ.update(saved)
        return os.waitstatus_to_exitcode(status)

    def close(self) -> None:
        if self.f is not None:
            try:
                self.f.close()
            finally:
                self.f = None


# ----------------------------------------------------------------------------- menu
def print_catalogue(entries: list[dict], c: C, selected: set[int] | None = None) -> None:
    cat = None
    for e in entries:
        if e["category"] != cat:
            cat = e["category"]
            print("\n  " + c.bold(c.blue(cat)))
        mark = ""
        if selected is not None:
            mark = c.green("[x] ") if e["id"] in selected else c.dim("[ ] ")
        pflag = c.yellow(" *params") if e.get("params") else ""
        doconly = c.dim(" (doc only)") if not (e.get("commands")) else ""
        print(f"    {mark}{e['id']:>2}. {e['name']}{pflag}{doconly}")


def interactive_select(entries: list[dict], c: C, preselected: set[int]) -> set[int]:
    ids = {e["id"] for e in entries}
    selected = set(preselected)
    cats = []
    for e in entries:
        if e["category"] not in cats:
            cats.append(e["category"])

    help_text = (
        c.dim(
            "\n  Commands: numbers/ranges (e.g. 10,19,31 or 5-9) toggle | "
            "'a'=all  'n'=none\n"
            "            category name toggles a whole group | "
            "'d' or Enter=proceed | 'q'=quit\n"
        )
    )
    while True:
        print_catalogue(entries, c, selected)
        print(help_text)
        print(f"  {c.bold('Selected:')} {len(selected)} of {len(ids)}")
        try:
            raw = input(c.bold("  > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit("Aborted.")
        low = raw.lower()
        if low in ("d", ""):
            if not selected:
                print(c.yellow("  Nothing selected yet."))
                continue
            return selected
        if low == "q":
            sys.exit("Aborted.")
        if low == "a":
            selected = set(ids); continue
        if low == "n":
            selected = set(); continue
        # category toggle (case-insensitive prefix match, unique)
        matches = [cat for cat in cats if cat.lower().startswith(low)]
        if len(matches) == 1 and not any(ch.isdigit() for ch in low):
            grp = {e["id"] for e in entries if e["category"] == matches[0]}
            selected = (selected - grp) if grp <= selected else (selected | grp)
            continue
        # otherwise treat as an id spec
        try:
            toggle = parse_id_spec(raw)
        except ValueError:
            print(c.red("  Unrecognised input.")); continue
        bad = toggle - ids
        if bad:
            print(c.red(f"  No such entry id(s): {sorted(bad)}")); continue
        selected ^= toggle


# ----------------------------------------------------------------------------- curses UI
def _add(win, y, x, text, attr=0, maxw=None):
    """Write text at (y,x), truncated to fit, ignoring edge-cell errors."""
    import curses
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w - 1:
            return
        avail = (w - x - 1) if maxw is None else min(maxw, w - x - 1)
        if avail <= 0:
            return
        win.addnstr(y, x, text, avail, attr)
    except Exception:
        pass


def _curses_select(stdscr, entries, selected):
    """Full-screen, cursor-driven multiselect. Returns a set, or None to quit."""
    import curses

    curses.curs_set(0)
    stdscr.keypad(True)
    has_color = False
    try:
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)    # category header
            curses.init_pair(2, curses.COLOR_GREEN, -1)   # checked box
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # scroll marker
            has_color = True
    except curses.error:
        has_color = False

    def cp(n):
        return curses.color_pair(n) if has_color else 0

    # flat display list: category headers interleaved with their entries
    cats = []
    for e in entries:
        if e["category"] not in cats:
            cats.append(e["category"])
    display = []
    for cat in cats:
        display.append(("cat", cat))
        for e in entries:
            if e["category"] == cat:
                display.append(("entry", e))
    entry_rows = [i for i, (k, _) in enumerate(display) if k == "entry"]
    all_ids = {e["id"] for e in entries}
    cur = entry_rows[0]
    offset = 0

    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()
        try:
            stdscr.border()
        except curses.error:
            pass

        title = " PopInstall — choose customizations "
        _add(stdscr, 0, max(2, (w - len(title)) // 2), title, curses.A_BOLD)
        _add(stdscr, 1, 2, f" Selected {len(selected)}/{len(all_ids)} ", curses.A_BOLD)

        list_top, list_bottom = 2, h - 2
        visible = max(1, list_bottom - list_top + 1)
        if cur < offset:
            offset = cur
        if cur >= offset + visible:
            offset = cur - visible + 1
        offset = max(0, min(offset, max(0, len(display) - visible)))

        for row in range(visible):
            d = offset + row
            if d >= len(display):
                break
            y = list_top + row
            kind, payload = display[d]
            if kind == "cat":
                _add(stdscr, y, 2, payload, curses.A_BOLD | cp(1))
            else:
                e = payload
                checked = e["id"] in selected
                box = "[x]" if checked else "[ ]"
                tag = " *params" if e.get("params") else ""
                doc = " (doc only)" if not e.get("commands") else ""
                text = f" {box} {e['id']:>2}. {e['name']}{tag}{doc}"
                attr = curses.A_REVERSE if d == cur else (cp(2) if checked else 0)
                _add(stdscr, y, 3, text, attr, w - 5)

        if offset > 0:
            _add(stdscr, list_top, w - 3, "^", curses.A_BOLD | cp(3))
        if offset + visible < len(display):
            _add(stdscr, list_bottom, w - 3, "v", curses.A_BOLD | cp(3))

        help_line = (" up/down move · space toggle · c category · a all · "
                     "n none · enter run · q quit ")
        _add(stdscr, h - 1, max(2, (w - len(help_line)) // 2), help_line, curses.A_BOLD)
        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (curses.KEY_DOWN, ord("j")):
            nxt = [p for p in entry_rows if p > cur]
            if nxt:
                cur = nxt[0]
        elif ch in (curses.KEY_UP, ord("k")):
            prv = [p for p in entry_rows if p < cur]
            if prv:
                cur = prv[-1]
        elif ch == curses.KEY_NPAGE:
            below = [p for p in entry_rows if p > cur]
            if below:
                cur = below[min(len(below) - 1, visible - 1)]
        elif ch == curses.KEY_PPAGE:
            above = [p for p in entry_rows if p < cur]
            if above:
                cur = above[max(0, len(above) - visible)]
        elif ch == curses.KEY_HOME:
            cur = entry_rows[0]
        elif ch == curses.KEY_END:
            cur = entry_rows[-1]
        elif ch == ord(" "):
            eid = display[cur][1]["id"]
            selected.discard(eid) if eid in selected else selected.add(eid)
        elif ch == ord("a"):
            selected |= all_ids
        elif ch == ord("n"):
            selected.clear()
        elif ch == ord("c"):
            cat = display[cur][1]["category"]
            grp = {e["id"] for e in entries if e["category"] == cat}
            selected.difference_update(grp) if grp <= selected else selected.update(grp)
        elif ch in (curses.KEY_ENTER, 10, 13):
            if selected:
                return set(selected)
        elif ch in (ord("q"), ord("Q")):
            # Note: not ESC (27) -- it is the lead byte of arrow-key sequences.
            return None
        # KEY_RESIZE and anything else: just redraw


def select_ui(entries: list[dict], c: C, preselected: set[int]) -> set[int]:
    """Cursor-driven picker with graceful fallback to the numbered menu."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return interactive_select(entries, c, preselected)
    try:
        import curses  # noqa: F401
        import locale
        locale.setlocale(locale.LC_ALL, "")
    except Exception:
        return interactive_select(entries, c, preselected)
    try:
        result = curses.wrapper(_curses_select, entries, set(preselected))
    except Exception:
        # unusable terminal (too small, no terminfo, ...) -> numbered menu
        return interactive_select(entries, c, preselected)
    if result is None:
        sys.exit("Aborted.")
    return result


# ----------------------------------------------------------------------------- params
def collect_params(chosen: list[dict], c: C, non_interactive: bool,
                   saved_values: dict[str, str] | None = None) -> dict:
    """Prompt once per unique token across all chosen entries.

    Any previously-saved (non-secret) answer becomes the pre-populated default,
    falling back to the entry's built-in default. Secrets are always prompted
    fresh and never read from saved config.

    Returns {"values": {token: str} (non-secret), "env": {token: str} (secret)}.
    """
    saved = saved_values or {}
    # gather unique params, remembering which entries use each
    order: list[str] = []
    meta: dict[str, dict] = {}
    users: dict[str, list[int]] = {}
    for e in chosen:
        for p in e.get("params") or []:
            tok = p["token"]
            if tok not in meta:
                meta[tok] = p
                order.append(tok)
            users.setdefault(tok, []).append(e["id"])

    values: dict[str, str] = {}
    env: dict[str, str] = {}
    if not order:
        return {"values": values, "env": env}

    print("\n" + c.bold("Parameters") + c.dim("  (press Enter to accept the default)"))
    for tok in order:
        p = meta[tok]
        used_by = ",".join(f"#{i}" for i in sorted(set(users[tok])))
        label = f"  {p.get('prompt', tok)} {c.dim('['+used_by+']')}"
        if p.get("secret"):
            if non_interactive:
                continue  # never assume a secret; leave it unset
            val = getpass.getpass(label + ": ")
            if val:
                env[tok] = val
        else:
            # prefer a previously-saved answer, then the entry's built-in default
            from_saved = tok in saved
            default = saved[tok] if from_saved else p.get("default", "")
            if non_interactive:
                values[tok] = default
                continue
            src = c.dim(" (saved)") if from_saved else ""
            shown = default if default != "" else c.dim("(empty)")
            val = input(f"{label}{src} [{c.green(str(shown))}]: ").strip()
            values[tok] = val if val else default
    return {"values": values, "env": env}


# ----------------------------------------------------------------------------- run
def run_entry(e: dict, values: dict, env: dict, c: C, dry_run: bool, log: RunLog) -> int:
    cmds = resolve(e.get("commands") or [], values)
    header = f"[{e['id']}] {e['name']}"
    if not cmds:
        print(c.dim(f"  · {header}: documentation-only, nothing to run"))
        log.line(f"\n--- {header}: documentation-only, nothing to run")
        return 0
    print("\n" + c.bold(c.green(f">>> {header}")))
    log.line("\n" + "=" * 72)
    log.line(f">>> {header}")
    log.line("--- commands ---")
    for line in cmds:
        log.line("    " + line)
    script = "set -euo pipefail\n" + "\n".join(cmds)
    if dry_run:
        for line in cmds:
            print("    " + c.dim(line))
        log.line("--- dry run: not executed ---")
        return 0
    run_env = os.environ.copy()
    run_env["POPINSTALL_DIR"] = POPINSTALL_DIR
    run_env.update(env)
    log.line("--- output ---")
    rc = log.run_teed(["bash", "-c", script], run_env)
    log.line(f"--- exit code: {rc} ---")
    if rc != 0:
        print(c.red(f"  !! entry {e['id']} exited with code {rc}"))
    return rc


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Interactive installer for the PopInstall customization set.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--list", action="store_true", help="list all entries and exit")
    ap.add_argument("--all", action="store_true", help="preselect every entry")
    ap.add_argument("--only", metavar="IDS", help="preselect ids, e.g. 10,19,31 or 5-9")
    ap.add_argument("--category", action="append", default=[], metavar="NAME",
                    help="preselect a whole category (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the resolved commands but do not execute anything")
    ap.add_argument("--yes", action="store_true",
                    help="non-interactive: accept parameter defaults and run without confirmation")
    ap.add_argument("--allow-root", action="store_true",
                    help="permit running as root (not recommended; user-scope steps break)")
    ap.add_argument("--config", metavar="PATH",
                    help="config file for saved selection/answers "
                         "(default: ~/.config/popinstall/config.json)")
    ap.add_argument("--no-save", action="store_true",
                    help="do not read or write the saved-preferences config file")
    ap.add_argument("--log", metavar="PATH",
                    help="write the run transcript here "
                         "(default: ~/.local/state/popinstall/logs/run-<timestamp>.log)")
    ap.add_argument("--no-log", action="store_true",
                    help="do not write a run transcript to disk")
    ap.add_argument("--no-color", action="store_true", help="disable coloured output")
    args = ap.parse_args()

    c = C(enabled=_supports_colour() and not args.no_color)
    data = load_entries()
    entries = data["entries"]
    by_id = {e["id"]: e for e in entries}

    # saved preferences (last selection + non-secret answers), used to pre-populate
    cfg_path = Path(args.config).expanduser() if args.config else default_config_path()
    cfg = {} if args.no_save else load_config(cfg_path)

    print(c.bold(f"\n{data.get('distro_name', 'PopInstall')} — install wizard"))
    base = data.get("base", {})
    if base:
        print(c.dim(f"Base: {base.get('name','')} {base.get('version','')} "
                    f"({base.get('codename','')})  ·  {len(entries)} available steps"))

    if args.list:
        print_catalogue(entries, c)
        print()
        return

    if os.geteuid() == 0 and not args.allow_root:
        sys.exit(c.red(
            "\nRefusing to run as root. Run as your normal user — individual steps call "
            "sudo where needed. User-scope steps (VS Code extensions, ~/.config, fonts) "
            "break under root. Use --allow-root only if you really mean it."))

    # ---- build the preselection
    preselected: set[int] = set()
    if args.all:
        preselected = set(by_id)
    if args.only:
        preselected |= parse_id_spec(args.only)
    for name in args.category:
        grp = {e["id"] for e in entries if e["category"].lower().startswith(name.lower())}
        if not grp:
            sys.exit(f"No category matches '{name}'.")
        preselected |= grp
    bad = preselected - set(by_id)
    if bad:
        sys.exit(f"No such entry id(s): {sorted(bad)}")

    # ---- selection
    # An explicit selection (--all/--only/--category) is taken as final and goes
    # straight to parameters + confirmation. With no selection flags, open the
    # interactive menu. --yes still needs an explicit selection to run unattended.
    if preselected:
        selected = preselected
    elif args.yes:
        sys.exit("--yes needs an explicit selection: use --all, --only, or --category.")
    else:
        saved_sel = {i for i in cfg.get("selection", []) if i in by_id}
        selected = select_ui(entries, c, saved_sel)

    chosen = [by_id[i] for i in sorted(selected)]

    # ---- parameters (pre-populated from saved answers)
    params = collect_params(chosen, c, non_interactive=args.yes,
                            saved_values=cfg.get("values", {}))

    # ---- remember selection + non-secret answers for next time
    if not args.no_save:
        merged_values = dict(cfg.get("values", {}))
        merged_values.update(params["values"])
        save_config(cfg_path, selected, merged_values, c)

    # ---- open the run log (transcript for troubleshooting)
    log_path = None if args.no_log else (
        Path(args.log).expanduser() if args.log else default_log_path())
    log = RunLog(log_path)
    if log.enabled:
        cols, rows = shutil.get_terminal_size((80, 24))
        log.line("=" * 72)
        log.line(f"PopInstall run log — {datetime.now().isoformat(timespec='seconds')}")
        log.line(f"distro      : {data.get('distro_name', 'PopInstall')}")
        log.line(f"base        : {base.get('name','')} {base.get('version','')} "
                 f"({base.get('codename','')})")
        log.line(f"popinstall  : {POPINSTALL_DIR}")
        log.line(f"invoked     : {' '.join(sys.argv)}")
        log.line(f"python      : {platform.python_version()}  ({sys.executable})")
        log.line(f"platform    : {platform.platform()}")
        log.line(f"terminal    : {cols}x{rows}")
        log.line(f"user (uid)  : {os.environ.get('USER','?')} ({os.geteuid()})")
        log.line(f"dry_run     : {args.dry_run}")
        log.line(f"selection   : {[e['id'] for e in chosen]}")
        if params["values"]:
            log.line("params      : " + ", ".join(f"{k}={v}" for k, v in params["values"].items()))
        secret_toks = sorted({p["token"] for e in chosen for p in (e.get("params") or [])
                              if p.get("secret") and p["token"] in params["env"]})
        if secret_toks:
            log.line(f"secrets set : {secret_toks} (values not logged)")
        print(c.dim(f"Logging this run to {log.path}"))

    # ---- summary + confirm
    print("\n" + c.bold("About to apply:"))
    for e in chosen:
        tag = c.dim(" (doc only)") if not e.get("commands") else ""
        sudo = c.yellow(" [sudo]") if e.get("requires_sudo") else ""
        print(f"  {e['id']:>2}. {e['name']}{sudo}{tag}")
    if args.dry_run:
        print(c.yellow("\n-- DRY RUN: showing resolved commands, nothing will execute --"))
    if not args.yes and not args.dry_run:
        try:
            ok = input("\n" + c.bold(f"Proceed with {len(chosen)} step(s)? [y/N] ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(); log.line("\n=== aborted at confirmation ==="); log.close(); sys.exit("Aborted.")
        if ok not in ("y", "yes"):
            log.line("\n=== declined at confirmation ==="); log.close()
            sys.exit("Aborted.")

    # ---- run
    failures = []
    for e in chosen:
        rc = run_entry(e, params["values"], params["env"], c, args.dry_run, log)
        if rc != 0 and not args.dry_run:
            failures.append(e["id"])
            if args.yes:
                break
            try:
                cont = input(c.yellow("  Continue with the remaining steps? [y/N] ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(); break
            if cont not in ("y", "yes"):
                break

    print()
    if args.dry_run:
        log.line("\n=== dry run complete ===")
        print(c.bold("Dry run complete."))
    elif failures:
        log.line(f"\n=== finished with failures in: {failures} ===")
        print(c.red(f"Finished with failures in: {failures}"))
        if log.enabled:
            print(c.yellow(f"Attach this log for troubleshooting: {log.path}"))
        log.close()
        sys.exit(1)
    else:
        log.line("\n=== done: all selected steps completed ===")
        print(c.bold(c.green("Done. All selected steps completed.")))
    if log.enabled:
        print(c.dim(f"Full transcript (copy/paste for troubleshooting): {log.path}"))
    log.close()


if __name__ == "__main__":
    main()
