import {
  Decoration,
  DecorationSet,
  EditorView,
  PluginSpec,
  PluginValue,
  ViewPlugin,
  ViewUpdate,
  WidgetType,
} from "@codemirror/view";
import { RangeSetBuilder } from "@codemirror/state";
import { navigateToTarget } from "./navigate";

/**
 * Widget that renders a resolved [[link-id]] inline in Live Preview.
 * Clicking navigates to the link target using Obsidian's API.
 */
class OrmdLinkWidget extends WidgetType {
  constructor(
    readonly linkId: string,
    readonly displayText: string,
    readonly rel: string | null,
    readonly target: string | null,
    readonly sourcePath: string,
    readonly isDefined: boolean,
  ) {
    super();
  }

  eq(other: OrmdLinkWidget): boolean {
    return (
      this.linkId === other.linkId &&
      this.displayText === other.displayText &&
      this.rel === other.rel &&
      this.target === other.target &&
      this.isDefined === other.isDefined
    );
  }

  toDOM(): HTMLElement {
    const span = document.createElement("span");

    if (this.isDefined) {
      const relClass = this.rel ? `ormd-rel-${this.rel}` : "ormd-rel-default";
      span.className = `ormd-link ${relClass}`;
      span.textContent = this.displayText;

      const tooltip = this.rel
        ? `${this.linkId} (${this.rel}) → ${this.target ?? ""}  · click to follow`
        : `${this.linkId} → ${this.target ?? ""}  · click to follow`;
      span.setAttribute("title", tooltip);

      // Indicate cross-document links visually
      if (this.target && !this.target.startsWith("#") && !this.target.startsWith("http")) {
        span.addClass("ormd-link-external-file");
      }

      // Navigate on click
      if (this.target) {
        const target = this.target;
        const sourcePath = this.sourcePath;
        span.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          navigateToTarget(target, sourcePath);
        });
      }
    } else {
      span.className = "ormd-link ormd-link-undefined";
      span.textContent = `[[${this.linkId}]]`;
      span.setAttribute("title", `Undefined ORMD link: ${this.linkId}`);
    }

    return span;
  }

  ignoreEvent(event: Event): boolean {
    // Allow click events through to our handler
    return event.type !== "click";
  }
}

/**
 * Widget that displays a relationship badge for inline semantic links.
 */
class OrmdRelBadgeWidget extends WidgetType {
  constructor(readonly rel: string) {
    super();
  }

  eq(other: OrmdRelBadgeWidget): boolean {
    return this.rel === other.rel;
  }

  toDOM(): HTMLElement {
    const badge = document.createElement("span");
    badge.className = `ormd-inline-rel-badge ormd-rel-${this.rel}`;
    badge.textContent = this.rel;
    badge.setAttribute("title", `Relationship: ${this.rel}`);
    return badge;
  }

  ignoreEvent(): boolean {
    return true;
  }
}

/** Matches [[link-id]] patterns */
const LINK_REF_RE = /\[\[([^\]]+)\]\]/g;

/** Matches [text](target "rel") patterns — only those with a quoted relationship */
const INLINE_LINK_RE = /\[([^\]]+)\]\(([^)]*?)\s+["']([^"']+)["']\)/g;

/**
 * A link definition extracted from front-matter for decoration purposes.
 */
interface LinkDef {
  id: string;
  displayText: string;
  rel: string | null;
  target: string | null;
}

/**
 * Extracts link definitions from the YAML front-matter in the document text.
 * Lightweight regex-based extraction to avoid a full YAML parser dependency.
 */
function extractLinkDefsFromText(docText: string): Map<string, LinkDef> {
  const map = new Map<string, LinkDef>();

  const versionTag = "<!-- ormd:0.1 -->";
  const trimmed = docText.trimStart();
  if (!trimmed.startsWith(versionTag)) return map;

  const afterVersion = trimmed.slice(versionTag.length).replace(/^\s*\r?\n?/, "");
  const fmStart = afterVersion.indexOf("---");
  if (fmStart !== 0) return map;

  const fmEndIndex = afterVersion.indexOf("\n---", 4);
  if (fmEndIndex === -1) return map;

  const fmContent = afterVersion.slice(4, fmEndIndex);

  const linkBlocks = fmContent.split(/\n\s*-\s+id:\s*/);

  for (let i = 1; i < linkBlocks.length; i++) {
    const block = linkBlocks[i];
    const idMatch = block.match(/^(\S+)/);
    if (!idMatch) continue;

    const id = idMatch[1].replace(/^["']|["']$/g, "");
    const relMatch = block.match(/\n\s+rel:\s*(\S+)/);
    const textMatch = block.match(/\n\s+text:\s*["']?([^"'\n]+)["']?/);
    const titleMatch = block.match(/\n\s+title:\s*["']?([^"'\n]+)["']?/);
    const toMatch = block.match(/\n\s+to:\s*["']?([^"'\n]+)["']?/);

    const rel = relMatch ? relMatch[1].replace(/^["']|["']$/g, "") : null;
    const target = toMatch ? toMatch[1].trim() : null;
    const displayText = textMatch
      ? textMatch[1].trim()
      : titleMatch
        ? titleMatch[1].trim()
        : id;

    map.set(id, { id, displayText, rel, target });
  }

  return map;
}

/**
 * Get the source file path from the EditorView.
 * Falls back to empty string if not determinable.
 */
function getSourcePathFromView(view: EditorView): string {
  // Obsidian attaches file info to the EditorView's state
  // We access it through the DOM — the editor lives inside a .workspace-leaf
  // whose data-path attribute contains the file path
  const leafEl = view.dom.closest(".workspace-leaf");
  if (leafEl) {
    const path = leafEl.getAttribute("data-path");
    if (path) return path;
  }

  // Fallback: try to find it from the view's state field
  // The file path is often in the Obsidian-specific state
  try {
    const state = view.state as unknown as Record<string, unknown>;
    if (state.file && typeof (state.file as Record<string, unknown>).path === "string") {
      return (state.file as Record<string, unknown>).path as string;
    }
  } catch {
    // ignore
  }

  return "";
}

/**
 * CodeMirror 6 ViewPlugin that decorates ORMD semantic links in Live Preview.
 *
 * Decorates:
 * - [[link-id]] references with resolved display text, relationship styling,
 *   and click-to-navigate behavior
 * - [text](target "rel") inline links with a relationship badge
 */
class OrmdEditorPlugin implements PluginValue {
  decorations: DecorationSet;

  constructor(view: EditorView) {
    this.decorations = this.buildDecorations(view);
  }

  update(update: ViewUpdate): void {
    if (update.docChanged || update.viewportChanged || update.selectionSet) {
      this.decorations = this.buildDecorations(update.view);
    }
  }

  destroy(): void {
    // nothing to clean up
  }

  private buildDecorations(view: EditorView): DecorationSet {
    const builder = new RangeSetBuilder<Decoration>();
    const docText = view.state.doc.toString();
    const linkDefs = extractLinkDefsFromText(docText);
    const sourcePath = getSourcePathFromView(view);

    const decos: Array<{ from: number; to: number; deco: Decoration }> = [];
    const cursorPos = view.state.selection.main.head;

    // Decorate [[link-id]] references
    LINK_REF_RE.lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = LINK_REF_RE.exec(docText)) !== null) {
      const from = match.index;
      const to = from + match[0].length;
      const linkId = match[1];

      if (cursorPos >= from && cursorPos <= to) continue;
      if (isInFrontMatter(docText, from)) continue;
      if (isInCodeBlock(docText, from)) continue;

      const def = linkDefs.get(linkId);

      const widget = new OrmdLinkWidget(
        linkId,
        def?.displayText ?? linkId,
        def?.rel ?? null,
        def?.target ?? null,
        sourcePath,
        def !== undefined,
      );

      decos.push({
        from,
        to,
        deco: Decoration.replace({ widget }),
      });
    }

    // Decorate relationship badges on [text](target "rel") links
    INLINE_LINK_RE.lastIndex = 0;

    while ((match = INLINE_LINK_RE.exec(docText)) !== null) {
      const from = match.index;
      const fullEnd = from + match[0].length;
      const rel = match[3];

      if (cursorPos >= from && cursorPos <= fullEnd) continue;
      if (isInFrontMatter(docText, from)) continue;
      if (isInCodeBlock(docText, from)) continue;

      decos.push({
        from: fullEnd,
        to: fullEnd,
        deco: Decoration.widget({
          widget: new OrmdRelBadgeWidget(rel),
          side: 1,
        }),
      });
    }

    decos.sort((a, b) => a.from - b.from || a.to - b.to);
    for (const { from, to, deco } of decos) {
      builder.add(from, to, deco);
    }

    return builder.finish();
  }
}

/** Check if a position is inside the YAML front-matter block. */
function isInFrontMatter(docText: string, pos: number): boolean {
  const versionTag = "<!-- ormd:0.1 -->";
  const trimmed = docText.trimStart();
  const offset = docText.length - trimmed.length;

  if (!trimmed.startsWith(versionTag)) return false;

  const afterVersion = trimmed.slice(versionTag.length);
  const fmStartRel = afterVersion.search(/\n---/);
  if (fmStartRel === -1) return false;

  const fmStart = offset + versionTag.length + fmStartRel;
  const fmEndRel = afterVersion.indexOf("\n---", fmStartRel + 4);
  if (fmEndRel === -1) return false;

  const fmEnd = offset + versionTag.length + fmEndRel + 4;
  return pos >= fmStart && pos <= fmEnd;
}

/** Simple check if a position is inside a fenced code block. */
function isInCodeBlock(docText: string, pos: number): boolean {
  const beforePos = docText.slice(0, pos);
  const fenceMatches = beforePos.match(/^```/gm);
  if (!fenceMatches) return false;
  return fenceMatches.length % 2 !== 0;
}

const pluginSpec: PluginSpec<OrmdEditorPlugin> = {
  decorations: (value) => value.decorations,
};

/** The exported CM6 extension for ORMD Live Preview decorations. */
export const ormdEditorExtension = ViewPlugin.fromClass(OrmdEditorPlugin, pluginSpec);
