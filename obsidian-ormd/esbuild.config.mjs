import esbuild from "esbuild";
import builtins from "builtin-modules";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const production = process.argv[2] === "production";
const pluginDir = dirname(fileURLToPath(import.meta.url));

const context = await esbuild.context({
  banner: {
    js: "/* ORMD Obsidian plugin */",
  },
  absWorkingDir: pluginDir,
  entryPoints: ["./src/main.ts"],
  bundle: true,
  external: [
    "obsidian",
    "electron",
    "@codemirror/autocomplete",
    "@codemirror/collab",
    "@codemirror/commands",
    "@codemirror/language",
    "@codemirror/lint",
    "@codemirror/search",
    "@codemirror/state",
    "@codemirror/view",
    "@lezer/common",
    "@lezer/highlight",
    "@lezer/lr",
    ...builtins,
  ],
  format: "cjs",
  target: "es2022",
  logLevel: "info",
  sourcemap: production ? false : "inline",
  treeShaking: true,
  outfile: "main.js",
  minify: production,
});

if (production) {
  await context.rebuild();
  await context.dispose();
} else {
  await context.watch();
  console.log("Watching for changes...");
}
