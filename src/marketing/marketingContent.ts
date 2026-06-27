export const MARKETING_ROUTE_PATH = "/marketing";
export const MARKETING_FILE_NAME = "marketing.html";

export const WINDOWS_DOWNLOAD_URL =
  "https://github.com/user-wangjun/company-pet/releases/latest/download/yuxin-desktop-pet-0.2.6-windows-x64-setup.exe";

export type SocialLink = {
  label: string;
  icon: "discord" | "download" | "x" | "wechat" | "qq" | "user";
  href?: string;
  behavior: "link" | "wechat" | "toast" | "download";
  toastMessage?: string;
};

export function isMarketingRoute(pathname: string): boolean {
  const normalizedPath = pathname.replace(/\\/g, "/").replace(/\/+$/, "") || "/";

  return (
    normalizedPath === MARKETING_ROUTE_PATH ||
    normalizedPath.endsWith(`/${MARKETING_FILE_NAME}`)
  );
}

export const socialLinks: SocialLink[] = [
  {
    label: "Discord",
    icon: "discord",
    href: "https://discord.gg/AEQqraAtER",
    behavior: "link",
  },
  {
    label: "下载",
    icon: "download",
    behavior: "download",
  },
  { label: "X", icon: "x", behavior: "toast" },
  { label: "微信", icon: "wechat", behavior: "wechat" },
  { label: "QQ", icon: "qq", behavior: "toast" },
  { label: "用户头像", icon: "user", behavior: "toast" },
];
