import { useEffect, useRef, useState } from "react";
import {
  MARKETING_FILE_NAME,
  WINDOWS_DOWNLOAD_URL,
  socialLinks,
  type SocialLink,
} from "./marketingContent";
import MarketingUniverse from "./MarketingUniverse";

const WECHAT_QRCODE_ART = "./marketing-assets/wechat-qrcode.jpg";

function MarketingNavItem({
  link,
  isWeChatActive,
  onWeChatToggle,
  onToast,
  onDownload,
}: {
  link: SocialLink;
  isWeChatActive: boolean;
  onWeChatToggle: () => void;
  onToast: (message: string) => void;
  onDownload: () => void;
}) {
  const className = `marketing-nav-item marketing-nav-${link.icon}`;

  if (link.behavior === "link" && link.href) {
    return (
      <a
        className={className}
        href={link.href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={link.label}
        title={link.label}
      >
        <span aria-hidden="true">◉</span>
        <small>{link.label}</small>
      </a>
    );
  }

  if (link.behavior === "wechat") {
    return (
      <button
        className={`${className}${isWeChatActive ? " is-active" : ""}`}
        type="button"
        aria-label={link.label}
        title={link.label}
        onClick={(event) => {
          event.stopPropagation();
          onWeChatToggle();
        }}
      >
        <span aria-hidden="true">✦</span>
        <small>{link.label}</small>
        <span className="marketing-wechat-popover">
          <img src={WECHAT_QRCODE_ART} alt="微信二维码" />
          <span className="marketing-wechat-popover-text">扫码加入微信群</span>
        </span>
      </button>
    );
  }

  if (link.behavior === "download") {
    return (
      <button
        className={`${className} marketing-nav-download`}
        type="button"
        aria-label={link.label}
        title="下载 Windows 安装包"
        onClick={(event) => {
          event.stopPropagation();
          onDownload();
        }}
      >
        <span aria-hidden="true">↓</span>
        <small>下载客户端</small>
      </button>
    );
  }

  return (
    <button
      className={className}
      type="button"
      aria-label={link.label}
      title={link.label}
      data-toast-message={link.toastMessage ?? "亟待展示"}
      onClick={(event) => {
        event.stopPropagation();
        onToast(link.toastMessage ?? "亟待展示");
      }}
    >
      <span aria-hidden="true">{link.icon === "user" ? "○" : "✧"}</span>
      <small>{link.label}</small>
    </button>
  );
}

function MarketingPage() {
  const [isWeChatActive, setIsWeChatActive] = useState(false);
  const [isToastVisible, setIsToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState("亟待展示");
  const [isDownloadDialogOpen, setIsDownloadDialogOpen] = useState(false);
  const toastTimerRef = useRef<number | null>(null);
  const homeHref =
    typeof window !== "undefined" &&
    window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME)
      ? `./${MARKETING_FILE_NAME}`
      : "/marketing";

  useEffect(() => {
    const closeWeChat = () => setIsWeChatActive(false);
    document.addEventListener("click", closeWeChat);

    return () => {
      document.removeEventListener("click", closeWeChat);
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  const showToast = (message: string) => {
    setToastMessage(message);
    setIsToastVisible(true);
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => {
      setIsToastVisible(false);
    }, 2200);
  };

  return (
    <>
      <link rel="preload" as="image" href={WECHAT_QRCODE_ART} />
      <main className="marketing-page marketing-universe-page">
        <section
          className="marketing-stage-shell marketing-universe-shell"
          aria-label="愈心桌宠互动宇宙官网"
        >
          <header className="marketing-universe-header">
            <a className="marketing-universe-brand" href={homeHref}>
              <span aria-hidden="true">✦</span>
              <strong>愈心桌宠</strong>
              <small>YOUR DESKTOP COMPANION</small>
            </a>

            <nav className="marketing-universe-nav" aria-label="社交与下载入口">
              {socialLinks.map((link) => (
                <MarketingNavItem
                  key={link.label}
                  link={link}
                  isWeChatActive={isWeChatActive}
                  onWeChatToggle={() => setIsWeChatActive((active) => !active)}
                  onToast={showToast}
                  onDownload={() => setIsDownloadDialogOpen(true)}
                />
              ))}
            </nav>
          </header>

          <MarketingUniverse />

          <div
            className={`marketing-toast${isToastVisible ? " is-visible" : ""}`}
            role="status"
            aria-live="polite"
          >
            {toastMessage}
          </div>
          <h1 className="marketing-screen-reader-text">愈心桌宠</h1>
          <p className="marketing-screen-reader-text">
            可交互星球、独立桌宠角色、三维景深与镜头探索体验
          </p>
        </section>
      </main>

      {isDownloadDialogOpen && (
        <div
          className="download-dialog-overlay"
          onClick={() => setIsDownloadDialogOpen(false)}
          role="presentation"
        >
          <div
            className="download-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="download-dialog-title"
            aria-describedby="download-dialog-desc"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="download-dialog-icon" aria-hidden="true">🖥️</div>
            <h2 id="download-dialog-title" className="download-dialog-title">
              下载 Windows 安装包
            </h2>
            <p id="download-dialog-desc" className="download-dialog-desc">
              愈心桌宠是一款轻量的桌面陪伴应用，让小橘、ds、ikun、蒜鸟在桌面上待机陪伴，支持点击、双击、拖拽和桌面图标互动，也会在合适的时候提醒你护眼、喝水、吃饭、睡觉。
              <br /><br />
              此安装包仅适用于 <strong>Windows 系统（64位）</strong>。
            </p>
            <div className="download-dialog-actions">
              <button
                className="download-dialog-btn download-dialog-btn-cancel"
                type="button"
                onClick={() => setIsDownloadDialogOpen(false)}
              >
                取消
              </button>
              <button
                className="download-dialog-btn download-dialog-btn-confirm"
                type="button"
                onClick={() => {
                  setIsDownloadDialogOpen(false);
                  window.open(WINDOWS_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
                }}
                autoFocus
              >
                确认，开始下载
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default MarketingPage;
