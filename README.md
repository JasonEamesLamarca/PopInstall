# PopInstall — a reproducible Pop!_OS 24.04 build log

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Platform: Pop!_OS 24.04 LTS](https://img.shields.io/badge/Platform-Pop!__OS%2024.04%20LTS-brightgreen)
![Shell script](https://img.shields.io/badge/install-bash-lightgrey)

A single, growing, self-documenting record of every package installed and every
customization applied to a fresh **Pop!_OS 24.04 LTS** machine — turned into a
**repeatable install script** (`install.sh`) and a matching **Word guide**, both
generated from one source of truth so they can never drift apart.

Use it to rebuild the same environment on a new machine in one command, cherry-pick
individual steps, or as a reference for how each tool was set up and *why*.

> [!IMPORTANT]
> This is a personal build log published as a reference. **Read `install.sh`
> before running it** and adjust it to your own hardware, network, and taste.
> Placeholders (see [Personalize before you run](#personalize-before-you-run))
> stand in for machine-specific values — the script is not meant to be run
> unmodified on someone else's computer.

---

## What's inside

| File | Purpose |
|------|---------|
| **`entries.json`** | The single source of truth. One entry per tool/customization: what, why, exact commands, params, and notes. |
| **`install-wizard.py`** | Interactive installer: pick which steps to apply from a menu, answer parameter prompts, run only those. |
| **`install.sh`** | Auto-generated Bash script that reproduces **every** step in order. **Do not edit by hand.** |
| **`docs/PopOS-Customization-Guide.docx`** | Auto-generated Word document with the same content as step-by-step procedures. |
| **`tools/generate.py`** | Regenerates `install.sh` and the `.docx` from `entries.json`. |
| **`tools/docx_writer.py`** | A tiny stdlib-only `.docx` writer (no pandoc/python-docx needed). |

Because both outputs come from the same `entries.json`, the script and the document
stay in lockstep.

## What it sets up

38 entries across these areas (see the guide for the full detail on each):

| Area | Examples |
|------|----------|
| **Desktop / Appearance** | COSMIC tweaks, themes, fonts |
| **Shell / Terminal** | oh-my-posh prompt with Nerd Font glyphs |
| **Development** | VS Code, Node, PowerShell + Azure tooling, git/SSH setup |
| **Applications** | Everyday GUI apps (Flatpak/apt/snap as appropriate) |
| **Browsers** | Native-package Chromium (default) and Microsoft Edge (optional); one setting picks which is the default browser |
| **Networking** | SMB/CIFS + NFS clients, NAS mount, **Wi-Fi analysis & security-auditing toolkit** |
| **Communication / Email** | Evolution + Exchange/Microsoft 365 backend |
| **Device Management** | **Microsoft Intune enrollment** (Company Portal, identity broker, Edge) so the machine registers in Entra ID for Conditional Access |
| **Gaming, Printing, Power, Graphics drivers** | Steam, CUPS, session tweaks, GPU firmware |
| **System Maintenance** | Full apt upgrade, PackageKit stack |

## Quick start

Get the whole thing in **one download** — everything the installer needs
(`entries.json`, the wallpapers in `img/`, the wizard) ships in the repo, so a
clone *or* a ZIP works with no extra fetching:

```bash
# Option A — clone
git clone https://github.com/JasonEamesLamarca/PopInstall.git
cd PopInstall

# Option B — download + unzip (no git required)
curl -L https://github.com/JasonEamesLamarca/PopInstall/archive/refs/heads/main.zip -o PopInstall.zip
unzip PopInstall.zip && cd PopInstall-main
```

Only **Python 3** (already on Pop!_OS) and **bash** are required — the wizard is
pure standard library, no `pip install` step. You can launch it from anywhere;
it finds its own files and the `img/` wallpapers regardless of your current
directory (override with `POPINSTALL_DIR` if you ever relocate them).

There are two ways to install. Either way, run as your **normal user** — steps call
`sudo` on the individual lines that need it.

### Option 1 — Interactive wizard (recommended)

Pick exactly the customizations you want from a menu, and the wizard prompts you for
any parameters those steps need (NAS host, git identity, an optional NAS password, …):

```bash
./install-wizard.py
```

Your selection and your (non-secret) answers are **remembered between runs**. They're
saved to `~/.config/popinstall/config.json` (0600), so the next launch pre-checks the
same steps and pre-fills every prompt with what you entered last time — just press
Enter to accept. **Secrets (e.g. the NAS password) are never written to disk** and are
prompted fresh each time.

Useful flags:

```bash
./install-wizard.py --list                 # list all steps and exit
./install-wizard.py --all --dry-run        # preview the resolved commands for everything
./install-wizard.py --only 10,19,31        # run just these steps
./install-wizard.py --category Networking  # run a whole category
./install-wizard.py --config ./my.json     # use a specific saved-preferences file
./install-wizard.py --no-save              # don't read or write the saved config
./install-wizard.py --log ./run.log        # write the transcript to a specific file
./install-wizard.py --no-log               # don't write a transcript
```

### Logs — for troubleshooting

**Every run writes a plain-text transcript** so you can copy/paste it if something
goes wrong. It records the metadata (distro, Python, terminal size, the exact
command line you ran), and for each step the exact commands, their live output,
and the exit code. By default it lands in:

```
~/.local/state/popinstall/logs/run-<timestamp>.log
```

The path is printed at the start and end of every run (and again, highlighted, if
any step fails). Change it with `--log PATH` or turn it off with `--no-log`.
**Secrets are never written to the log** (or to the saved config): passwords are
passed to steps through the environment and never resolved into the recorded
commands.

The menu is a full-screen picker: use **↑/↓** (or `j`/`k`) to move, **space** to
toggle a step, **`c`** to toggle the whole category under the cursor, **`a`/`n`** for
all/none, then **Enter** to run (**`q`** quits). The list scrolls automatically when
it's taller than your terminal. Steps marked `*params` will prompt for input; nothing
runs until you confirm, and `--dry-run` shows the exact commands without executing.
On a terminal without curses it falls back to a numbered menu.

### Option 2 — Run everything

```bash
# READ it first, edit placeholders / delete steps you don't want, then:
bash install.sh
```

> [!WARNING]
> Don't run either installer with `sudo` in front (`sudo bash install.sh` /
> `sudo ./install-wizard.py`). Individual lines use `sudo` where required; running the
> whole thing as root breaks user-scope steps (e.g. VS Code extensions install into
> `~/.vscode`, and would land in `/root`). The wizard refuses to run as root unless you
> pass `--allow-root`.

## Personalize before you run

Machine-specific values are shipped as **placeholders**. The **wizard prompts you for
these automatically** (so you can leave the files untouched); if you use `install.sh`
instead, replace them by hand or delete the entries you don't need first:

| Placeholder | Replace with |
|-------------|--------------|
| `192.168.1.10` | Your NAS / server IP |
| `NAS_USER` | Your NAS username |
| `/etc/cifs/synology-nas` | Your credentials filename |
| `your-router.synology.me` | Your router hostname (if relevant) |
| `you@example.com` | Your git / SSH email |
| `wlxXXXXXXXXXXXX` | Your Wi-Fi adapter interface name (`ip link`) |
| `youruser` | Your local username |
| `chromium` (entry 38) | Default browser: `chromium` or `edge` |

No passwords, tokens, or keys are stored in this repo by design — credential files
are created out-of-band and never committed.

## Regenerating the outputs

After editing `entries.json`, regenerate the script and the Word doc:

```bash
python3 tools/generate.py
```

This rewrites `install.sh` and `docs/PopOS-Customization-Guide.docx`. Never edit
those two files directly — they are generated artifacts.

## Microsoft Intune enrollment (Conditional Access)

Entry 36 enrolls the machine in **Microsoft Intune**, so it shows up in
Microsoft Entra ID as a managed device and can meet Conditional Access rules
such as *require a compliant device*. It installs everything needed from
Microsoft's apt repos — the Microsoft Intune app (`intune-portal`), the
Microsoft Identity Broker, `libpam-pwquality` and Microsoft Edge — starts the
Intune services, then opens the Intune app for you to sign in:

```bash
./install-wizard.py --only 36
```

Sign in with your work account (with MFA) and accept the registration prompts.
Then sign in to an **Edge** profile with the same account — on Linux, Edge is
the only browser that passes the device's state to Conditional Access. Check
the result with `dsreg --status` (expect `Registered` and `PRT Present: YES`).

> [!NOTE]
> **Registered is not the same as compliant.** Microsoft supports Intune on
> Ubuntu, not Pop!_OS, and the device reports as *Pop!_OS 24.04*. If your
> tenant's compliance policy only allows Ubuntu, requires disk encryption (a
> Pop!_OS install without *Encrypt drive* fails this), or sets password rules,
> the device can register but still be non-compliant. The Intune app lists any
> failing setting; see entry 36's notes in the guide for each fix.

## ⚠️ Security & authorized-use notice (Wi-Fi tooling)

The **Networking** section installs Wi-Fi analysis and security-auditing tools
(`wifite`, `bully`, `hashcat`, `hcxdumptool`, `hcxtools`, `macchanger`, and
survey tools). These are legitimate tools for **testing networks you own or are
explicitly authorized in writing to test**.

Capturing handshakes/PMKIDs, brute-forcing WPS, or cracking passwords on networks
you do not own or have permission to assess is **illegal in most jurisdictions**.
You are solely responsible for how you use them. If you don't want these tools,
delete the Networking entry from `entries.json` (or the corresponding block in
`install.sh`) before running.

## Building your own Pop!_OS-based image

The final section of the Word guide covers three ways to turn this into a custom
distro: **Cubic** (easiest ISO respin), **live-build/debootstrap** (full control),
or simply running `install.sh` as a **first-boot provisioning script** on a stock
install. Start with the last option to validate end-to-end, then move to Cubic if
you want a shareable `.iso`.

The Intune enrollment step (entry 36) is the exception: skip it in a Cubic/chroot
build and run `./install-wizard.py --only 36` on each machine after first boot,
since every device has to register itself with its own user's sign-in.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: edit `entries.json`, run
`python3 tools/generate.py`, and commit all three (`entries.json`, `install.sh`,
`docs/…docx`) together so they stay in sync.

## License

Licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).
