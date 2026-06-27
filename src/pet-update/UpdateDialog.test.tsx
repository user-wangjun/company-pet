import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { UpdateDialog } from "./UpdateDialog";

describe("UpdateDialog", () => {
  test("renders a compact confirmation before downloading the matching installer", () => {
    const html = renderToStaticMarkup(
      <UpdateDialog
        currentVersion="0.2.2"
        latestVersion="0.2.3"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-labelledby="update-dialog-title"');
    expect(html).toContain('aria-describedby="update-dialog-description"');
    expect(html).toContain("当前版本 0.2.2");
    expect(html).toContain("最新版本 0.2.3");
    expect(html).toContain("适合当前电脑的安装包");
    expect(html).toContain("宠物和设置会保留");
    expect(html).not.toContain("覆盖");
    expect(html).toContain("稍后再说");
    expect(html).toContain("下载并安装");
  });

  test("does not render release notes in the pet update dialog", () => {
    const html = renderToStaticMarkup(
      <UpdateDialog
        currentVersion="0.2.2"
        latestVersion="0.2.3"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(html).not.toContain("##");
    expect(html).not.toContain("兼容性");
    expect(html).not.toContain("class=\"update-dialog-notes\"");
  });
});
