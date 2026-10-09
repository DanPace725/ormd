import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";
import { validateOrmd } from "../src/core/validator";
import type { OrmdValidationResult } from "../src/core/types";
import YAML from "yaml";

const fixturesDir = resolve(__dirname, "fixtures");

function loadFixture(name: string): string {
  return readFileSync(resolve(fixturesDir, name), "utf-8");
}

function parseYaml(yaml: string): unknown {
  return YAML.parse(yaml);
}

function validate(content: string): OrmdValidationResult {
  return validateOrmd(content, parseYaml);
}

describe("validateOrmd", () => {
  describe("Core Framework ORMD 1.0", () => {
    const coreDocument = `<!-- ormd:1.0 -->
---
title: Core source
authors: ["Daniel Pace"]
frame: scientific.theory
lineage:
  origin: { uri: "internal://core", ts: "2024-12-13T00:00:00Z" }
  parents: []
policy:
  read: [{ roles: ["public"] }]
semantics:
  keywords: ["relations"]
resolution: { confidence: 0.85 }
---
# Core source {#title}

See [another section](#other "ontological:composes").
`;

    it("accepts the current metadata envelope without legacy links", () => {
      const result = validate(coreDocument);
      expect(result.valid).toBe(true);
      expect(result.frontMatter?.frame).toBe("scientific.theory");
      expect(result.body).toContain("# Core source");
    });

    it("reports a missing required Core field", () => {
      const result = validate(coreDocument.replace("resolution: { confidence: 0.85 }\n", ""));
      expect(result.errors.some((error) => error.message.includes("resolution"))).toBe(true);
    });
  });

  describe("valid documents", () => {
    it("validates a minimal document", () => {
      const result = validate(loadFixture("valid_minimal.ormd"));
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("validates a full-featured document", () => {
      const result = validate(loadFixture("valid_full.ormd"));
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("validates a document with empty links", () => {
      const result = validate(loadFixture("valid_no_links.ormd"));
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("warns about unused link definitions", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors:
  - Test
links:
  - id: unused-link
    rel: supports
    to: "#section"
---
# Body

No references here.
`;
      const result = validate(content);
      expect(result.valid).toBe(true); // warnings don't make it invalid
      expect(result.warnings.some((w) => w.message.includes("unused-link"))).toBe(true);
    });
  });

  describe("invalid documents", () => {
    it("rejects missing version tag", () => {
      const result = validate(loadFixture("invalid_no_version.ormd"));
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("version tag"))).toBe(true);
    });

    it("rejects missing title", () => {
      const result = validate(loadFixture("invalid_missing_title.ormd"));
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("title"))).toBe(true);
    });

    it("rejects undefined link references", () => {
      const result = validate(loadFixture("invalid_undefined_refs.ormd"));
      expect(result.valid).toBe(false);

      const refErrors = result.errors.filter((e) => e.message.includes("Undefined link reference"));
      expect(refErrors).toHaveLength(2);
      expect(refErrors.some((e) => e.message.includes("undefined-link"))).toBe(true);
      expect(refErrors.some((e) => e.message.includes("another-missing"))).toBe(true);
    });

    it("rejects unapproved relationship types", () => {
      const result = validate(loadFixture("invalid_bad_rel.ormd"));
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("unapproved relationship"))).toBe(true);
      expect(result.errors.some((e) => e.message.includes("destroys"))).toBe(true);
    });

    it("rejects unknown front-matter fields", () => {
      const result = validate(loadFixture("invalid_unknown_fields.ormd"));
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("custom_field"))).toBe(true);
      expect(result.errors.some((e) => e.message.includes("experimental"))).toBe(true);
    });

    it("rejects missing authors", () => {
      const content = `<!-- ormd:0.1 -->
---
title: No Authors
links: []
---
# Body
`;
      const result = validate(content);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("authors"))).toBe(true);
    });

    it("rejects missing links field", () => {
      const content = `<!-- ormd:0.1 -->
---
title: No Links Field
authors:
  - Test
---
# Body
`;
      const result = validate(content);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("links"))).toBe(true);
    });

    it("rejects link missing id", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors:
  - Test
links:
  - rel: supports
    to: "#section"
---
# Body
`;
      const result = validate(content);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("missing required field 'id'"))).toBe(true);
    });

    it("rejects link missing to", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors:
  - Test
links:
  - id: broken-link
    rel: supports
---
# Body

See [[broken-link]].
`;
      const result = validate(content);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.message.includes("missing required field 'to'"))).toBe(true);
    });
  });

  describe("auto-link merging", () => {
    it("merges inline links with front-matter links", () => {
      const content = `<!-- ormd:0.1 -->
---
title: Test
authors:
  - Test
links:
  - id: manual-link
    rel: supports
    to: "#section"
---
# Body

See [[manual-link]].

Also [click here](#other "cites") for info.
`;
      const result = validate(content);
      // manual-link is defined and referenced — valid
      // inline link auto-merges — no error from it
      expect(result.valid).toBe(true);
    });
  });
});
