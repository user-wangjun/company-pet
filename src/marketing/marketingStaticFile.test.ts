// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node types out.
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node types out.
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";
import { WINDOWS_DOWNLOAD_URL } from "./marketingContent";

const staticMarketingHtmlPath = resolve("public/marketing.html");

describe("static marketing universe", () => {
  test("opens without Vite and renders independent interactive objects", () => {
    expect(existsSync(staticMarketingHtmlPath)).toBe(true);
    const html = readFileSync(staticMarketingHtmlPath, "utf8");

    expect(html).toContain("愈心桌宠 · 互动宇宙");
    expect(html).toContain('class="viewport"');
    expect(html).toContain('class="camera"');
    expect(html).toContain('id="star-particles"');
    expect(html).toContain('id="constellation"');
    expect(html).toContain('id="encounter"');
    expect(html).toContain('data-camera-target="overview"');
    expect(html).toContain("const entities = [");
    expect(html).toContain('"xiaoju","character"');
    expect(html).toContain('"yuxin-world","landmark"');
    expect(html).toContain('"orbit-bunny","character"');
    expect(html).toContain('"ufo-bunny","character"');
    expect(html).toContain('"tiny-earth","planet"');
    expect(html).toContain("function focus(e)");
    expect(html).toContain("const interactions={");
    expect(html).toContain("const companionLinks=");
    expect(html).toContain("LIVE ENCOUNTER · 07 SEC");
    expect(html).toContain("--cs");
    expect(html).toContain("--cx");
    expect(html).toContain("--cy");
    expect(html).toContain("移动鼠标感受空间");
    expect(html).toContain("./marketing-assets/universe-backdrop-v2.png");
    expect(html).toContain("./marketing-assets/healing-world-v2.png");
    expect(html).toContain("planet-honey-v2.png");
    expect(html).toContain("planet-moon-v2.png");
    expect(html).toContain("planet-earth-v2.png");
    expect(html).toContain("./marketing-assets/foreground-clouds-v2.png");
    expect(html).toContain("./pets/xiaoju-cat/spritesheet-scruff.png");
    expect(html).toContain("./pets/ds/spritesheet.png");
    expect(html).toContain("./pets/ikun/spritesheet.png");
    expect(html).toContain("./pets/suan-bird/spritesheet.png");
    expect(html).not.toContain('type="module"');
    expect(html).not.toContain("marketing-morning.png");
    expect(html).not.toContain("marketing-morning-blink.png");
  });

  test("keeps community and release actions available", () => {
    const html = readFileSync(staticMarketingHtmlPath, "utf8");

    expect(html).toContain("https://discord.gg/AEQqraAtER");
    expect(html).toContain("下载客户端");
    expect(html).toContain("0.3.0-windows-x64-setup.exe");
    expect(WINDOWS_DOWNLOAD_URL).toContain("0.3.0");
  });
});
