# Contributing

Thanks for your interest! This repo is a generated build log, so the workflow is a
little unusual: **you never edit `install.sh` or the `.docx` directly.**

## The golden rule

`entries.json` is the **single source of truth**. `install.sh` and
`docs/PopOS-Customization-Guide.docx` are both generated from it by
`tools/generate.py`. Editing the generated files by hand will be overwritten the
next time anyone regenerates.

## Workflow

1. Add or edit an entry in **`entries.json`**. Each entry has:
   ```json
   {
     "id": 36,
     "date": "YYYY-MM-DD",
     "category": "Networking",
     "name": "Short human-readable name",
     "description": "What was installed/changed and why.",
     "method": "apt",
     "requires_sudo": true,
     "commands": ["sudo apt install -y example"],
     "notes": "Gotchas, verification steps, alternatives, revert instructions."
   }
   ```
   - `id` is the next unused integer.
   - Keep `commands` as the exact, copy-pasteable steps.
   - Put anything future-you would want to know in `notes`.

### Parameters (optional)

If a step needs machine-specific input, add a `params` array. The wizard
(`install-wizard.py`) prompts for each one; `tools/generate.py` bakes the
`default` into `install.sh` and the Word guide.

```json
"params": [
  { "token": "NAS_HOST", "prompt": "NAS / server IP or hostname", "default": "192.168.1.10" },
  { "token": "NAS_PASSWORD", "prompt": "NAS password (optional)", "default": "", "secret": true }
]
```

Two kinds of token, referenced differently inside `commands`:

- **Non-secret** — write it as `{{TOKEN}}` in commands. `generate.py` replaces it
  with `default`; the wizard replaces it with the user's answer.
- **Secret** (`"secret": true`) — **never** write it as `{{TOKEN}}`. Reference it as a
  shell variable `${TOKEN:-}` instead. The wizard passes it through the environment at
  run time; it is never substituted into text and never written to `install.sh`, the
  `.docx`, or the repo. Use `:-` so `install.sh` (run without the wizard) treats it as
  empty under `set -u`.

Tokens are collected by name across all selected steps, so the same `{{NAS_HOST}}`
used by two entries is prompted for only once.

2. Regenerate the outputs:
   ```bash
   python3 tools/generate.py
   ```

3. Commit **all three together** so they never drift:
   ```bash
   git add entries.json install.sh docs/PopOS-Customization-Guide.docx
   git commit -m "Add entry 36: <name>"
   ```

## Please do not commit

- **Secrets or personal data.** No passwords, tokens, API keys, private IPs,
  usernames, MAC addresses, or hostnames. Use placeholders (see the README's
  *Personalize before you run* table) and create credentials out-of-band.
- Hand-edited `install.sh` / `.docx` — regenerate instead.

## Style

- Match the tone of existing entries: concrete commands, honest notes about what
  broke and how it was fixed.
- Prefer native packages; call out deliberate exceptions in `notes`.
