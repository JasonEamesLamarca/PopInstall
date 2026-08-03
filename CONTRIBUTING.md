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
