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
  });
});

describe("MarketingPage", () => {
  test("renders the morning homepage as one complete visual", () => {
    const html = renderToStaticMarkup(<MarketingPage />);

    expect(html).toContain("愈心桌宠");
    expect(html).toContain("彩色星空主视觉");
    expect(html).toContain("宇宙星球主视觉");
    expect(html).toContain("marketing-stage-shell");
    expect(html).toContain("marketing-morning-art");
    expect(html).toContain("marketing-morning-hit");
    expect(html).toContain("marketing-cloud-surge");
    expect(html).toContain("marketing-cloud-surge-layer");
    expect(html).toContain("data-cloud-surge");
    expect(html).toContain("marketing-morning.png");
    expect(html).not.toContain("marketing-motion-floaters");
    expect(html).not.toContain("marketing-motion-clouds");
    expect(html).not.toContain("marketing-cloud-flow");
    expect(html).not.toContain("marketing-cloud-flow.png");
    expect(html).not.toContain("yuxin-floating-motion.png");
    expect(html).not.toContain("yuxin-clouds-clean.png");
    expect(html).not.toContain("marketing-cloud-surge-roll");
    expect(html).not.toContain("下载");
  });

  test("keeps the morning topbar hit targets available", () => {
    const html = renderToStaticMarkup(<MarketingPage />);

    for (const link of socialLinks) {
      expect(html).toContain(link.label);
    }

    expect(html).toContain("marketing-morning-discord");
    expect(html).toContain("marketing-morning-x");
    expect(html).toContain("marketing-morning-wechat");
    expect(html).toContain("marketing-morning-qq");
    expect(html).toContain("marketing-morning-user");
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
