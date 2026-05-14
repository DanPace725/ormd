# ORMD 0.1 Specification (MVP)

**Version:** 0.1 | **Date:** 2025-05-28

---

## 1. Overview

Open Relational Markdown (`.ormd`) 0.1 is a minimal specification that:

* Extends CommonMark with a lightweight relational layer.
* Defines a canonical plain-text or ZIP-packed package.
* Embeds verifiable metadata and versioning.

This spec is intentionally limited to core syntax, packaging, and validation rules. Features like CRDT change-feeds and embedded comments will follow in v0.2.

## 2. File Version Tag

Every `.ormd` file **MUST** begin with an HTML comment version marker:

```ormd
<!-- ormd:0.1 -->
```

* Ensures toolchains can detect and validate against the correct spec.

## 3. Base Syntax

1.  **CommonMark 0.30** compliance for all Markdown constructs.
2.  ORMD documents use a single YAML front-matter block for all metadata. This block **MUST** be at the beginning of the document, immediately following the version tag.
    *   The front-matter block **MUST** be delimited by `---` on lines by themselves.
    *   While `+++` delimiters for this initial block may still be parsed by some tools for backward compatibility with older ORMD 0.1 drafts, `---` is the standard and preferred delimiter. Future versions of ORMD may deprecate `+++` for front-matter entirely.
    *   The parser implementation correctly distinguishes these delimiters from thematic breaks (`---`) or other `+++` sequences within the document body.

```ormd
<!-- ormd:0.1 -->
---
title: Example
authors:
  - id: alice
    display: Alice L.
links: []
---
# Heading

Body text…
```

**Note on Metadata:** Separate metadata blocks (e.g., using `+++meta ... +++end-meta` syntax) within the document body are no longer supported. All document metadata (including authorship, links, dates, custom fields, etc.) **MUST** be defined within the single YAML front-matter block at the top of the file.

## 4. Relational Layer

ORMD's relational layer allows authors to define and reference semantic connections within the document or to external resources.

### 4.1 Inline Semantic Links (Primary Creation Method)

Links are primarily created directly in the document body using a Markdown-like syntax:

`[display text](target "optional relationship")`

*   **`display text`**: The text that will be rendered for the link.
*   **`target`**: The URL, internal anchor (e.g., `#section-id`), or path to another file. Internal anchors should correspond to HTML-compatible anchor IDs generated from Markdown headings (e.g., `# My Heading` becomes `#my-heading`) or explicit HTML anchors (e.g., `<a id="custom-anchor"></a>`).
*   **`optional relationship`**: A keyword describing the semantic nature of the link, enclosed in double quotes. If omitted, the link has no explicit semantic relationship. Approved relationship types are defined by the ORMD schema (e.g., `supports`, `refutes`, `cites`, `references`, `related`).

**Example:**
`This concept [supports our main argument](#argument-1 "supports"). Read more at [Example.com](https://example.com "references").`

### 4.2 Front-Matter `links:` Section (Link Definitions)

All links, whether created inline or defined manually, are registered in the document's front-matter within the `links:` list. Tools like `ormd update` can scan the document body for inline semantic links and auto-populate this section.

Each entry in the `links:` list is an object with the following fields:

*   `id` (string, required): A unique identifier for the link within the document. For auto-populated links, this is typically generated (e.g., `auto-link-1`).
*   `to` (string, required): The target URI or internal anchor (derived from the `target` in inline syntax).
*   `rel` (string, optional): The relationship type (from the `"relationship"` part of inline syntax or manually defined). If present, it must be one of the approved relationship types.
*   `text` (string, optional): For links auto-generated from inline syntax, this field stores the original `display text`.
*   `title` (string, optional): For manually defined links, this field can suggest a display text when the link is referenced using the `[[link-id]]` syntax.
*   `source` (string, optional): Indicates how the link definition was created (e.g., `inline` for auto-generated links, `manual` if specified).

**Example `links:` section in YAML front-matter:**
```yaml
links:
  - id: "manual-ref"
    to: "#section-details"
    rel: "references"
    title: "Detailed Section Reference" # Manual link with a title
  - id: "auto-link-1" # Auto-populated from an inline link
    to: "https://example.org/resource"
    rel: "cites"
    text: "External Resource" # Original display text from [External Resource](...)
    source: "inline"
```

### 4.3 Referencing Defined Links: `[[link-id]]`

Once a link is defined in the front-matter's `links:` section (either manually or via auto-population), it can be referenced elsewhere in the document body using the `[[link-id]]` syntax.

**Example:**
`As shown in our methods [[manual-ref]], the data was processed.`

When rendered, `[[link-id]]` is typically replaced by an HTML hyperlink. The display text for this link may be derived from the link definition's `text` field (if populated from an inline link), then its `title` field (if manually provided), or fall back to the `link-id` itself.

### 4.4 Legacy Link Handling

For backward compatibility or specific workflows, tools may offer a `--legacy-links` mode. When active:
*   `ormd update` may not auto-populate inline `[text](target "rel")` links into the front-matter.
*   `ormd validate` may apply stricter rules for `[[link-id]]` references, expecting them to be resolved only from manually defined front-matter `links:`, and may not fully process inline links for definition purposes.
This flag is intended as a transitional aid. The primary mechanism for link creation and definition is the inline syntax with front-matter auto-population.

## 5. Packaging

A `.ormd` artifact **MUST** be one of:

1. **Plain `.ormd` file** (text-only): contains version tag, front-matter, and body.
2. **Zipped package** (`.ormd` extension on a zip): with this structure:

```
archive.ormd/
├── content.ormd      # canonical text file
├── meta.json         # JSON-LD metadata & signatures
├── ops/              # optional CRDT binary patches
└── render.css        # default stylesheet for HTML/print
```

* Tools must prefer unpacking the zip and validating `content.ormd`.

## 6. Metadata & Signatures

* **meta.json** follows JSON-LD, containing at least:

  * `@context`: JSON-LD context URL or inline.
  * `title`, `authors`, `created`, `modified`.
  * `provenance` object with C2PA-style hash chain and signature references.

```json
{
  "@context": "https://openrel.org/ormd/context.jsonld",
  "title": "Example",
  "authors": [...],
  "provenance": {
    "hash": "SHA256:...",
    "sigRef": "provenance.sig"
  }
}
```

* Detached signature file (e.g. `provenance.sig`) may accompany the package.

## 7. Validation

An `.ormd` validator **MUST** check:

1. Presence and correct format of version tag.
2. Valid YAML front-matter and required keys.
3. CommonMark-compliant body parse.
4. Every `[[id]]` matches a `links.id` entry.
5. For packages: existence of `content.ormd` and `meta.json`.

Failure to meet any rule **MUST** result in a non-zero exit code.

## 8. Example: Hello ORMD

```ormd
<!-- ormd:0.1 -->
---
title: Hello ORMD
authors:
  - id: daniel.pace
    display: Daniel Pace
links:
  - id: g1
    rel: supports
    to: "#goal"
---
# Hello ORMD

This is a **living document** that combines Markdown and semantic links.

See [[g1]] for the guiding principle.

## <a id="goal"></a>Goal

Open. Relational. Markdown.
```

## 9. Test Vectors

* **Missing version tag** → invalid.
* **Broken YAML** in front-matter → invalid.
* **Undefined `[[link]]`** → invalid.
* **Valid plain `.ormd`** → valid.
* **Valid zipped `.ormd`** with correct structure → valid.

## 10. CLI Commands (v0.1)

* `ormd validate [file.ormd|package.ormd] [--legacy-links] [--check-external-links]`
* `ormd update [file.ormd] [--legacy-links] [--dry-run] [--force-update]`
* `ormd pack content.ormd meta.json [--out=package.ormd]`
* `ormd unpack package.ormd --out-dir=./`
* `ormd render [file.ormd|package.ormd] [-o output.html]`
* `ormd create [file.ormd]`
* `ormd open [file.ormd|package.ormd]`
* `ormd edit [file.ormd|package.ormd]`
* `ormd convert [input_file] [output.ormd]`


## 11. Next Steps (for v0.2)

* CRDT change-feed embedding and merge rules.
* Inline commenting and annotation syntax.
* GUI reference implementation and Conformance Test Suite.

---


