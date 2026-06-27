import { getVersion } from "@tauri-apps/api/app";
import packageMetadata from "../../package.json";

export const GITHUB_RELEASE_API =
  "https://api.github.com/repos/user-wangjun/company-pet/releases/latest";
export const GITHUB_RELEASE_PAGE =
  "https://github.com/user-wangjun/company-pet/releases/latest";

type ReleaseResponse = {
  tag_name: string;
  body?: string | null;
  html_url?: string | null;
  assets?: ReleaseAsset[] | null;
};

type ReleaseAsset = {
  name?: string | null;
  browser_download_url?: string | null;
};

type InstallerPlatform = "windows" | "macos";

export type UpdateCheckResult =
  | { status: "current"; currentVersion: string }
  | {
      status: "available";
      currentVersion: string;
      latestVersion: string;
      notes: string;
      releaseUrl: string;
      downloadUrl: string;
    }
  | { status: "failed"; message: string };

function normalizeVersion(version: string): [number, number, number] | null {
  const match = version.trim().match(/^v?(\d+)\.(\d+)\.(\d+)$/i);
  return match
    ? [Number(match[1]), Number(match[2]), Number(match[3])]
    : null;
}

export function compareSemanticVersions(left: string, right: string): number {
  const a = normalizeVersion(left);
  const b = normalizeVersion(right);
  if (!a || !b) throw new Error("Invalid semantic version");

  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) return a[index] > b[index] ? 1 : -1;
  }
  return 0;
}

export async function getCurrentAppVersion(): Promise<string> {
  try {
    return await getVersion();
  } catch {
    return packageMetadata.version;
  }
}

export async function fetchLatestRelease(): Promise<ReleaseResponse> {
  const response = await fetch(GITHUB_RELEASE_API, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!response.ok) {
    throw new Error(`GitHub release request: ${response.status}`);
  }
  return response.json() as Promise<ReleaseResponse>;
}

function getCurrentInstallerPlatform(): InstallerPlatform {
  const userAgent =
    typeof navigator === "undefined" ? "" : navigator.userAgent.toLowerCase();
  return userAgent.includes("mac") ? "macos" : "windows";
}

function selectInstallerDownloadUrl(
  release: ReleaseResponse,
  platform: InstallerPlatform,
): string | null {
  const extension = platform === "macos" ? ".dmg" : ".exe";
  const asset = release.assets?.find((item) =>
    item.name?.toLowerCase().endsWith(extension),
  );
  return asset?.browser_download_url?.trim() || null;
}

export async function checkForLatestRelease(
  currentVersion: string,
  fetcher: () => Promise<ReleaseResponse> = fetchLatestRelease,
  platform: InstallerPlatform = getCurrentInstallerPlatform(),
): Promise<UpdateCheckResult> {
  try {
    const release = await fetcher();
    const normalized = normalizeVersion(release.tag_name);
    if (!normalized) {
      return { status: "failed", message: "Invalid release version" };
    }

    const latestVersion = normalized.join(".");
    if (compareSemanticVersions(latestVersion, currentVersion) <= 0) {
      return { status: "current", currentVersion };
    }

    const downloadUrl = selectInstallerDownloadUrl(release, platform);
    if (!downloadUrl) {
      return { status: "failed", message: "未找到适合当前系统的安装包。" };
    }

    return {
      status: "available",
      currentVersion,
      latestVersion,
      notes: release.body?.trim() || "新版本已发布。",
      releaseUrl: release.html_url?.trim() || GITHUB_RELEASE_PAGE,
      downloadUrl,
    };
  } catch {
    return { status: "failed", message: "检查更新失败，请稍后再试。" };
  }
}
