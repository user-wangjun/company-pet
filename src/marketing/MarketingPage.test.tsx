import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import MarketingPage from "./MarketingPage";
import {
  MARKETING_FILE_NAME,
  MARKETING_ROUTE_PATH,
  isMarketingRoute,
  socialLinks,
} from "./marketingContent";

describe("marketing homepage route", () => {
  test("only uses the marketing page on the standalone marketing path", () => {
    expect(MARKETING_ROUTE_PATH).toBe("/marketing");
    expect(isMarketingRoute("/marketing")).toBe(true);
    expect(isMarketingRoute("/marketing/")).toBe(true);
    expect(MARKETING_FILE_NAME).toBe("marketing.html");
    expect(isMarketingRoute("/dist/marketing.html")).toBe(true);
    expect(isMarketingRoute("D:/CodeWorkspace/电脑桌宠/dist/marketing.html")).toBe(
      true,
    );
    expect(isMarketingRoute("/")).toBe(false);
    expect(isMarketingRoute("/dist/index.html")).toBe(false);
    expect(isMarketingRoute("/platform")).toBe(false);
    expect(isMarketingRoute("/marketing-3d")).toBe(false);
  });
});

describe("MarketingPage", () => {
  test("renders the independent interactive universe instead of the reference image", () => {
    const html = renderToStaticMarkup(<MarketingPage />);

    expect(html).toContain("愈心桌宠");
    expect(html).toContain("marketing-stage-shell");
    expect(html).toContain("marketing-universe-viewport");
    expect(html).toContain("marketing-universe-camera");
    expect(html).toContain("marketing-star-particles");
    expect(html).toContain("marketing-companion-constellation");
    expect(html).toContain("marketing-generated-world");
    expect(html).toContain("universe-backdrop-v2.png");
    expect(html).toContain("healing-world-v2.png");
    expect(html).toContain("planet-honey-v2.png");
    expect(html).toContain("planet-moon-v2.png");
    expect(html).toContain("planet-earth-v2.png");
    expect(html).toContain("foreground-clouds-v2.png");
    expect(html).toContain("marketing-generated-planet");
    expect(html).toContain("marketing-pet-sprite");
    expect(html).toContain("可交互星球、独立桌宠角色、三维景深与镜头探索体验");
    expect(html).not.toContain("marketing-morning.png");
    expect(html).not.toContain("marketing-morning-blink.png");
    expect(html).toContain("下载");
  });

  test("keeps the morning topbar hit targets available", () => {
    const html = renderToStaticMarkup(<MarketingPage />);

    for (const link of socialLinks) {
      expect(html).toContain(link.label);
    }

    expect(html).toContain("marketing-nav-discord");
    expect(html).toContain("marketing-nav-x");
    expect(html).toContain("marketing-nav-wechat");
    expect(html).toContain("marketing-nav-qq");
    expect(html).toContain("marketing-nav-user");
    expect(html).toContain("marketing-nav-download");
    expect(html).toContain('data-toast-message="亟待展示"');
  });

  test("renders an explorable camera target for every scene entity", async () => {
    const html = renderToStaticMarkup(<MarketingPage />);
    const { MARKETING_SCENE_ENTITIES } = await import("./marketingScene");

    expect(html).toContain("marketing-universe-viewport");
    expect(html).toContain("marketing-universe-camera");
    expect(html).toContain('data-camera-target="overview"');
    expect(html).toContain("marketing-universe-card");
    expect(html).toContain("marketing-universe-controls");
    expect(html).toContain("移动鼠标感受空间，点击任意星球或桌宠靠近");
    expect(html).toContain("桌宠与伴生星球之间的星光航线");

    for (const entity of MARKETING_SCENE_ENTITIES) {
      expect(html).toContain(`data-entity-id="${entity.id}"`);
      expect(html).toContain(`探索${entity.name}`);
    }
  });

  test("wires social clicks to the requested destinations and placeholders", () => {
    const html = renderToStaticMarkup(<MarketingPage />);
    const discordLink = socialLinks.find((link) => link.icon === "discord");

    expect(discordLink?.href).toBe("https://discord.gg/AEQqraAtER");
    expect(html).toContain('href="https://discord.gg/AEQqraAtER"');
    expect(html).toContain("wechat-qrcode.jpg");
    expect(html).toContain("微信二维码");
    expect(html).toContain("亟待展示");
    expect(html).not.toContain("亟待开发中");
  });
});
