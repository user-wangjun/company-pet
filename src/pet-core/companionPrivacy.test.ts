import { describe, expect, test } from "vitest";
import {
  containsSensitiveCompanionData,
  containsSensitiveCompanionText,
  removeSensitiveCompanionDataLines,
} from "./companionPrivacy";

describe("shared companion privacy boundary", () => {
  test.each([
    "我的密码是 never-save",
    "my password is never-save",
    "Bearer abcdefghijklmnop",
    "API key: never-save",
    "-----BEGIN PRIVATE KEY-----",
    "我的身份证号是 11010519491231002X",
    "my social security number is 123-45-6789",
    "我的护照号码是 E12345678",
    "银行卡号 6222021234567890123",
    "credit card number 4111111111111111",
    "bank account is 123456789012",
    "我住在北京市朝阳区建国路 1 号",
    "I live at 123 Main Street",
    "medical diagnosis is migraine",
    "my medical history includes asthma",
    "my medication is never-save",
    "sk-proj-12345678901234567890",
    "ghp_12345678901234567890",
    "github_pat_12345678901234567890",
    "xoxb-12345678901234567890",
    "AIza123456789012345678901234567890",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature-value",
  ])("rejects sensitive categories and credential shapes: %s", (value) => {
    expect(containsSensitiveCompanionText(value)).toBe(true);
  });

  test.each([
    "我有糖尿病",
    "I have diabetes",
    "I was diagnosed with diabetes",
    "I take metformin every day",
    "我通常吃二甲双胍，请记住。",
    "123 Main Street, Springfield",
    "明天下午三点提醒我去朝阳区建国路1号",
  ])("rejects unlabeled health, medication, and detailed address shapes: %s", (value) => {
    expect(containsSensitiveCompanionText(value)).toBe(true);
    expect(containsSensitiveCompanionData(value)).toBe(true);
  });

  test.each([
    "密码策略应该要求至少 12 个字符，不要保存实际密码。",
    "医疗科普：糖尿病有哪些常见症状？",
    "Let's discuss password policy and medical education in general.",
  ])("allows policy or educational discussion without attached user data: %s", (value) => {
    expect(containsSensitiveCompanionText(value)).toBe(false);
    expect(containsSensitiveCompanionData(value)).toBe(false);
  });

  test("distinguishes attached sensitive data from a policy category mention", () => {
    expect(containsSensitiveCompanionData("不要把 password 发送到云端")).toBe(false);
    expect(containsSensitiveCompanionData("my password is never-save")).toBe(true);
    expect(containsSensitiveCompanionData("sk-proj-12345678901234567890")).toBe(true);
  });

  test("removes only lines carrying sensitive data from trusted policy text", () => {
    const filtered = removeSensitiveCompanionDataLines(
      "不要索取 password。\nmy password is never-save\n保持陪伴式语气。",
    );
    expect(filtered).toContain("不要索取 password");
    expect(filtered).toContain("保持陪伴式语气");
    expect(filtered).not.toContain("never-save");
  });
});
