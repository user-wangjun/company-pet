// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

const staticMarketingHtmlPath = resolve("public/marketing.html");
const staticHeroImagePath = resolve(
  "public/marketing-assets/marketing-morning.png",
);
const appStylesPath = resolve("src/App.css");

describe("static marketing file", () => {
  test("can be opened from file:// without a Vite module script", () => {
    expect(existsSync(staticMarketingHtmlPath)).toBe(true);
    expect(existsSync(staticHeroImagePath)).toBe(true);

    const html = readFileSync(staticMarketingHtmlPath, "utf8");

    expect(html).toContain("彩色星空主视觉");
    expect(html).toContain("marketing-stage-shell");
    expect(html).toContain("marketing-morning-art");
    expect(html).toContain("marketing-morning-hit");
    expect(html).toContain("marketing-cloud-surge");
    expect(html).toContain("marketing-cloud-surge-layer-a");
    expect(html).toContain("data-cloud-surge");
    expect(html).toContain("marketing-morning-wechat");
    expect(html).not.toContain('type="module"');
    expect(html).not.toContain("/src/main.tsx");
    expect(html).not.toContain("./assets/main-");
    expect(html).toContain("./marketing-assets/marketing-morning.png");
    expect(html).not.toContain("./marketing-assets/marketing-cloud-flow.png");
    expect(html).not.toContain("./marketing-assets/yuxin-floating-motion.png");
    expect(html).not.toContain("./marketing-assets/yuxin-clouds-clean.png");
    expect(html).toContain("object-fit: cover;");
    expect(html).toContain("radial-gradient");
    expect(html).toContain("setCloudSurgeFrame");
    expect(html).toContain("window.setInterval");
    expect(html).not.toContain("marketing-cloud-surge-roll");
    expect(html).toContain(
      'href="https://discord.gg/AEQqraAtER" target="_blank"',
    );
    expect(html).toContain("./marketing-assets/wechat-qrcode.jpg");
    expect(html).toContain("微信二维码");
    expect(html).toContain("亟待展示");
    expect(html).not.toContain("亟待开发中");
  });

  test("keeps React marketing WeChat popover styles wired to the morning hit target", () => {
    const css = readFileSync(appStylesPath, "utf8");

    expect(css).toContain(
      ".marketing-morning-wechat.is-active .marketing-wechat-popover",
    );
  });
});
