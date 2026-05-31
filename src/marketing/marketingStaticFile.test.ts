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
const staticBlinkImagePath = resolve(
  "public/marketing-assets/marketing-morning-blink.png",
);
const staticTailClearImagePath = resolve(
  "public/marketing-assets/marketing-xiaoju-tail-clear.png",
);
const staticTailImagePath = resolve(
  "public/marketing-assets/marketing-xiaoju-tail.png",
);
const appStylesPath = resolve("src/App.css");

describe("static marketing file", () => {
  test("can be opened from file:// without a Vite module script", () => {
    expect(existsSync(staticMarketingHtmlPath)).toBe(true);
    expect(existsSync(staticHeroImagePath)).toBe(true);
    expect(existsSync(staticBlinkImagePath)).toBe(true);
    expect(existsSync(staticTailClearImagePath)).toBe(true);
    expect(existsSync(staticTailImagePath)).toBe(true);

    const html = readFileSync(staticMarketingHtmlPath, "utf8");

    expect(html).toContain("彩色星空主视觉");
    expect(html).toContain("marketing-stage-shell");
    expect(html).toContain("marketing-morning-art");
    expect(html).toContain("marketing-morning-blink-art");
    expect(html).toContain("marketing-xiaoju-tail-clear-art");
    expect(html).toContain("marketing-xiaoju-tail-art");
    expect(html).toContain("marketing-morning-hit");
    expect(html).toContain("marketing-cloud-surge");
    expect(html).toContain("marketing-cloud-surge-layer-a");
    expect(html).toContain("data-cloud-surge");
    expect(html).toContain("marketing-morning-wechat");
    expect(html).toContain("marketing-morning-download");
    expect(html).toContain("下载");
    expect(html).toContain('data-toast-message="亟待展示"');
    expect(html).not.toContain('type="module"');
    expect(html).not.toContain("/src/main.tsx");
    expect(html).not.toContain("./assets/main-");
    expect(html).toContain("./marketing-assets/marketing-morning.png");
    expect(html).toContain("./marketing-assets/marketing-morning-blink.png");
    expect(html).toContain("./marketing-assets/marketing-xiaoju-tail-clear.png");
    expect(html).toContain("./marketing-assets/marketing-xiaoju-tail.png");
    expect(html).not.toContain("./marketing-assets/marketing-cloud-flow.png");
    expect(html).not.toContain("./marketing-assets/yuxin-floating-motion.png");
    expect(html).not.toContain("./marketing-assets/yuxin-clouds-clean.png");
    expect(html).toContain("object-fit: cover;");
    expect(html).toContain("marketing-xiaoju-blink");
    expect(html).toContain("marketing-xiaoju-tail-sway");
    expect(html).toContain("15s linear");
    expect(html).toContain("radial-gradient");
    expect(html).toContain("setCloudSurgeFrame");
    expect(html).toContain("window.requestAnimationFrame");
    expect(html).not.toContain("window.setInterval");
    expect(html).not.toContain("--cloud-a-bg");
    expect(html).not.toContain("--cloud-b-bg");
    expect(html).not.toContain("--cloud-c-bg");
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
    expect(css).toContain("animation: marketing-xiaoju-blink 15s linear");
    expect(css).toContain("animation: marketing-xiaoju-tail-sway 4.6s");
    expect(css).toContain(".marketing-xiaoju-tail-clear-art");
    expect(css).toContain(".marketing-xiaoju-tail-art");
    expect(css).toContain("transform-origin: 31.8% 32.2%");
    expect(css).toContain("transform: rotate(1.8deg)");
    expect(css).not.toContain("transform: rotate(3.2deg)");
    expect(css).not.toContain("transform: rotate(6.4deg)");
    expect(css).toContain("will-change: transform, opacity");
    expect(css).not.toContain("--cloud-a-bg");
    expect(css).not.toContain("--cloud-b-bg");
    expect(css).not.toContain("--cloud-c-bg");
  });
});
