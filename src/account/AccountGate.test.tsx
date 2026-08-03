import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import { AccountGate } from "./AccountGate";

describe("AccountGate", () => {
  test("renders the registration preview with reserved email verification", () => {
    const html = renderToStaticMarkup(
      <AccountGate><div>正式应用</div></AccountGate>,
    );

    expect(html).toContain("创建预览账号");
    expect(html).toContain("确认密码");
    expect(html).toContain("邮箱验证码");
    expect(html).toContain("暂未启用");
    expect(html).toContain("小橘一直");
    expect(html).toContain("点一下输入框，看看小橘的反应");
    expect(html).toContain("/pets/xiaoju-cat/live2d/runtime/xiaoju-planet-login/xiaoju-planet-login.model3.json");
    expect(html).toContain("/pets/xiaoju-cat/live2d/planet-scene-source/layers-v3/60_Foreleg_L_Complete.png");
    expect(html).toContain("/pets/xiaoju-cat/live2d/planet-scene-source/layers-v3/61_Foreleg_R_Complete.png");
    expect(html).toContain("/pets/xiaoju-cat/live2d/planet-scene-source/layers-v2/20_Eye_L_Whole.png");
    expect(html).toContain("account-live2d-canvas");
    expect(html).toContain("account-foreleg-rig");
    expect(html).not.toContain("account-pose-sequence");
    expect(html).not.toContain("login-email-focus-v1.png");
    expect(html).not.toContain("login-password-cover-v1.png");
    expect(html).not.toContain(">正式应用<");
  });
});
