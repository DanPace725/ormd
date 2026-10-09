import { MarkdownPostProcessorContext, parseYaml } from "obsidian";
import { navigateToTarget, parseLinkTarget } from "./navigate";
import type { OrmdFrontMatter, OrmdLink } from "../core/types";

/**
 * Relationship type → CSS class mapping.
 */
const REL_CLASSES: Record<string, string> = {
  supports: "ormd-rel-supports",
  refutes: "ormd-rel-refutes",
  cites: "ormd-rel-cites",
  references: "ormd-rel-references",
  related: "ormd-rel-related",
  extends: "ormd-rel-extends",
};

/** Pattern to match [[link-id]] text nodes in rendered HTML. */
const LINK_REF_PATTERN = /\[\[([^\]]+)\]\]/g;

/** Describes a resolved ORMD link for rendering. */
interface ResolvedLink {
  id: string;
  displayText: string;
  target: string;
  rel: string | null;
  cssClass: string;
}

/** Extract the links list from front-matter. */
function extractLinks(frontMatter: OrmdFrontMatter | null): OrmdLink[] {
  if (!frontMatter || !Array.isArray(frontMatter.links)) {
    return [];
  }
  return frontMatter.links.filter(
    (item: unknown): item is OrmdLink =>
      typeof item === "object" && item !== null && !Array.isArray(item),
  );
}

/** Build a lookup map from link ID to resolved link info. */
function buildLinkMap(links: OrmdLink[]): Map<string, ResolvedLink> {
  const map = new Map<string, ResolvedLink>();

  for (const link of links) {
    if (!link.id) continue;

    const target = (link.to ?? link.target) || "";
    const rel = link.rel ?? null;
    const displayText = link.text || link.title || link.id;
    const relClass = rel && REL_CLASSES[rel] ? REL_CLASSES[rel] : "ormd-rel-default";
    const cssClass = `ormd-link ${relClass}`;

    map.set(link.id, { id: link.id, displayText, target, rel, cssClass });
  }

  return map;
}

/**
 * Parse ORMD front-matter from raw file content.
 */
function parseFrontMatterFromContent(content: string): OrmdFrontMatter | null {
  const VERSION_TAG = "<!-- ormd:0.1 -->";
  const trimmed = content.trimStart();

  if (!trimmed.startsWith(VERSION_TAG)) return null;

  const afterVersion = trimmed.slice(VERSION_TAG.length).replace(/^\s*\r?\n?/, "");
  const normalized = afterVersion.replace(/\r\n/g, "\n").trim();

  if (!normalized.startsWith("---\n")) return null;

  const lines = normalized.split("\n");
  let closingLine = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      closingLine = i;
      break;
    }
  }

  if (closingLine === -1) return null;

  const yamlContent = lines.slice(1, closingLine).join("\n");
  if (!yamlContent.trim()) return {};

  try {
    const parsed = parseYaml(yamlContent);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as OrmdFrontMatter;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * Create the markdown post-processor that transforms [[link-id]] references
 * in reading view into styled, clickable ORMD semantic links.
 *
 * Cross-document links navigate using Obsidian's openLinkText() API,
 * just like clicking a wiki-link.
 */
export function createOrmdPostProcessor(
  getActiveFileContent: () => Promise<string | null>,
  getSourcePath: () => string,
): (el: HTMLElement, ctx: MarkdownPostProcessorContext) => void {
  return (el: HTMLElement, ctx: MarkdownPostProcessorContext): void => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const textNodes: Text[] = [];

    let node: Node | null;
    while ((node = walker.nextNode())) {
      if (node.textContent && LINK_REF_PATTERN.test(node.textContent)) {
        textNodes.push(node as Text);
        LINK_REF_PATTERN.lastIndex = 0;
      }
    }

    if (textNodes.length === 0) return;

    void (async () => {
      const content = await getActiveFileContent();
      if (!content) return;

      const frontMatter = parseFrontMatterFromContent(content);
      const links = extractLinks(frontMatter);
      const linkMap = buildLinkMap(links);
      const sourcePath = getSourcePath();

      for (const textNode of textNodes) {
        if (!textNode.parentNode) continue;
        replaceTextNodeWithLinks(textNode, linkMap, sourcePath);
      }
    })();
  };
}

/**
 * Replace a text node containing [[link-id]] references with
 * clickable semantic link elements.
 */
function replaceTextNodeWithLinks(
  textNode: Text,
  linkMap: Map<string, ResolvedLink>,
  sourcePath: string,
): void {
  const text = textNode.textContent || "";
  const fragment = document.createDocumentFragment();
  let lastIndex = 0;

  LINK_REF_PATTERN.lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = LINK_REF_PATTERN.exec(text)) !== null) {
    const linkId = match[1];
    const matchStart = match.index;
    const matchEnd = matchStart + match[0].length;

    if (matchStart > lastIndex) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex, matchStart)));
    }

    const resolved = linkMap.get(linkId);
    if (resolved) {
      const anchor = createLinkElement(resolved, sourcePath);
      fragment.appendChild(anchor);
    } else {
      const errorSpan = document.createElement("span");
      errorSpan.className = "ormd-link ormd-link-undefined";
      errorSpan.textContent = `[[${linkId}]]`;
      errorSpan.setAttribute("title", `Undefined ORMD link: ${linkId}`);
      fragment.appendChild(errorSpan);
    }

    lastIndex = matchEnd;
  }

  if (lastIndex < text.length) {
    fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
  }

  textNode.parentNode?.replaceChild(fragment, textNode);
}

/**
 * Create a clickable anchor element for a resolved ORMD link.
 * Uses Obsidian's navigation API for cross-document links.
 */
function createLinkElement(resolved: ResolvedLink, sourcePath: string): HTMLElement {
  const anchor = document.createElement("a");
  anchor.className = resolved.cssClass;
  anchor.textContent = resolved.displayText;
  anchor.setAttribute("data-ormd-link-id", resolved.id);

  if (resolved.rel) {
    anchor.setAttribute("data-ormd-rel", resolved.rel);
  }

  // Tooltip with relationship and target
  const parsed = parseLinkTarget(resolved.target);
  let tooltipExtra = "";
  if (parsed.kind === "file") {
    tooltipExtra = ` · click to open ${parsed.filePath}`;
  }
  const tooltip = resolved.rel
    ? `${resolved.id} (${resolved.rel}) → ${resolved.target}${tooltipExtra}`
    : `${resolved.id} → ${resolved.target}${tooltipExtra}`;
  anchor.setAttribute("title", tooltip);

  // All link navigation goes through the shared navigate module
  anchor.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    navigateToTarget(resolved.target, sourcePath);
  });

  // Add visual indicator for cross-document links
  if (parsed.kind === "file") {
    anchor.addClass("ormd-link-external-file");
  }

  // Make it look like a proper link
  anchor.href = resolved.target;

  return anchor;
}
