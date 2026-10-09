import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { parseOrmd, splitInlineLinkInner, hasAdditionalFrontMatterBlock } from "../src/core/parser";
import type { OrmdParseResult } from "../src/core/types";
import YAML from "yaml";

const fixturesDir = resolve(__dirname, "fixtures");

function loadFixture(name: string): string {
  return readFileSync(resolve(fixturesDir, name), "utf-8");
}

/** Minimal YAML parser matching Obsidian's parseYaml signature */
function parseYaml(yaml: string): unknown {
  return YAML.parse(yaml);
}

describe("parseOrmd", () => {
  describe("valid documents", () => {
    it("parses a minimal valid document", () => {
      const content = loadFixture("valid_minimal.ormd");
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).not.toBeNull();
      expect(result.frontMatter?.title).toBe("Valid Minimal Document");
      expect(result.frontMatter?.authors).toHaveLength(1);
      expect(result.frontMatter?.links).toHaveLength(1);
      expect(result.body).toContain("# Valid Minimal Document");
      expect(result.body).toContain("[[g1]]");
      expect(result.diagnostics.filter((d) => d.severity === "error")).toHaveLength(0);
    });

    it("parses a full-featured document", () => {
      const content = loadFixture("valid_full.ormd");
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).not.toBeNull();
      expect(result.frontMatter?.title).toBe("Full Featured Document");
      expect(result.frontMatter?.authors).toHaveLength(2);
      expect(result.frontMatter?.links).toHaveLength(2);
      expect(result.frontMatter?.version).toBe("1.0");
      expect(result.frontMatter?.status).toBe("draft");
      expect(result.frontMatter?.keywords).toEqual(["test", "ormd"]);
      expect(result.diagnostics.filter((d) => d.severity === "error")).toHaveLength(0);
    });

    it("parses a document with empty links", () => {
      const content = loadFixture("valid_no_links.ormd");
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).not.toBeNull();
      expect(result.frontMatter?.links).toEqual([]);
      expect(result.diagnostics.filter((d) => d.severity === "error")).toHaveLength(0);
    });

    it("extracts auto-links from inline syntax", () => {
      const content = loadFixture("valid_full.ormd");
      const result = parseOrmd(content, parseYaml);

      expect(result.autoLinks.length).toBeGreaterThan(0);
      const inlineLink = result.autoLinks.find((l) => l.target === "#introduction");
      expect(inlineLink).toBeDefined();
      expect(inlineLink?.rel).toBe("references");
      expect(inlineLink?.text).toBe("inline link");
    });
  });

  describe("invalid documents", () => {
    it("rejects a document without version tag", () => {
      const content = loadFixture("invalid_no_version.ormd");
      const result = parseOrmd(content, parseYaml);

      const errors = result.diagnostics.filter((d) => d.severity === "error");
      expect(errors.length).toBeGreaterThan(0);
      expect(errors[0].message).toContain("version tag");
    });

    it("returns null frontMatter when version tag is missing", () => {
      const content = loadFixture("invalid_no_version.ormd");
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).toBeNull();
      expect(result.body).toBe("");
    });
  });

  describe("front-matter edge cases", () => {
    it("handles no front-matter as empty object", () => {
      const content = "<!-- ormd:0.1 -->\n# Just a heading\n\nBody text.";
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).toEqual({});
      expect(result.body).toContain("# Just a heading");
    });

    it("handles empty front-matter delimiters", () => {
      const content = "<!-- ormd:0.1 -->\n---\n---\n# Heading";
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).toEqual({});
    });

    it("rejects non-object front-matter", () => {
      const content = "<!-- ormd:0.1 -->\n---\n- list item\n- another\n---\n# Body";
      const result = parseOrmd(content, parseYaml);

      expect(result.frontMatter).toBeNull();
      const errors = result.diagnostics.filter((d) => d.severity === "error");
      expect(errors.some((e) => e.message.includes("YAML object"))).toBe(true);
    });

    it("detects legacy +++meta blocks", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors: [Test]
links: []
---
# Body

+++meta
word_count: 100
+++end-meta
`;
      // The parser checks for +++meta pattern
      const result = parseOrmd(content, parseYaml);
      const errors = result.diagnostics.filter((d) => d.severity === "error");
      expect(errors.some((e) => e.message.includes("+++meta"))).toBe(true);
    });

    it("detects multiple front-matter blocks", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors: [Test]
links: []
---
# Body

---
extra: metadata
---

More text.
`;
      const result = parseOrmd(content, parseYaml);
      const errors = result.diagnostics.filter((d) => d.severity === "error");
      expect(errors.some((e) => e.message.includes("Multiple YAML"))).toBe(true);
    });
  });
});

describe("splitInlineLinkInner", () => {
  it("splits target and relationship", () => {
    expect(splitInlineLinkInner('#section "supports"')).toEqual({
      target: "#section",
      rel: "supports",
    });
  });

  it("handles target-only (no relationship)", () => {
    expect(splitInlineLinkInner("#section")).toEqual({
      target: "#section",
      rel: null,
    });
  });

  it("handles URL targets with relationship", () => {
    expect(splitInlineLinkInner('https://example.com "cites"')).toEqual({
      target: "https://example.com",
      rel: "cites",
    });
  });

  it("handles single-quoted relationships", () => {
    expect(splitInlineLinkInner("#section 'refutes'")).toEqual({
      target: "#section",
      rel: "refutes",
    });
  });

  it("trims whitespace", () => {
    expect(splitInlineLinkInner('  #section  "supports"  ')).toEqual({
      target: "#section",
      rel: "supports",
    });
  });
});

describe("hasAdditionalFrontMatterBlock", () => {
  it("returns false for normal body", () => {
    expect(hasAdditionalFrontMatterBlock("# Heading\n\nBody text.")).toBe(false);
  });

  it("detects additional --- block", () => {
    expect(hasAdditionalFrontMatterBlock("# Heading\n\n---\nextra: value\n---\n\nMore text.")).toBe(true);
  });

  it("ignores --- inside code fences", () => {
    expect(hasAdditionalFrontMatterBlock("# Heading\n\n```\n---\nextra: value\n---\n```\n")).toBe(false);
  });

  it("returns false for thematic breaks", () => {
    // A standalone --- without a closing delimiter is not a front-matter block
    expect(hasAdditionalFrontMatterBlock("# Heading\n\n---\n\nMore text.")).toBe(false);
  });
});
