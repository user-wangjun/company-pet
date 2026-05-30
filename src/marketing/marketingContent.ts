export const MARKETING_ROUTE_PATH = "/marketing";
export const MARKETING_FILE_NAME = "marketing.html";

export type SocialLink = {
  label: string;
  icon: "discord" | "x" | "wechat" | "qq" | "user";
  href?: string;
  behavior: "link" | "wechat" | "toast";
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
  { label: "X", icon: "x", behavior: "toast" },
  { label: "微信", icon: "wechat", behavior: "wechat" },
  { label: "QQ", icon: "qq", behavior: "toast" },
  { label: "用户头像", icon: "user", behavior: "toast" },
];
