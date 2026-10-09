import type { OrmdDiagnostic, OrmdFrontMatter, OrmdLink, OrmdParseResult, YamlParser } from "./types";

const VERSION_TAG = /^<!-- ormd:(0\.1|1\.0) -->/;

export function parseOrmd(content: string, parseYaml: YamlParser): OrmdParseResult {
  const diagnostics: OrmdDiagnostic[] = [];
  const autoLinks: OrmdLink[] = [];

  const versionMatch = VERSION_TAG.exec(content.trimStart());
  if (!versionMatch) {
    diagnostics.push({
      severity: "error",
      message: "Missing or invalid version tag. Expected '<!-- ormd:0.1 -->' or '<!-- ormd:1.0 -->' at the top of the document.",
      line: 1,
    });
    return { frontMatter: null, body: "", autoLinks, diagnostics };
  }

  // Count lines consumed by the version tag (leading whitespace + tag line)
  const leadingLines = content.slice(0, content.indexOf(versionMatch[0])).split("\n").length - 1;
  const versionTagLine = leadingLines + 1;

  const withoutVersion = content.trimStart().slice(versionMatch[0].length).replace(/^\s*\r?\n?/, "");
  const { frontMatter, body, bodyStartLine } = parseFrontMatterAndBody(
    withoutVersion, parseYaml, diagnostics, versionTagLine,
  );

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
    // Find the line of the extra block
    const bodyLines = body.split("\n");
    let extraBlockLine: number | undefined;
    let inFence = false;
    for (let i = 0; i < bodyLines.length; i++) {
      const stripped = bodyLines[i].trim();
      if (/^(```+|~~~+)/.test(stripped)) {
        inFence = !inFence;
        continue;
      }
      if (!inFence && (stripped === "---" || stripped === "+++")) {
        extraBlockLine = bodyStartLine + i;
        break;
      }
    }
    diagnostics.push({
      severity: "error",
      message: "Multiple YAML front-matter blocks found. Only one is allowed at the beginning of the document.",
      line: extraBlockLine,
    });
  }

  if (/^[ ]*\+\+\+meta\b/m.test(body)) {
    // Find the line
    const bodyLines = body.split("\n");
    let metaLine: number | undefined;
    for (let i = 0; i < bodyLines.length; i++) {
      if (/^\s*\+\+\+meta\b/.test(bodyLines[i])) {
        metaLine = bodyStartLine + i;
        break;
      }
    }
    diagnostics.push({
      severity: "error",
      message: "`+++meta` blocks are no longer supported. All metadata must be in the YAML front-matter.",
      line: metaLine,
    });
  }

  return { frontMatter, body, autoLinks, diagnostics, bodyStartLine };
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
  versionTagLine: number,
): { frontMatter: OrmdFrontMatter | null; body: string; bodyStartLine: number } {
  const normalized = content.replace(/\r\n/g, "\n").trim();
  const delimiter = normalized.startsWith("---\n") ? "---" : normalized.startsWith("+++\n") ? "+++" : null;

  // bodyStartLine is the 1-based line number where the body begins in the original document
  if (!delimiter) {
    return { frontMatter: {}, body: normalized, bodyStartLine: versionTagLine + 1 };
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
    diagnostics.push({
      severity: "error",
      message: "Invalid YAML in front-matter.",
      line: versionTagLine + 1,
    });
    return { frontMatter: null, body: normalized, bodyStartLine: versionTagLine + 1 };
  }

  const yamlContent = lines.slice(1, closingLine).join("\n");
  const body = lines.slice(closingLine + 1).join("\n").trim();
  // +2: version tag line + opening delimiter line; +closingLine for the YAML lines; +1 for closing delimiter
  const bodyStartLine = versionTagLine + 1 + closingLine + 1;

  if (!yamlContent.trim()) {
    return { frontMatter: {}, body, bodyStartLine };
  }

  try {
    const parsed = parseYaml(yamlContent);
    if (parsed === null || parsed === undefined) {
      return { frontMatter: {}, body, bodyStartLine };
    }
    if (!isRecord(parsed)) {
      diagnostics.push({
        severity: "error",
        message: "Front-matter must be a YAML object.",
        line: versionTagLine + 2,
      });
      return { frontMatter: null, body, bodyStartLine };
    }
    return { frontMatter: parsed as OrmdFrontMatter, body, bodyStartLine };
  } catch (error) {
    diagnostics.push({
      severity: "error",
      message: `Invalid YAML in front-matter: ${error instanceof Error ? error.message : String(error)}`,
      line: versionTagLine + 2,
    });
    return { frontMatter: null, body, bodyStartLine };
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
