import type { OrmdFrontMatter, OrmdLink } from "./types";

/**
 * Serialize front-matter changes back into an ORMD document,
 * preserving the version tag and minimizing YAML reformatting.
 *
 * Strategy: replace only the YAML block between the --- delimiters
 * while keeping the version tag and body untouched.
 */

const VERSION_TAG = "<!-- ormd:0.1 -->";

/**
 * Result of splitting an ORMD document into its structural parts.
 */
export interface OrmdDocumentParts {
  /** Text before the first --- (includes version tag + any whitespace) */
  preamble: string;
  /** The raw YAML content between --- delimiters (no delimiters included) */
  yaml: string;
  /** Everything after the closing --- */
  body: string;
}

/**
 * Split an ORMD document into preamble, yaml, and body.
 * Returns null if the document structure is invalid.
 */
export function splitDocument(content: string): OrmdDocumentParts | null {
  const trimmed = content.trimStart();

  if (!trimmed.startsWith(VERSION_TAG)) {
    return null;
  }

  const afterVersion = content.slice(content.indexOf(VERSION_TAG) + VERSION_TAG.length);
  const normalized = afterVersion.replace(/\r\n/g, "\n");

  // Find opening ---
  const openMatch = normalized.match(/^(\s*)\n---\n/);
  if (!openMatch) {
    // Try without leading whitespace
    const altMatch = normalized.match(/^(\s*\n?)---\n/);
    if (!altMatch) return null;
  }

  const openIdx = normalized.indexOf("---\n");
  if (openIdx === -1) return null;

  const yamlStart = openIdx + 4; // after "---\n"
  const closeIdx = normalized.indexOf("\n---", yamlStart);
  if (closeIdx === -1) return null;

  const preamble = content.slice(0, content.indexOf(VERSION_TAG) + VERSION_TAG.length) +
    normalized.slice(0, openIdx + 4); // includes version tag through opening ---\n

  const yaml = normalized.slice(yamlStart, closeIdx);
  const body = normalized.slice(closeIdx + 4); // after "\n---"

  return { preamble, yaml, body };
}

/**
 * Reassemble an ORMD document from parts.
 */
export function reassembleDocument(parts: OrmdDocumentParts): string {
  return `${parts.preamble}${parts.yaml}\n---${parts.body}`;
}

/**
 * Count words in a body of text (excluding YAML front-matter).
 * Simple word-boundary split, counting non-empty tokens.
 */
export function countWords(body: string): number {
  // Strip markdown syntax elements that shouldn't be counted
  const cleaned = body
    .replace(/^#+\s*/gm, "") // heading markers
    .replace(/\[\[([^\]]+)\]\]/g, "$1") // [[link-id]] → link-id
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1") // [text](url) → text
    .replace(/[`*_~]/g, "") // inline formatting
    .replace(/<[^>]+>/g, "") // HTML tags
    .replace(/^\s*[-*+]\s+/gm, ""); // list markers

  const words = cleaned.split(/\s+/).filter((w) => w.length > 0);
  return words.length;
}

/**
 * Generate a simple reading time estimate.
 */
export function estimateReadingTime(wordCount: number): string {
  const minutes = Math.max(1, Math.ceil(wordCount / 200));
  return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

/**
 * Scan document body for inline semantic links [text](target "rel")
 * and return link objects with auto-generated IDs.
 */
export function extractInlineLinks(body: string): OrmdLink[] {
  const links: OrmdLink[] = [];
  const pattern = /\[([^\]]+)\]\(([^)]*)\)/g;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(body)) !== null) {
    const [, text, inner] = match;
    const { target, rel } = splitInlineLinkInner(inner);

    links.push({
      id: `auto-link-${links.length + 1}`,
      text,
      to: target,
      rel: rel ?? undefined,
      source: "inline",
    });
  }

  return links;
}

/**
 * Split inline link inner content into target and optional relationship.
 * e.g. '#section "supports"' → { target: "#section", rel: "supports" }
 */
function splitInlineLinkInner(inner: string): { target: string; rel: string | null } {
  const trimmed = inner.trim();
  const match = /^(?<target>.+?)\s+(?<quote>["'])(?<rel>[^"']+)\k<quote>$/.exec(trimmed);
  if (!match?.groups) {
    return { target: trimmed, rel: null };
  }
  return {
    target: match.groups.target.trim(),
    rel: match.groups.rel,
  };
}

/**
 * Merge auto-detected inline links into an existing links array,
 * avoiding duplicates based on target+rel combination.
 */
export function mergeLinks(existing: OrmdLink[], incoming: OrmdLink[]): OrmdLink[] {
  const seen = new Set(
    existing.map((link) => `${link.to ?? ""}\0${link.rel ?? ""}`),
  );

  const merged = [...existing];

  for (const link of incoming) {
    const key = `${link.to ?? ""}\0${link.rel ?? ""}`;
    if (!seen.has(key)) {
      merged.push(link);
      seen.add(key);
    }
  }

  return merged;
}
