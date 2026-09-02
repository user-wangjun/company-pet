import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import { AccountGate } from "./AccountGate";
import { isFirebaseAuthConfigured } from "./firebaseAuth";

describe("AccountGate", () => {
  test("renders the login gate with the configured account mode", () => {
    const html = renderToStaticMarkup(
      <AccountGate><div>正式应用</div></AccountGate>,
    );

    expect(html).toContain("回到小橘身边");
    expect(html).toContain("登录，回到小橘身边");
    expect(html).not.toContain("确认密码");
    expect(html).toContain("account-warm-pet-scene");
    expect(html).toContain("account-layered-pet");
    expect(html).toContain("/pets/xiaoju-cat/qa/login-gaze-v8/warm-room-backdrop.png");
    expect(html).toContain("/pets/xiaoju-cat/qa/login-gaze-v8/body-open-base.png");
    expect(html).toContain("/pets/xiaoju-cat/qa/login-gaze-v8/pupil-left.png");
    expect(html).toContain("/pets/xiaoju-cat/qa/login-gaze-v8/closed-eye-sockets.png");
    expect(html).not.toContain("idle-24.png");
    expect(html).not.toContain("character-master-v1.png");
    expect(html).not.toContain("xiaoju-scene-email.jpg");
    expect(html).not.toContain("xiaoju-scene-password.jpg");
    if (isFirebaseAuthConfigured()) {
      expect(html).toContain("邮箱验证由 Firebase 发送");
      expect(html).not.toContain("邮箱验证码");
      expect(html).not.toContain("暂未启用");
    } else {
      expect(html).toContain("当前为网页预览账号");
    }
    expect(html).toContain("account-pet-eye-group");
    expect(html).not.toContain("account-infinite-starfield");
    expect(html).not.toContain("account-cosmos-canvas");
    expect(html).toContain("account-stage-footer");
    expect(html).not.toContain("account-live2d-canvas");
    expect(html).not.toContain("account-foreleg-rig");
    expect(html).not.toContain(">正式应用<");
  });
});
