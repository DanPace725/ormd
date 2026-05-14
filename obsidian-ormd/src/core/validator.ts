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

  if (parsed.frontMatter) {
    validateFrontMatter(parsed.frontMatter, errors);
    validateLinks(parsed.frontMatter, parsed.body, parsed.autoLinks, errors, warnings);
  }

  return {
    ...parsed,
    diagnostics: [...errors, ...warnings],
    errors,
    warnings,
    valid: errors.length === 0,
  };
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
): void {
  const manualLinks = Array.isArray(frontMatter.links)
    ? frontMatter.links.filter(isLinkLike).map((link) => ({ ...link, source: link.source ?? "manual" }))
    : [];

  const mergedLinks: OrmdLink[] = [...manualLinks];
  const seenTargetRels = new Set(manualLinks.map((link) => `${link.to ?? ""}\u0000${link.rel ?? ""}`));

  for (const autoLink of autoLinks) {
    const key = `${autoLink.target ?? ""}\u0000${autoLink.rel ?? ""}`;
    if (!seenTargetRels.has(key)) {
      mergedLinks.push({ ...autoLink, to: autoLink.target });
      seenTargetRels.add(key);
    }
  }

  const bodyRefs = new Set([...body.matchAll(/\[\[([^\]]+)\]\]/g)].map((match) => match[1]));
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

  for (const ref of bodyRefs) {
    if (!definedIds.has(ref)) {
      errors.push({
        severity: "error",
        message: `Undefined link reference [[${ref}]]. Add a matching entry to the front-matter links section.`,
      });
    }
  }
}

function hasNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isLinkLike(value: unknown): value is OrmdLink {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
