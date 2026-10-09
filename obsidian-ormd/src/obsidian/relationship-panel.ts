import { ItemView, MarkdownView, TFile, WorkspaceLeaf, parseYaml } from "obsidian";
import { parseOrmd } from "../core/parser";
import { navigateToTarget, parseLinkTarget } from "./navigate";
import type { OrmdLink, OrmdFrontMatter } from "../core/types";

export const RELATIONSHIP_PANEL_VIEW_TYPE = "ormd-relationship-panel";

/**
 * Sidebar panel that shows ORMD document metadata and semantic links.
 *
 * Displays:
 * - Document title and authors
 * - All defined links with relationship badges
 * - Warnings for unused links and undefined references
 */
export class RelationshipPanelView extends ItemView {
  private contentEl_: HTMLElement | null = null;
  private refreshId = 0;

  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return RELATIONSHIP_PANEL_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "ORMD Relationships";
  }

  getIcon(): string {
    return "link";
  }

  async onOpen(): Promise<void> {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("ormd-relationship-panel");

    this.contentEl_ = container.createDiv({ cls: "ormd-panel-content" });

    // Initial render
    await this.refresh();

    // Listen for file changes
    this.registerEvent(
      this.app.workspace.on("file-open", () => {
        void this.refresh();
      }),
    );

    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => {
        void this.refresh();
      }),
    );

    this.registerEvent(
      this.app.vault.on("modify", (file) => {
        const activeFile = this.getActiveOrmdFile();
        if (activeFile && file.path === activeFile.path) {
          void this.refresh();
        }
      }),
    );
  }

  async onClose(): Promise<void> {
    this.contentEl_ = null;
  }

  async refresh(): Promise<void> {
    if (!this.contentEl_) return;
    const refreshId = ++this.refreshId;
    this.contentEl_.empty();

    const file = this.getActiveOrmdFile();
    if (!file) {
      this.contentEl_.createEl("p", {
        text: "Open an .ormd file to see its relationships.",
        cls: "ormd-panel-placeholder",
      });
      return;
    }

    const content = await this.app.vault.read(file);
    if (refreshId !== this.refreshId || !this.contentEl_) return;
    const parsed = parseOrmd(content, parseYaml);

    if (!parsed.frontMatter) {
      this.contentEl_.createEl("p", {
        text: "Could not parse front-matter.",
        cls: "ormd-panel-error",
      });
      return;
    }

    this.renderHeader(parsed.frontMatter, file);
    this.renderLinks(parsed.frontMatter, parsed.body, parsed.autoLinks, file);
    this.renderDiagnostics(parsed.frontMatter, parsed.body);
  }

  private renderHeader(fm: OrmdFrontMatter, file: TFile): void {
    if (!this.contentEl_) return;

    // Title
    const title = typeof fm.title === "string" ? fm.title : file.basename;
    this.contentEl_.createEl("h3", { text: title, cls: "ormd-panel-title" });

    // Authors
    if (Array.isArray(fm.authors) && fm.authors.length > 0) {
      const authorsDiv = this.contentEl_.createDiv({ cls: "ormd-panel-authors" });
      const authorNames = fm.authors.map((a: unknown) => {
        if (typeof a === "string") return a;
        if (typeof a === "object" && a !== null && "display" in a) {
          return String((a as Record<string, unknown>).display);
        }
        if (typeof a === "object" && a !== null && "id" in a) {
          return String((a as Record<string, unknown>).id);
        }
        return String(a);
      });
      authorsDiv.createEl("span", {
        text: authorNames.join(", "),
        cls: "ormd-panel-author-list",
      });
    }

    // Status / Version
    const metaDiv = this.contentEl_.createDiv({ cls: "ormd-panel-meta" });
    if (typeof fm.status === "string") {
      const badge = metaDiv.createEl("span", { cls: "ormd-panel-status-badge" });
      badge.textContent = fm.status;
      badge.addClass(`ormd-status-${fm.status}`);
    }
    if (typeof fm.version === "string") {
      metaDiv.createEl("span", {
        text: `v${fm.version}`,
        cls: "ormd-panel-version",
      });
    }
  }

  private renderLinks(fm: OrmdFrontMatter, body: string, autoLinks: OrmdLink[], file: TFile): void {
    if (!this.contentEl_) return;

    const links = Array.isArray(fm.links)
      ? (fm.links as OrmdLink[]).filter(
          (l): l is OrmdLink => typeof l === "object" && l !== null && !Array.isArray(l),
        )
      : [];

    if (links.length === 0 && autoLinks.length === 0) {
      this.contentEl_.createEl("h4", { text: "Links" });
      this.contentEl_.createEl("p", {
        text: "No links defined.",
        cls: "ormd-panel-placeholder",
      });
      return;
    }

    // Front-matter links
    if (links.length > 0) {
      this.contentEl_.createEl("h4", { text: `Links (${links.length})` });
      const linkList = this.contentEl_.createDiv({ cls: "ormd-panel-link-list" });

      for (const link of links) {
        this.renderLinkItem(linkList, link, body, file);
      }
    }

    // Auto-detected inline links
    if (autoLinks.length > 0) {
      this.contentEl_.createEl("h4", { text: `Inline Links (${autoLinks.length})` });
      const autoList = this.contentEl_.createDiv({ cls: "ormd-panel-link-list" });

      for (const link of autoLinks) {
        this.renderLinkItem(autoList, { ...link, to: link.target }, body, file);
      }
    }
  }

  private renderLinkItem(container: HTMLElement, link: OrmdLink, body: string, file: TFile): void {
    const row = container.createDiv({ cls: "ormd-panel-link" });

    const target = link.to ?? link.target ?? "";
    const parsed = parseLinkTarget(target);

    // Make the whole row clickable for navigation
    if (target) {
      row.addClass("ormd-panel-link-clickable");
      row.setAttribute("title", `Click to navigate to ${target}`);
      row.addEventListener("click", () => {
        navigateToTarget(target, file.path);
      });
    }

    // Relationship badge
    if (link.rel) {
      const badge = row.createEl("span", { cls: "ormd-panel-rel-badge" });
      badge.textContent = link.rel;
      badge.addClass(`ormd-rel-${link.rel}`);
    }

    // Link info
    const info = row.createDiv({ cls: "ormd-panel-link-info" });
    info.createEl("span", {
      text: link.id || "(no id)",
      cls: "ormd-panel-link-id",
    });

    if (target) {
      const targetEl = info.createEl("span", {
        cls: "ormd-panel-link-target",
      });

      // Show a friendly label for file links
      if (parsed.kind === "file" && parsed.filePath) {
        const fileName = parsed.filePath.replace(/\.ormd$/, "");
        const fragment = parsed.fragment ? `#${parsed.fragment}` : "";
        targetEl.textContent = ` → 📄 ${fileName}${fragment}`;
      } else if (parsed.kind === "anchor") {
        targetEl.textContent = ` → ${target}`;
      } else {
        targetEl.textContent = ` → 🔗 ${target}`;
      }
    }

    // Referenced check
    if (link.id && body) {
      const pattern = `[[${link.id}]]`;
      if (!body.includes(pattern)) {
        const warning = row.createEl("span", { cls: "ormd-panel-link-warning" });
        warning.textContent = "⚠ unused";
        warning.setAttribute("title", "This link is defined but not referenced in the body");
      }
    }
  }

  private renderDiagnostics(fm: OrmdFrontMatter, body: string): void {
    if (!this.contentEl_) return;

    // Find undefined references in body
    const definedIds = new Set<string>();
    if (Array.isArray(fm.links)) {
      for (const link of fm.links as OrmdLink[]) {
        if (typeof link === "object" && link !== null && link.id) {
          definedIds.add(link.id);
        }
      }
    }

    const bodyRefs = [...body.matchAll(/\[\[([^\]]+)\]\]/g)].map((m) => m[1]);
    const undefinedRefs = bodyRefs.filter((ref) => !definedIds.has(ref));

    if (undefinedRefs.length > 0) {
      this.contentEl_.createEl("h4", { text: "Issues" });
      const issueList = this.contentEl_.createDiv({ cls: "ormd-panel-issues" });

      for (const ref of undefinedRefs) {
        const issue = issueList.createDiv({ cls: "ormd-panel-issue" });
        issue.createEl("span", {
          text: `❌ Undefined: [[${ref}]]`,
          cls: "ormd-panel-issue-error",
        });
      }
    }
  }

  private getActiveOrmdFile(): TFile | null {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    const file = view?.file ?? this.app.workspace.getActiveFile();
    if (file && file.extension === "ormd") return file;
    return null;
  }
}
