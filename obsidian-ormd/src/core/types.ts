export type Severity = "error" | "warning";

export interface OrmdDiagnostic {
  severity: Severity;
  message: string;
  /** 1-based line number, if determinable */
  line?: number;
}

export interface OrmdLink {
  id: string;
  to?: string;
  target?: string;
  rel?: string | null;
  text?: string;
  title?: string;
  source?: "manual" | "inline" | string;
}

export interface OrmdFrontMatter {
  title?: unknown;
  authors?: unknown;
  links?: unknown;
  dates?: unknown;
  metrics?: unknown;
  permissions?: unknown;
  version?: unknown;
  status?: unknown;
  description?: unknown;
  language?: unknown;
  license?: unknown;
  keywords?: unknown;
  link_ids?: unknown;
  asset_ids?: unknown;
  [key: string]: unknown;
}

export interface OrmdParseResult {
  frontMatter: OrmdFrontMatter | null;
  body: string;
  autoLinks: OrmdLink[];
  diagnostics: OrmdDiagnostic[];
  /** 1-based line number where the body starts in the original document */
  bodyStartLine?: number;
}

export interface OrmdValidationResult extends OrmdParseResult {
  valid: boolean;
  errors: OrmdDiagnostic[];
  warnings: OrmdDiagnostic[];
}

export type YamlParser = (yaml: string) => unknown;
