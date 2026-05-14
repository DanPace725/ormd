import { MarkdownView, Notice, Plugin, TFile, parseYaml } from "obsidian";
import { validateOrmd } from "./core/validator";
import type { OrmdValidationResult } from "./core/types";

export default class OrmdPlugin extends Plugin {
  private statusBarItem: HTMLElement | null = null;

  async onload(): Promise<void> {
    this.registerExtensions(["ormd"], "markdown");

    this.statusBarItem = this.addStatusBarItem();
    this.statusBarItem.addClass("ormd-status");
    this.statusBarItem.setText("ORMD");

    this.addCommand({
      id: "validate-current-ormd-file",
      name: "Validate current ORMD file",
      callback: () => {
        void this.validateActiveFile(true);
      },
    });

    this.registerEvent(
      this.app.workspace.on("file-open", () => {
        void this.validateActiveFile(false);
      }),
    );

    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => {
        void this.validateActiveFile(false);
      }),
    );

    await this.validateActiveFile(false);
  }

  onunload(): void {
    this.statusBarItem = null;
  }

  private async validateActiveFile(showNotice: boolean): Promise<void> {
    const file = this.getActiveFile();

    if (!file || file.extension !== "ormd") {
      this.updateStatus(null);
      return;
    }

    const content = await this.app.vault.read(file);
    const result = validateOrmd(content, parseYaml);
    this.updateStatus(result);

    if (showNotice) {
      new Notice(formatNotice(file, result));
    }
  }

  private getActiveFile(): TFile | null {
    const activeView = this.app.workspace.getActiveViewOfType(MarkdownView);
    return activeView?.file ?? this.app.workspace.getActiveFile();
  }

  private updateStatus(result: OrmdValidationResult | null): void {
    if (!this.statusBarItem) {
      return;
    }

    this.statusBarItem.removeClass("is-valid");
    this.statusBarItem.removeClass("has-errors");
    this.statusBarItem.removeClass("has-warnings");

    if (!result) {
      this.statusBarItem.setText("");
      return;
    }

    if (result.errors.length > 0) {
      this.statusBarItem.addClass("has-errors");
      this.statusBarItem.setText(`ORMD: ${result.errors.length} error${plural(result.errors.length)}`);
      return;
    }

    if (result.warnings.length > 0) {
      this.statusBarItem.addClass("has-warnings");
      this.statusBarItem.setText(`ORMD: ${result.warnings.length} warning${plural(result.warnings.length)}`);
      return;
    }

    this.statusBarItem.addClass("is-valid");
    this.statusBarItem.setText("ORMD: valid");
  }
}

function formatNotice(file: TFile, result: OrmdValidationResult): string {
  if (result.valid && result.warnings.length === 0) {
    return `${file.name} is valid ORMD.`;
  }

  if (result.valid) {
    return `${file.name} is valid ORMD with ${result.warnings.length} warning${plural(result.warnings.length)}.`;
  }

  const firstError = result.errors[0]?.message ?? "Unknown validation error.";
  return `${file.name} has ${result.errors.length} error${plural(result.errors.length)}: ${firstError}`;
}

function plural(count: number): string {
  return count === 1 ? "" : "s";
}
