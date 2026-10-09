import type { App } from "obsidian";

/**
 * Singleton reference to the Obsidian App instance.
 * Set during plugin load so all modules can navigate without
 * needing the app passed through every function signature.
 */
let appInstance: App | null = null;

/**
 * Store the App reference. Called once from OrmdPlugin.onload().
 */
export function setApp(app: App): void {
  appInstance = app;
}

/**
 * Clear the App reference. Called from OrmdPlugin.onunload().
 */
export function clearApp(): void {
  appInstance = null;
}

/**
 * Classify an ORMD link target into one of three categories:
 *
 * - "anchor"   — starts with #, stays in the current document
 * - "external" — starts with http:// or https://, opens in browser
 * - "file"     — everything else, treated as a vault-relative file path
 *                (may include a #fragment for in-file anchors)
 */
export type LinkTargetKind = "anchor" | "external" | "file";

export interface ParsedLinkTarget {
  kind: LinkTargetKind;
  /** For "file" links: the file path portion (e.g. "collaboration-workflows.ormd") */
  filePath: string | null;
  /** For "anchor" and "file" links: the #fragment, if any */
  fragment: string | null;
  /** The original raw target string */
  raw: string;
}

/**
 * Parse a link target string into its structural parts.
 */
export function parseLinkTarget(target: string): ParsedLinkTarget {
  if (!target) {
    return { kind: "anchor", filePath: null, fragment: null, raw: target };
  }

  if (target.startsWith("http://") || target.startsWith("https://")) {
    return { kind: "external", filePath: null, fragment: null, raw: target };
  }

  if (target.startsWith("#")) {
    return { kind: "anchor", filePath: null, fragment: target.slice(1), raw: target };
  }

  // File link, possibly with a fragment
  const hashIdx = target.indexOf("#");
  if (hashIdx === -1) {
    return { kind: "file", filePath: target, fragment: null, raw: target };
  }

  return {
    kind: "file",
    filePath: target.slice(0, hashIdx),
    fragment: target.slice(hashIdx + 1),
    raw: target,
  };
}

/**
 * Navigate to an ORMD link target using Obsidian's workspace API.
 *
 * - Anchors (#id): scrolls to the element in the current view
 * - External URLs: opens in the default browser
 * - File references: uses openLinkText() to navigate like a wiki-link,
 *   resolving relative to the source file's path
 *
 * @param target     The raw link target string from the `to` field
 * @param sourcePath The vault path of the file containing the link
 *                   (used to resolve relative file references)
 */
export function navigateToTarget(target: string, sourcePath: string): void {
  if (!target) return;
  const app = appInstance;
  if (!app) return;

  const parsed = parseLinkTarget(target);

  switch (parsed.kind) {
    case "anchor": {
      // Scroll to the anchor in the current document
      if (parsed.fragment) {
        const el = document.getElementById(parsed.fragment);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
      break;
    }

    case "external": {
      // Open external URL in browser
      window.open(target, "_blank", "noopener,noreferrer");
      break;
    }

    case "file": {
      // Use Obsidian's link resolver to open the file
      // openLinkText handles: relative paths, .md/.ormd extension resolution,
      // and optional #subpath fragments
      const linkText = parsed.fragment
        ? `${parsed.filePath}#${parsed.fragment}`
        : parsed.filePath ?? "";

      void app.workspace.openLinkText(linkText, sourcePath, false);
      break;
    }
  }
}
