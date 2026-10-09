import { APPROVED_LINK_RELATIONSHIPS } from "./relationships";
import { parseOrmd } from "./parser";
import type { OrmdDiagnostic, OrmdFrontMatter, OrmdLink, OrmdValidationResult, YamlParser } from "./types";

const ALLOWED_FRONT_MATTER_KEYS = new Set([
  "title",
  "authors",
  "links",
  "dates",
  "metrics",
  "permissions",
  "version",
  "status",
  "description",
  "language",
  "license",
  "keywords",
  "link_ids",
  "asset_ids",
]);

export function validateOrmd(content: string, parseYaml: YamlParser): OrmdValidationResult {
  const parsed = parseOrmd(content, parseYaml);
  const errors = parsed.diagnostics.filter((diagnostic) => diagnostic.severity === "error");
  const warnings = parsed.diagnostics.filter((diagnostic) => diagnostic.severity === "warning");
  const bodyStartLine = parsed.bodyStartLine ?? 1;

  if (parsed.frontMatter) {
    if (content.replace(/^\uFEFF/, "").startsWith("<!-- ormd:1.0 -->")) {
      validateCoreFrontMatter(parsed.frontMatter, parsed.body, errors);
    } else {
      validateFrontMatter(parsed.frontMatter, errors);
      validateLinks(parsed.frontMatter, parsed.body, parsed.autoLinks, errors, warnings, bodyStartLine);
      validateAnchors(parsed.frontMatter, parsed.body, errors, bodyStartLine);
    }
  }

  return {
    ...parsed,
    diagnostics: [...errors, ...warnings],
    errors,
    warnings,
    valid: errors.length === 0,
  };
}

function validateCoreFrontMatter(frontMatter: OrmdFrontMatter, body: string, errors: OrmdDiagnostic[]): void {
  for (const key of ["title", "frame", "lineage", "policy", "semantics", "resolution"]) {
    if (!(key in frontMatter) || frontMatter[key] === null || frontMatter[key] === "") {
      errors.push({ severity: "error", message: `Missing required front-matter field '${key}'.` });
    }
  }
  if (!/^# /m.test(body)) {
    errors.push({ severity: "error", message: "Missing level-one document heading." });
  }
}

function validateFrontMatter(frontMatter: OrmdFrontMatter, errors: OrmdDiagnostic[]): void {
  for (const key of Object.keys(frontMatter)) {
    if (!ALLOWED_FRONT_MATTER_KEYS.has(key)) {
      errors.push({ severity: "error", message: `Unknown field in front-matter: ${key}` });
    }
  }

  if (!hasNonEmptyString(frontMatter.title)) {
    errors.push({ severity: "error", message: "Missing or invalid required field 'title'." });
  }

  if (!Array.isArray(frontMatter.authors) || frontMatter.authors.length === 0) {
    errors.push({ severity: "error", message: "Missing or invalid required field 'authors'." });
  }

  if (!Array.isArray(frontMatter.links)) {
    errors.push({ severity: "error", message: "Missing or invalid required field 'links'." });
  }
}

function validateLinks(
  frontMatter: OrmdFrontMatter,
  body: string,
  autoLinks: OrmdLink[],
  errors: OrmdDiagnostic[],
  warnings: OrmdDiagnostic[],
  bodyStartLine: number,
): void {
  const manualLinks = Array.isArray(frontMatter.links)
    ? frontMatter.links.filter(isLinkLike).map((link) => ({ ...link, source: link.source ?? "manual" }))
    : [];

  const mergedLinks: OrmdLink[] = [...manualLinks];
  const seenTargetRels = new Set(manualLinks.map((link) => `${link.to ?? ""}\0${link.rel ?? ""}`));

  for (const autoLink of autoLinks) {
    const key = `${autoLink.target ?? ""}\0${autoLink.rel ?? ""}`;
    if (!seenTargetRels.has(key)) {
      mergedLinks.push({ ...autoLink, to: autoLink.target });
      seenTargetRels.add(key);
    }
  }

  const bodyLines = body.split("\n");
  const bodyRefs = new Map<string, number>(); // linkId → first line number
  for (let i = 0; i < bodyLines.length; i++) {
    for (const match of bodyLines[i].matchAll(/\[\[([^\]]+)\]\]/g)) {
      if (!bodyRefs.has(match[1])) {
        bodyRefs.set(match[1], bodyStartLine + i);
      }
    }
  }

  const definedIds = new Set<string>();

  for (const link of mergedLinks) {
    if (!hasNonEmptyString(link.id)) {
      errors.push({ severity: "error", message: "Link is missing required field 'id'." });
      continue;
    }

    definedIds.add(link.id);

    const target = link.to ?? link.target;
    if (!hasNonEmptyString(target)) {
      errors.push({ severity: "error", message: `Link '${link.id}' is missing required field 'to'.` });
    }

    if (link.rel && !APPROVED_LINK_RELATIONSHIPS.has(link.rel)) {
      errors.push({ severity: "error", message: `Link '${link.id}' uses unapproved relationship '${link.rel}'.` });
    }

    if (!bodyRefs.has(link.id)) {
      warnings.push({ severity: "warning", message: `Link definition '${link.id}' is defined but not referenced.` });
    }
  }

  for (const [ref, line] of bodyRefs) {
    if (!definedIds.has(ref)) {
      errors.push({
        severity: "error",
        message: `Undefined link reference [[${ref}]]. Add a matching entry to the front-matter links section.`,
        line,
      });
    }
  }
}

/**
 * Validate that internal anchor targets (#anchor-id) in link definitions
 * actually exist in the document body.
 *
 * Anchors are detected from:
 * - Explicit HTML anchors: <a id="anchor-id"></a>
 * - Markdown headings: # Heading Text → #heading-text
 */
function validateAnchors(
  frontMatter: OrmdFrontMatter,
  body: string,
  errors: OrmdDiagnostic[],
  bodyStartLine: number,
): void {
  // Collect all anchors present in the document
  const anchors = new Set<string>();

  // Explicit HTML anchors: <a id="anchor-id"> or <a id='anchor-id'>
  for (const match of body.matchAll(/<a\s[^>]*id\s*=\s*["']([^"']+)["'][^>]*>/gi)) {
    anchors.add(match[1]);
  }

  // Markdown headings → slug-based anchors
  // e.g., "## My Heading" → "my-heading"
  for (const match of body.matchAll(/^#{1,6}\s+(.+)$/gm)) {
    const slug = headingToSlug(match[1]);
    anchors.add(slug);
  }

  // Check each link with a local anchor target
  const links = Array.isArray(frontMatter.links)
    ? frontMatter.links.filter(isLinkLike)
    : [];

  for (const link of links) {
    const target = link.to ?? link.target ?? "";

    // Only check local anchors (not cross-document ones like "file.ormd#section")
    if (!target.startsWith("#")) continue;

    const anchorId = target.slice(1);
    if (!anchorId) continue;

    if (!anchors.has(anchorId)) {
      errors.push({
        severity: "error",
        message: `Link '${link.id}' targets anchor '${target}' which does not exist in the document. ` +
          `Add <a id="${anchorId}"></a> or a heading that generates this anchor.`,
      });
    }
  }
}

/**
 * Convert a Markdown heading text to a slug-based anchor ID.
 * Matches the algorithm used by most Markdown renderers:
 * lowercase, strip non-alphanumeric (except hyphens/spaces), replace spaces with hyphens.
 */
function headingToSlug(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[^\w\s-]/g, "") // remove special characters
    .replace(/\s+/g, "-")      // spaces → hyphens
    .replace(/-+/g, "-")       // collapse multiple hyphens
    .replace(/^-|-$/g, "");    // trim leading/trailing hyphens
}

function hasNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isLinkLike(value: unknown): value is OrmdLink {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
