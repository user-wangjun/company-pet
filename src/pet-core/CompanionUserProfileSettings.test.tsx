import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionUserProfileSettings } from "./CompanionUserProfileSettings";
import { EMPTY_COMPANION_USER_PROFILE } from "./companionUserProfile";

describe("CompanionUserProfileSettings", () => {
  test("renders the general personal information section without remote disclosure", () => {
    const html = renderToStaticMarkup(
      <CompanionUserProfileSettings
        profile={{
          ...EMPTY_COMPANION_USER_PROFILE,
          nickname: "阿星",
        }}
        onSave={vi.fn()}
      />,
    );

    expect(html).toContain('aria-label="个人信息"');
    expect(html).toContain("用户昵称");
    expect(html).toContain("用户性别");
    expect(html).toContain("用户邮箱");
    expect(html).toContain("用户电话");
    expect(html).toContain("保存个人信息");
    expect(html).toContain("不会进入聊天上下文或发送给 Provider");
    expect(html).not.toContain("sk-profile-test-value");
  });
});
