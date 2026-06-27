# Preserve Paths

Default local-config preserve list for `app1/2/3/4`:

- `config/localDebug.js`
- `scripts/auto_pack_on_export.ps1`
- `scripts/export_app_resources.ps1`
- `scripts/export_pack_install.ps1`
- `scripts/onekey_pack_install.ps1`
- `scripts/send_duomilu_prompt.ps1`

Intent:

- these files may differ per workspace because device id, ports, local login account, install target, or debug relay settings differ
- they should usually stay out of `hanhan/app` shared sync

If a future workspace adds another local-only file, extend the preserve list in the script before bulk refresh.
