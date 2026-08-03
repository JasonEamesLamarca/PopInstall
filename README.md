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
| **`entries.json`** | The single source of truth. One entry per tool/customization: what, why, exact commands, and notes. |
| **`install.sh`** | Auto-generated Bash script that reproduces every step in order. **Do not edit by hand.** |
| **`docs/PopOS-Customization-Guide.docx`** | Auto-generated Word document with the same content as step-by-step procedures. |
| **`tools/generate.py`** | Regenerates `install.sh` and the `.docx` from `entries.json`. |
| **`tools/docx_writer.py`** | A tiny stdlib-only `.docx` writer (no pandoc/python-docx needed). |

Because both outputs come from the same `entries.json`, the script and the document
stay in lockstep.

## What it sets up

35 entries across these areas (see the guide for the full detail on each):

| Area | Examples |
|------|----------|
| **Desktop / Appearance** | COSMIC tweaks, themes, fonts |
| **Shell / Terminal** | oh-my-posh prompt with Nerd Font glyphs |
| **Development** | VS Code, Node, PowerShell + Azure tooling, git/SSH setup |
| **Applications** | Everyday GUI apps (Flatpak/apt/snap as appropriate) |
| **Browsers** | Native-package browser installs |
| **Networking** | SMB/CIFS + NFS clients, NAS mount, **Wi-Fi analysis & security-auditing toolkit** |
| **Communication / Email** | Evolution + Exchange/Microsoft 365 backend |
| **Gaming, Printing, Power, Graphics drivers** | Steam, CUPS, session tweaks, GPU firmware |
| **System Maintenance** | Full apt upgrade, PackageKit stack |

## Quick start

```bash
git clone https://github.com/JasonEamesLamarca/PopInstall.git
cd PopInstall

# 1) READ the script and edit placeholders / remove steps you don't want
less install.sh

# 2) Run it as your normal user (it calls sudo on the lines that need it)
bash install.sh
```

> [!WARNING]
> Run `install.sh` as your **normal user, not `sudo bash install.sh`**. Individual
> lines use `sudo` where required; running the whole thing as root breaks user-scope
> steps (e.g. VS Code extensions install into `~/.vscode`, and would land in `/root`).

## Personalize before you run

Machine-specific values are shipped as **placeholders** — replace them with your own,
or delete the entries you don't need, before running:

| Placeholder | Replace with |
|-------------|--------------|
| `192.168.1.10` | Your NAS / server IP |
| `NAS_USER` | Your NAS username |
| `/etc/cifs/synology-nas` | Your credentials filename |
| `your-router.synology.me` | Your router hostname (if relevant) |
| `you@example.com` | Your git / SSH email |
| `wlxXXXXXXXXXXXX` | Your Wi-Fi adapter interface name (`ip link`) |
| `youruser` | Your local username |

No passwords, tokens, or keys are stored in this repo by design — credential files
are created out-of-band and never committed.

## Regenerating the outputs

After editing `entries.json`, regenerate the script and the Word doc:

```bash
python3 tools/generate.py
```

This rewrites `install.sh` and `docs/PopOS-Customization-Guide.docx`. Never edit
those two files directly — they are generated artifacts.

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: edit `entries.json`, run
`python3 tools/generate.py`, and commit all three (`entries.json`, `install.sh`,
`docs/…docx`) together so they stay in sync.

## License

Licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE).
