# Open Relational Markdown (ORMD)

*A document format that doesn't suck*

## The Problem Everyone Has But Nobody Talks About

### PDF: The Zombie Format That Won't Die
- ✅ **Looks identical everywhere** (its one redeeming quality)
- ✅ **Can be "frozen"** for legal/government use (cryptographic signatures)
- ❌ **Collaboration is hell** (email chains of "final_FINAL_v3.pdf")
- ❌ **Editing requires expensive software** (Adobe's $20/month monopoly)
- ❌ **Version control doesn't work** (binary blob, can't diff changes)
- ❌ **Accessibility is terrible** (screen readers hate it)
- ❌ **Mobile experience sucks** (fixed layouts don't adapt)

### Google Docs: Great Until It Isn't
- ✅ **Real-time collaboration** (when it works)
- ✅ **Easy editing** (familiar interface)
- ❌ **Vendor lock-in** (Google owns your data)
- ❌ **Requires internet** (offline editing is clunky)
- ❌ **No version control** (try merging two Google Docs)
- ❌ **Export breaks formatting** (PDF export never looks right)
- ❌ **No semantic meaning** (a link is just a link, no relationship context)

### Microsoft Word: The Corporate Standard Nobody Loves
- ✅ **Widely available** (everyone has it)
- ✅ **Familiar interface** (30 years of muscle memory)
- ❌ **Collaboration requires Office 365** (more vendor lock-in)
- ❌ **Version control nightmare** ("Track Changes" isn't real version control)
- ❌ **File corruption** (corrupted .docx files are data loss)
- ❌ **Platform inconsistencies** (looks different on Mac vs Windows vs web)

### Markdown: So Close, Yet So Far
- ✅ **Plain text** (works in any editor, git-friendly)
- ✅ **Universal support** (GitHub, Reddit, Discord all use it)
- ✅ **Future-proof** (will work in 50 years)
- ❌ **No semantic relationships** (can't express "this supports that argument")
- ❌ **No rich metadata** (authorship, permissions, change history)
- ❌ **No standardized sharing** (everyone has their own flavor)

## The Real Problem: False Choice Between Features

Current document formats force you to choose:
- **Portable** OR **Editable** (PDF vs Word)
- **Collaborative** OR **Version Controlled** (Google Docs vs Git)
- **Rich formatting** OR **Future-proof** (Word vs Markdown)
- **Semantic meaning** OR **Universal editing** (Structured data vs plain text)

**What if you didn't have to choose?**

## The ORMD Solution: Building on What Actually Works

ORMD isn't reinventing the wheel - it's combining the best parts of existing solutions:

### Built on Proven Standards
- **CommonMark** → The markdown syntax everyone already knows
- **YAML front-matter** → Used by Jekyll, Hugo, Obsidian, and countless others
- **ZIP packaging** → Universal compression, works everywhere
- **Cryptographic signatures** → Same tech securing the entire internet
- **Git workflows** → Fork, merge, attribution patterns developers trust

### Core Innovation: Semantic Relationships

ORMD documents use a single YAML front-matter block for all metadata, placed at the very beginning of the file after the `<!-- ormd:0.1 -->` version tag. This block is delimited by `---` on lines by themselves.

```markdown
---
title: Research Paper
links:
  - id: methodology-support
    rel: supports
    to: "#methodology"
  - id: contrary-evidence  
    rel: refutes
    to: "#opposing-view"
---

# Research Paper

Our findings [[methodology-support]] show clear evidence.
However, [[contrary-evidence]] suggests we need more data.

## Methodology {#methodology}
We used standard protocols...

## Opposing View {#opposing-view}
Critics argue that...
```

**The magic:** `[[link-id]]` becomes clickable relationships with semantic meaning. Not just "click here" but "this supports that argument" or "this refutes that claim."

### Document Lifecycle: Draft → Published → Signed

#### Draft Mode (.ormd file)
```
document.ormd  # Plain text, editable in anything
```
- Edit in **any text editor** (VS Code, Vim, Notepad, phone notes app)
- **Git version control** works perfectly (diffs, merges, blame)
- **Collaboration** through pull requests and forks
- **No vendor lock-in** (it's just text)

#### Published Mode (.ormd.zip package)
```
document.ormd.zip
├── content.ormd     # The document
├── meta.json       # Rich metadata, permissions
└── assets/         # Images, data files
    ├── chart.png
    └── data.csv
```
- **Self-contained** like PDF (everything in one file)
- **Still editable** (unpack, edit, repack)
- **Rich metadata** (authorship, creation date, word count)
- **Asset embedding** (images, spreadsheets, charts)

#### Signed Mode (.ormd.zip + cryptographic signature)
```
document-signed.ormd.zip  # Cryptographically frozen
```
- **Tamper-evident** (any change breaks the signature)
- **Legal permanence** (like PDF for government/legal use)
- **Provenance chain** (who signed when, with what key)
- **Still readable** (even if signature is broken)

### The "Excel Killer" Feature

Ever tried to version control an Excel file? It's impossible. But ORMD can convert spreadsheets to human-readable text while preserving formulas:

```markdown
## Q4 Budget

| Category | Budget | Actual | Variance |
|----------|--------|--------|----------|
| Marketing | $50,000 | $45,000 | `=C2-B2` |
| Engineering | $200,000 | $210,000 | `=C3-B3` |

**Total Variance:** `=SUM(D2:D3)`
```

**The breakthrough:** Formulas become visible text, but calculations still work. Suddenly Excel files can be version controlled, collaborated on, and understood without Excel.

## Universal Editing: The Real Innovation

ORMD files work in:
- **VS Code** (with syntax highlighting)
- **Vim** (because vim works everywhere)
- **Notepad** (on any Windows machine)
- **TextEdit** (on any Mac)
- **Phone notes apps** (edit documents on mobile)
- **Web browsers** (view and edit without installing anything)
- **Obsidian** (for knowledge management folks)
- **Any text editor ever made**

**No custom software required.** If you can edit text, you can edit ORMD.

## Real-World Use Cases

### Academic Writing
```bash
# Write paper in any editor
vim research-paper.ormd

# Collaborate with Git
git add research-paper.ormd
git commit -m "Add methodology section"
git push

# Colleague reviews
git checkout -b peer-review
# Edit document, add comments
git commit -m "Suggest methodology improvements"
git push

# Merge changes
git merge peer-review

# Submit to journal
ormd sign research-paper.ormd --key=university.pem
# Creates tamper-proof submission
```

### Legal Documents
```bash
# Draft contract
ormd init contract.ormd --template=legal

# Negotiate changes (tracked in Git)
git log --oneline contract.ormd
# abc1234 Add termination clause
# def5678 Adjust payment terms  
# ghi9012 Initial draft

# Final execution
ormd sign contract.ormd --key=law-firm.pem
# Legal permanence achieved
```

### Corporate Documentation
```bash
# Write in markdown, get PDF output
ormd render handbook.ormd --format=pdf

# Convert existing Excel to ORMD
ormd convert budget.xlsx --output=budget.ormd
# Now your spreadsheet is version controllable!

# Share with team
ormd publish handbook.ormd --permissions=read-only
# Creates shareable package
```

## Why This Will Work

### 1. **Progressive Enhancement**
- Start with plain text (works everywhere)
- Add metadata when needed (ZIP packaging)
- Add signatures when required (legal permanence)

### 2. **Network Effects**
- More ORMD files → more tool support
- More tools → easier adoption
- Easier adoption → more files

### 3. **No Vendor Lock-in**
- Plain text foundation means you can always get your data out
- Open source tools mean no subscription fees
- Standard formats mean 50-year compatibility

### 4. **Solves Real Pain Points**
- **Collaboration:** Git workflows everyone already knows
- **Version control:** Diffs and merges that actually work
- **Portability:** One file contains everything
- **Future-proofing:** Built on text and open standards

## Current Status

✅ **Working CLI** (`validate`, `pack`, `unpack`, `render`)  
✅ **HTML renderer** with semantic link visualization  
✅ **Single-file format** (no ZIP required for simple docs)  
✅ **Relationship graph** (see document structure visually)  
⏳ **Asset embedding** (images, spreadsheets)  
⏳ **VS Code extension** (syntax highlighting, preview)  
⏳ **Cryptographic signing** (tamper-proof documents)  
⏳ **Format converters** (Excel → ORMD, Word → ORMD)  

## Get Started

```bash
# Install
pip install ormd-cli

# Create your first document
ormd init my-document.ormd

# Edit in any text editor
code my-document.ormd

# Render to HTML
ormd render my-document.ormd
# Creates portable HTML file

# Validate
ormd validate my-document.ormd

# Share as package
ormd publish my-document.ormd
# Creates self-contained .ormd.zip
```

## Context Layer Features (Experimental)

ORMD now includes experimental support for **conversation lineage tracking** and **explicit uncertainty levels**. This allows documents to carry context about their origins and confidence levels, making it easier to hand off context between AI conversations and collaborative sessions.

### New YAML Fields

```yaml
context:
  lineage:
    source: "claude-conversation-2025-09-18"
    parent_docs: ["previous-discussion.ormd"]
  resolution:
    confidence: "exploratory"  # exploratory | working | validated
```

### Context Schema

- **`context.lineage.source`**: Identifier for the conversation, session, or process that created this document
- **`context.lineage.parent_docs`**: Array of parent document paths that this document derives from or builds upon
- **`context.resolution.confidence`**: Explicit uncertainty level:
  - `exploratory`: Early ideas, brainstorming, uncertain conclusions
  - `working`: Tested concepts with reasonable confidence
  - `validated`: High confidence, tested/reviewed content

### Example Usage

```markdown
<!-- ormd:0.1 -->
---
title: "Meeting Notes - Project Alpha"
authors: ["Alice", "Bob"]
context:
  lineage:
    source: "zoom-meeting-2025-09-18"
    parent_docs: ["project-alpha-charter.ormd"]
  resolution:
    confidence: "working"
---

# Meeting Notes

Based on our [[charter-review]] discussion, we've decided...
```

### Planned CLI Extensions

Future CLI commands will support context management:

```bash
# Create document with conversation lineage
ormd create --from-conversation my-notes.ormd

# Link documents in parent-child relationships  
ormd link parent.ormd child.ormd

# Trace document lineage chain
ormd trace document.ormd
```

**Note**: This is experimental MVP functionality focused on solving the "context handoff problem" between AI conversations and collaborative sessions. The schema may evolve based on usage feedback.

## The Philosophy

**Documents should be:**
- **Human-readable** (you can understand them without special software)
- **Machine-processable** (tools can extract meaning and relationships)
- **Universally editable** (any text editor works)
- **Version controllable** (Git treats them like code)
- **Portable** (one file contains everything)
- **Future-proof** (will work in 50 years)

**ORMD is what PDF should have been if it was designed today.**

---

*"The best way to predict the future is to invent it." - Alan Kay*

We're not just building a file format. We're building the future of human knowledge sharing.