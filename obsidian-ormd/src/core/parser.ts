import type { OrmdDiagnostic, OrmdFrontMatter, OrmdLink, OrmdParseResult, YamlParser } from "./types";

const VERSION_TAG = "<!-- ormd:0.1 -->";

export function parseOrmd(content: string, parseYaml: YamlParser): OrmdParseResult {
  const diagnostics: OrmdDiagnostic[] = [];
  const autoLinks: OrmdLink[] = [];

  if (!content.trimStart().startsWith(VERSION_TAG)) {
    diagnostics.push({
      severity: "error",
      message: "Missing or invalid version tag. Add '<!-- ormd:0.1 -->' at the top of the document.",
    });
    return { frontMatter: null, body: "", autoLinks, diagnostics };
  }

  const withoutVersion = content.trimStart().slice(VERSION_TAG.length).replace(/^\s*\r?\n?/, "");
  const { frontMatter, body } = parseFrontMatterAndBody(withoutVersion, parseYaml, diagnostics);

  for (const match of body.matchAll(/\[([^\]]+)\]\(([^)]*)\)/g)) {
    const [, text, inner] = match;
    const { target, rel } = splitInlineLinkInner(inner);
    autoLinks.push({
      id: `auto-link-${autoLinks.length + 1}`,
      text,
      target,
      rel,
      source: "inline",
    });
  }

  if (hasAdditionalFrontMatterBlock(body)) {
    diagnostics.push({
      severity: "error",
      message: "Multiple YAML front-matter blocks found. Only one is allowed at the beginning of the document.",
    });
  }

  if (/^[ ]*\+\+\+meta\b/m.test(body)) {
    diagnostics.push({
      severity: "error",
      message: "`+++meta` blocks are no longer supported. All metadata must be in the YAML front-matter.",
    });
  }

  return { frontMatter, body, autoLinks, diagnostics };
}

export function splitInlineLinkInner(inner: string): { target: string; rel: string | null } {
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

function parseFrontMatterAndBody(
  content: string,
  parseYaml: YamlParser,
  diagnostics: OrmdDiagnostic[],
): { frontMatter: OrmdFrontMatter | null; body: string } {
  const normalized = content.replace(/\r\n/g, "\n").trim();
  const delimiter = normalized.startsWith("---\n") ? "---" : normalized.startsWith("+++\n") ? "+++" : null;

  if (!delimiter) {
    return { frontMatter: {}, body: normalized };
  }

  const lines = normalized.split("\n");
  let closingLine = -1;
  for (let index = 1; index < lines.length; index += 1) {
    if (lines[index].trim() === delimiter) {
      closingLine = index;
      break;
    }
  }

  if (closingLine === -1) {
    diagnostics.push({ severity: "error", message: "Invalid YAML in front-matter." });
    return { frontMatter: null, body: normalized };
  }

  const yamlContent = lines.slice(1, closingLine).join("\n");
  const body = lines.slice(closingLine + 1).join("\n").trim();

  if (!yamlContent.trim()) {
    return { frontMatter: {}, body };
  }

  try {
    const parsed = parseYaml(yamlContent);
    if (parsed === null || parsed === undefined) {
      return { frontMatter: {}, body };
    }
    if (!isRecord(parsed)) {
      diagnostics.push({ severity: "error", message: "Front-matter must be a YAML object." });
      return { frontMatter: null, body };
    }
    return { frontMatter: parsed as OrmdFrontMatter, body };
  } catch (error) {
    diagnostics.push({
      severity: "error",
      message: `Invalid YAML in front-matter: ${error instanceof Error ? error.message : String(error)}`,
    });
    return { frontMatter: null, body };
  }
}

export function hasAdditionalFrontMatterBlock(body: string): boolean {
  const lines = body.split(/\r?\n/);
  let inFence = false;
  let fenceMarker: "`" | "~" | null = null;

  for (let index = 0; index < lines.length; index += 1) {
    const stripped = lines[index].trim();
    const fenceMatch = /^(```+|~~~+)/.exec(stripped);
    if (fenceMatch) {
      const marker = fenceMatch[1][0] as "`" | "~";
      if (!inFence) {
        inFence = true;
        fenceMarker = marker;
      } else if (fenceMarker && stripped.startsWith(fenceMarker.repeat(3))) {
        inFence = false;
        fenceMarker = null;
      }
      continue;
    }

    if (inFence || (stripped !== "---" && stripped !== "+++")) {
      continue;
    }

    const delimiter = stripped;
    const blockLines: string[] = [];
    for (let later = index + 1; later < lines.length; later += 1) {
      const laterStripped = lines[later].trim();
      if (laterStripped === delimiter) {
        return blockLines.some((line) => line.includes(":"));
      }
      blockLines.push(lines[later]);
    }
  }

  return false;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
