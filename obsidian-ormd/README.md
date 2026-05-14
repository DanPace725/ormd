# ORMD for Obsidian

Minimal development plugin for Open Relational Markdown (`.ormd`) files.

Current starter scope:

- Register `.ormd` files with Obsidian's Markdown view.
- Validate the active `.ormd` file from the command palette.
- Show a small status-bar summary for the active `.ormd` file.
- Keep the ORMD parser and validator in TypeScript modules that can grow independently.

## Development

```bash
npm install
npm run build
```

For local Obsidian testing, copy or symlink this directory into:

```text
<vault>/.obsidian/plugins/ormd
```

Then enable the plugin from Obsidian's Community plugins settings.
