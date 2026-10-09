import { Editor, MarkdownView, Modal, Notice, Plugin, Setting, TFile, parseYaml } from "obsidian";
import { validateOrmd } from "./core/validator";
import { parseOrmd } from "./core/parser";
import {
  splitDocument,
  reassembleDocument,
  countWords,
  estimateReadingTime,
  extractInlineLinks,
  mergeLinks,
} from "./core/serializer";
import { APPROVED_LINK_RELATIONSHIPS } from "./core/relationships";
import { createOrmdPostProcessor } from "./obsidian/postprocessor";
import { ormdEditorExtension } from "./obsidian/extensions";
import { setApp, clearApp } from "./obsidian/navigate";
import { RelationshipPanelView, RELATIONSHIP_PANEL_VIEW_TYPE } from "./obsidian/relationship-panel";
import type { OrmdValidationResult, OrmdLink } from "./core/types";

export default class OrmdPlugin extends Plugin {
  private statusBarItem: HTMLElement | null = null;

  async onload(): Promise<void> {
    // Initialize the shared navigation module with our App reference
    setApp(this.app);

    this.registerExtensions(["ormd"], "markdown");

    this.statusBarItem = this.addStatusBarItem();
    this.statusBarItem.addClass("ormd-status");
    this.statusBarItem.setText("ORMD");

    // ── Commands ──

    this.addCommand({
      id: "validate-current-ormd-file",
      name: "Validate current ORMD file",
      callback: () => {
        void this.validateActiveFile(true);
      },
    });

    this.addCommand({
      id: "update-generated-metadata",
      name: "Update generated metadata",
      callback: () => {
        void this.updateMetadata();
      },
    });

    this.addCommand({
      id: "insert-semantic-link",
      name: "Insert semantic link",
      editorCallback: (editor: Editor) => {
        new InsertLinkModal(this.app, editor).open();
      },
    });

    this.addCommand({
      id: "open-relationship-panel",
      name: "Open relationship panel",
      callback: () => {
        void this.activateRelationshipPanel();
      },
    });

    // ── Views ──

    this.registerView(
      RELATIONSHIP_PANEL_VIEW_TYPE,
      (leaf) => new RelationshipPanelView(leaf),
    );

    // ── Events ──

    this.registerEvent(
      this.app.workspace.on("file-open", () => {
        void this.validateActiveFile(false);
      }),
    );

    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => {
        void this.validateActiveFile(false);
      }),
    );

    // Register reading-view postprocessor for [[link-id]] rendering
    this.registerMarkdownPostProcessor(
      createOrmdPostProcessor(
        async () => {
          const file = this.getActiveFile();
          if (!file || file.extension !== "ormd") return null;
          return await this.app.vault.read(file);
        },
        () => this.getActiveFile()?.path ?? "",
      ),
    );

    // Register Live Preview decorations for [[link-id]] and inline semantic links
    this.registerEditorExtension(ormdEditorExtension);

    await this.validateActiveFile(false);
  }

  onunload(): void {
    this.statusBarItem = null;
    clearApp();
    this.app.workspace.detachLeavesOfType(RELATIONSHIP_PANEL_VIEW_TYPE);
  }

  private async activateRelationshipPanel(): Promise<void> {
    const existing = this.app.workspace.getLeavesOfType(RELATIONSHIP_PANEL_VIEW_TYPE);
    if (existing.length > 0) {
      this.app.workspace.revealLeaf(existing[0]);
      return;
    }

    const leaf = this.app.workspace.getRightLeaf(false);
    if (leaf) {
      await leaf.setViewState({
        type: RELATIONSHIP_PANEL_VIEW_TYPE,
        active: true,
      });
      this.app.workspace.revealLeaf(leaf);
    }
  }

  // ── Validation ──

  private async validateActiveFile(showNotice: boolean): Promise<void> {
    const file = this.getActiveFile();

    if (!file || file.extension !== "ormd") {
      this.updateStatus(null);
      return;
    }

    const content = await this.app.vault.read(file);
    const result = validateOrmd(content, parseYaml);
    this.updateStatus(result);

    if (showNotice) {
      new Notice(formatNotice(file, result));
    }
  }

  // ── Metadata Update ──

  private async updateMetadata(): Promise<void> {
    const file = this.getActiveFile();

    if (!file || file.extension !== "ormd") {
      new Notice("No active ORMD file.");
      return;
    }

    const content = await this.app.vault.read(file);
    if (content.trimStart().startsWith("<!-- ormd:1.0 -->")) {
      new Notice("Core Framework ORMD 1.0 metadata is source-managed; automatic metadata updates are unavailable.");
      return;
    }
    const parts = splitDocument(content);

    if (!parts) {
      new Notice("Cannot parse document structure. Is the version tag and front-matter present?");
      return;
    }

    // Parse the existing front-matter
    let yaml: Record<string, unknown>;
    try {
      const parsed = parseYaml(parts.yaml);
      yaml = (parsed && typeof parsed === "object" && !Array.isArray(parsed))
        ? parsed as Record<string, unknown>
        : {};
    } catch {
      new Notice("Cannot parse existing front-matter YAML.");
      return;
    }

    // Track changes for the notice
    const changes: string[] = [];

    // 1. Auto-populate inline links into the links array
    const existingLinks = Array.isArray(yaml.links) ? yaml.links as OrmdLink[] : [];
    const inlineLinks = extractInlineLinks(parts.body);

    if (inlineLinks.length > 0) {
      const merged = mergeLinks(existingLinks, inlineLinks);
      const newCount = merged.length - existingLinks.length;
      if (newCount > 0) {
        yaml.links = merged;
        changes.push(`+${newCount} inline link${newCount > 1 ? "s" : ""}`);
      }
    }

    // 2. Update dates.modified
    if (!yaml.dates || typeof yaml.dates !== "object") {
      yaml.dates = {};
    }
    const dates = yaml.dates as Record<string, unknown>;
    dates.modified = new Date().toISOString();
    changes.push("updated dates.modified");

    // 3. Update metrics
    const wordCount = countWords(parts.body);
    const readingTime = estimateReadingTime(wordCount);
    if (!yaml.metrics || typeof yaml.metrics !== "object") {
      yaml.metrics = {};
    }
    const metrics = yaml.metrics as Record<string, unknown>;
    metrics.word_count = wordCount;
    metrics.reading_time = readingTime;
    changes.push(`word_count: ${wordCount}`);

    // 4. Serialize back
    // We use a simple approach: stringify the updated YAML object
    const newYaml = serializeYaml(yaml);
    parts.yaml = newYaml;

    const newContent = reassembleDocument(parts);
    await this.app.vault.modify(file, newContent);

    new Notice(`Metadata updated: ${changes.join(", ")}`);
    void this.validateActiveFile(false);
  }

  // ── Helpers ──

  private getActiveFile(): TFile | null {
    const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
    return activeView?.file ?? this.app.workspace.getActiveFile();
  }

  private updateStatus(result: OrmdValidationResult | null): void {
    if (!this.statusBarItem) {
      return;
    }

    this.statusBarItem.removeClass("is-valid");
    this.statusBarItem.removeClass("has-errors");
    this.statusBarItem.removeClass("has-warnings");

    if (!result) {
      this.statusBarItem.setText("");
      return;
    }

    if (result.errors.length > 0) {
      this.statusBarItem.addClass("has-errors");
      this.statusBarItem.setText(`ORMD: ${result.errors.length} error${plural(result.errors.length)}`);
      return;
    }

    if (result.warnings.length > 0) {
      this.statusBarItem.addClass("has-warnings");
      this.statusBarItem.setText(`ORMD: ${result.warnings.length} warning${plural(result.warnings.length)}`);
      return;
    }

    this.statusBarItem.addClass("is-valid");
    this.statusBarItem.setText("ORMD: valid");
  }
}

// ── Insert Semantic Link Modal ──

class InsertLinkModal extends Modal {
  private editor: Editor;
  private linkTarget = "";
  private linkRel = "";
  private linkText = "";

  constructor(app: import("obsidian").App, editor: Editor) {
    super(app);
    this.editor = editor;

    // Pre-fill with selected text if any
    const selection = editor.getSelection();
    if (selection) {
      this.linkText = selection;
    }
  }

  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl("h3", { text: "Insert Semantic Link" });

    new Setting(contentEl)
      .setName("Display text")
      .setDesc("The visible link text")
      .addText((text) => {
        text.setValue(this.linkText);
        text.onChange((value) => { this.linkText = value; });
        text.inputEl.focus();
      });

    new Setting(contentEl)
      .setName("Target")
      .setDesc("URL, anchor (#section), or file path")
      .addText((text) => {
        text.setPlaceholder("#section-id or https://...");
        text.onChange((value) => { this.linkTarget = value; });
      });

    new Setting(contentEl)
      .setName("Relationship")
      .setDesc("Semantic relationship type (optional)")
      .addDropdown((dropdown) => {
        dropdown.addOption("", "(none)");
        for (const rel of APPROVED_LINK_RELATIONSHIPS) {
          dropdown.addOption(rel, rel);
        }
        dropdown.onChange((value) => { this.linkRel = value; });
      });

    new Setting(contentEl)
      .addButton((btn) => {
        btn.setButtonText("Insert")
          .setCta()
          .onClick(() => {
            this.insertLink();
            this.close();
          });
      });
  }

  onClose(): void {
    this.contentEl.empty();
  }

  private insertLink(): void {
    if (!this.linkTarget) {
      new Notice("Link target is required.");
      return;
    }

    const displayText = this.linkText || this.linkTarget;
    let markdown: string;

    if (this.linkRel) {
      markdown = `[${displayText}](${this.linkTarget} "${this.linkRel}")`;
    } else {
      markdown = `[${displayText}](${this.linkTarget})`;
    }

    this.editor.replaceSelection(markdown);
  }
}

// ── Utilities ──

function formatNotice(file: TFile, result: OrmdValidationResult): string {
  if (result.valid && result.warnings.length === 0) {
    return `${file.name} is valid ORMD.`;
  }

  if (result.valid) {
    return `${file.name} is valid ORMD with ${result.warnings.length} warning${plural(result.warnings.length)}.`;
  }

  const firstError = result.errors[0]?.message ?? "Unknown validation error.";
  return `${file.name} has ${result.errors.length} error${plural(result.errors.length)}: ${firstError}`;
}

function plural(count: number): string {
  return count === 1 ? "" : "s";
}

/**
 * Simple YAML serializer for front-matter objects.
 * Produces clean, human-readable YAML.
 */
function serializeYaml(obj: Record<string, unknown>, indent = 0): string {
  const lines: string[] = [];
  const prefix = "  ".repeat(indent);

  for (const [key, value] of Object.entries(obj)) {
    if (value === undefined || value === null) continue;

    if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${prefix}${key}: []`);
      } else if (value.every((v) => typeof v === "string" || typeof v === "number")) {
        // Simple array of scalars
        lines.push(`${prefix}${key}:`);
        for (const item of value) {
          lines.push(`${prefix}  - ${yamlScalar(item)}`);
        }
      } else {
        // Array of objects
        lines.push(`${prefix}${key}:`);
        for (const item of value) {
          if (typeof item === "object" && item !== null && !Array.isArray(item)) {
            const entries = Object.entries(item as Record<string, unknown>);
            for (let i = 0; i < entries.length; i++) {
              const [k, v] = entries[i];
              if (v === undefined || v === null) continue;
              if (i === 0) {
                lines.push(`${prefix}  - ${k}: ${yamlScalar(v)}`);
              } else {
                lines.push(`${prefix}    ${k}: ${yamlScalar(v)}`);
              }
            }
          } else {
            lines.push(`${prefix}  - ${yamlScalar(item)}`);
          }
        }
      }
    } else if (typeof value === "object" && !(value instanceof Date)) {
      lines.push(`${prefix}${key}:`);
      lines.push(serializeYaml(value as Record<string, unknown>, indent + 1));
    } else {
      lines.push(`${prefix}${key}: ${yamlScalar(value)}`);
    }
  }

  return lines.join("\n");
}

/**
 * Format a scalar value for YAML output.
 */
function yamlScalar(value: unknown): string {
  if (typeof value === "string") {
    // Quote strings that contain special YAML characters or look like non-strings
    if (
      value === "" ||
      value === "true" || value === "false" ||
      value === "null" ||
      /^[\d.]+$/.test(value) ||
      /[:#\[\]{}&*!|>'"%@`]/.test(value) ||
      value.includes("\n")
    ) {
      return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
    }
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Date) {
    return `"${value.toISOString()}"`;
  }
  return String(value);
}
