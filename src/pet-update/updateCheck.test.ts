import { describe, expect, test, vi } from "vitest";
import packageMetadata from "../../package.json";
import {
  checkForLatestRelease,
  compareSemanticVersions,
  GITHUB_RELEASE_PAGE,
  getCurrentAppVersion,
} from "./updateCheck";

describe("update checking", () => {
  test("compares normalized semantic versions", () => {
    expect(compareSemanticVersions("v0.2.3", "0.2.2")).toBe(1);
    expect(compareSemanticVersions("0.2.2", "v0.2.2")).toBe(0);
    expect(compareSemanticVersions("0.2.1", "0.2.2")).toBe(-1);
  });

  test("rejects malformed semantic versions", () => {
    expect(() => compareSemanticVersions("latest", "0.2.2")).toThrow(
      "Invalid semantic version",
    );
    expect(() => compareSemanticVersions("0.2", "0.2.2")).toThrow(
      "Invalid semantic version",
    );
  });

  test("returns available only for a newer release", async () => {
    const fetchLatest = vi.fn(async () => ({
      tag_name: "v0.2.3",
      body: "Fixes and animation improvements.",
      html_url:
        "https://github.com/user-wangjun/company-pet/releases/tag/v0.2.3",
    }));

    await expect(
      checkForLatestRelease("0.2.2", fetchLatest),
    ).resolves.toEqual({
      status: "available",
      currentVersion: "0.2.2",
      latestVersion: "0.2.3",
      notes: "Fixes and animation improvements.",
      releaseUrl:
        "https://github.com/user-wangjun/company-pet/releases/tag/v0.2.3",
    });
  });

  test("uses default release notes and page when optional fields are blank", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "v0.2.3",
        body: "  ",
        html_url: " ",
      })),
    ).resolves.toEqual({
      status: "available",
      currentVersion: "0.2.2",
      latestVersion: "0.2.3",
      notes: "新版本已发布。",
      releaseUrl: GITHUB_RELEASE_PAGE,
    });
  });

  test("returns current for equal or older remote releases", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "v0.2.2",
        body: "",
        html_url: "https://example.test/current",
      })),
    ).resolves.toEqual({ status: "current", currentVersion: "0.2.2" });

    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "v0.2.1",
        body: "",
        html_url: "https://example.test/old",
      })),
    ).resolves.toEqual({ status: "current", currentVersion: "0.2.2" });
  });

  test("returns failed for malformed responses", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "latest",
        body: "",
        html_url: "",
      })),
    ).resolves.toMatchObject({ status: "failed" });
  });

  test("returns failed for request errors", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => {
        throw new Error("network");
      }),
    ).resolves.toEqual({
      status: "failed",
      message: "检查更新失败，请稍后再试。",
    });
  });

  test("falls back to package metadata outside Tauri", async () => {
    await expect(getCurrentAppVersion()).resolves.toBe(packageMetadata.version);
  });
});
