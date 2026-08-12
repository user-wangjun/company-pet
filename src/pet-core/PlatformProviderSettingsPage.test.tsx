import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { PlatformProviderSettingsPage } from "./PlatformProviderSettingsPage";
import {
  getCompanionProviderProfilePreset,
  getCompanionProviderStatusInfo,
  normalizeCompanionProviderSettings,
} from "./companionProviderConfig";
import { EMPTY_COMPANION_USER_PROFILE } from "./companionUserProfile";

describe("PlatformProviderSettingsPage", () => {
  test("renders Provider settings in the platform settings surface", () => {
    const settings = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("google-gemini"),
      credentialConfigured: true,
    });
    const html = renderToStaticMarkup(
      <PlatformProviderSettingsPage
        userProfile={{ ...EMPTY_COMPANION_USER_PROFILE, nickname: "阿星" }}
        onUserProfileSave={vi.fn()}
        settings={settings}
        providerInfo={getCompanionProviderStatusInfo(settings)}
        onTest={vi.fn()}
        onSave={vi.fn()}
        onClear={vi.fn()}
      />,
    );

    expect(html).toContain('aria-label="设置"');
    expect(html).toContain(">设置</span>");
    expect(html).toContain("设置中心");
    expect(html).toContain("个人信息");
    expect(html).toContain("用户邮箱");
    expect(html).toContain("接入方式：远程");
    expect(html).toContain("Provider 只负责模型接入");
    expect(html).toContain("Provider Profile");
    expect(html).toContain("测试连接");
    expect(html).toContain("保存并使用");
    expect(html).not.toContain("聊天设置");
    expect(html).not.toContain("提醒设置");
    expect(html).not.toContain("unit-secret");
  });
});
