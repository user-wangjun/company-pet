import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { UpdateDialog } from "./UpdateDialog";

describe("UpdateDialog", () => {
  test("renders an accessible confirmation with versions and notes", () => {
    const html = renderToStaticMarkup(
      <UpdateDialog
        currentVersion="0.2.2"
        latestVersion="0.2.3"
        notes="Improved pet interactions."
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
    expect(html).toContain("Improved pet interactions.");
    expect(html).toContain("稍后再说");
    expect(html).toContain("下载更新");
  });

  test("keeps notes whitespace readable", () => {
    const html = renderToStaticMarkup(
      <UpdateDialog
        currentVersion="0.2.2"
        latestVersion="0.2.3"
        notes={"第一行\n第二行"}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(html).toContain("第一行");
    expect(html).toContain("第二行");
    expect(html).toContain("class=\"update-dialog-notes\"");
  });
});
