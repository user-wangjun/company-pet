import { useEffect, useRef, useState } from "react";
import {
  MARKETING_FILE_NAME,
  WINDOWS_DOWNLOAD_URL,
  socialLinks,
  type SocialLink,
} from "./marketingContent";
import { startCloudSurgeMotion } from "./cloudSurgeMotion";

const MARKETING_MORNING_ART = "./marketing-assets/marketing-morning.png";
const MARKETING_MORNING_BLINK_ART =
  "./marketing-assets/marketing-morning-blink.png";
const MARKETING_XIAOJU_TAIL_CLEAR_ART =
  "./marketing-assets/marketing-xiaoju-tail-clear.png";
const MARKETING_XIAOJU_TAIL_ART =
  "./marketing-assets/marketing-xiaoju-tail.png";
const WECHAT_QRCODE_ART = "./marketing-assets/wechat-qrcode.jpg";

function MarketingMorningHit({
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
  const className = `marketing-morning-hit marketing-morning-${link.icon}`;

  if (link.behavior === "link" && link.href) {
    return (
      <a
        className={className}
        href={link.href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={link.label}
        title={link.label}
      />
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
        className={className}
        type="button"
        aria-label={link.label}
        title="下载 Windows 安装包"
        onClick={(event) => {
          event.stopPropagation();
          onDownload();
        }}
      >
        <span className="marketing-morning-download-label">下载</span>
      </button>
    );
  }

  const toastMessage = link.toastMessage ?? "亟待展示";

  return (
    <button
      className={className}
      type="button"
      aria-label={link.label}
      title={link.label}
      data-toast-message={toastMessage}
      onClick={(event) => {
        event.stopPropagation();
        onToast(toastMessage);
      }}
    />
  );
}

function MarketingPage() {
  const [isWeChatActive, setIsWeChatActive] = useState(false);
  const [isToastVisible, setIsToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState("亟待展示");
  const [isDownloadDialogOpen, setIsDownloadDialogOpen] = useState(false);
  const toastTimerRef = useRef<number | null>(null);
  const cloudSurgeRef = useRef<HTMLDivElement | null>(null);
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

  useEffect(() => {
    const cloudSurge = cloudSurgeRef.current;
    const prefersReducedMotion = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (!cloudSurge || prefersReducedMotion) {
      return undefined;
    }

    return startCloudSurgeMotion(cloudSurge);
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

  const handleDownloadClick = () => {
    setIsDownloadDialogOpen(true);
  };

  const handleDownloadConfirm = () => {
    setIsDownloadDialogOpen(false);
    window.open(WINDOWS_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
  };

  const handleDownloadCancel = () => {
    setIsDownloadDialogOpen(false);
  };

  return (
    <>
      <link rel="preload" as="image" href={MARKETING_MORNING_ART} />
      <link rel="preload" as="image" href={MARKETING_MORNING_BLINK_ART} />
      <link rel="preload" as="image" href={MARKETING_XIAOJU_TAIL_CLEAR_ART} />
      <link rel="preload" as="image" href={MARKETING_XIAOJU_TAIL_ART} />
      <link rel="preload" as="image" href={WECHAT_QRCODE_ART} />
      <main className="marketing-page">
        <section
          className="marketing-stage-shell marketing-morning-shell"
          aria-label="愈心桌宠宣传首页"
        >
          <img
            className="marketing-morning-art"
            src={MARKETING_MORNING_ART}
            width="1672"
            height="941"
            alt=""
            aria-hidden="true"
            draggable={false}
          />
          <img
            className="marketing-morning-art marketing-morning-blink-art"
            src={MARKETING_MORNING_BLINK_ART}
            width="1672"
            height="941"
            alt=""
            aria-hidden="true"
            draggable={false}
          />
          <img
            className="marketing-morning-art marketing-xiaoju-tail-clear-art"
            src={MARKETING_XIAOJU_TAIL_CLEAR_ART}
            width="1672"
            height="941"
            alt=""
            aria-hidden="true"
            draggable={false}
          />
          <img
            className="marketing-morning-art marketing-xiaoju-tail-art"
            src={MARKETING_XIAOJU_TAIL_ART}
            width="1672"
            height="941"
            alt=""
            aria-hidden="true"
            draggable={false}
          />

          <div
            ref={cloudSurgeRef}
            className="marketing-cloud-surge"
            data-cloud-surge="active"
            aria-hidden="true"
          >
            <span className="marketing-cloud-surge-layer marketing-cloud-surge-layer-a" />
            <span className="marketing-cloud-surge-layer marketing-cloud-surge-layer-b" />
            <span className="marketing-cloud-surge-layer marketing-cloud-surge-layer-c" />
          </div>

          <a
            className="marketing-morning-hit marketing-morning-brand-hit"
            href={homeHref}
            aria-label="愈心桌宠首页"
          />

          <nav className="marketing-morning-socials" aria-label="社交入口">
            {socialLinks.map((link) => (
              <MarketingMorningHit
                key={link.label}
                link={link}
                isWeChatActive={isWeChatActive}
                onWeChatToggle={() => setIsWeChatActive((active) => !active)}
                onToast={showToast}
                onDownload={handleDownloadClick}
              />
            ))}
          </nav>

          <div
            className={`marketing-toast${isToastVisible ? " is-visible" : ""}`}
            role="status"
            aria-live="polite"
          >
            {toastMessage}
          </div>
          <h1 className="marketing-screen-reader-text">愈心桌宠</h1>
          <p className="marketing-screen-reader-text">彩色星空主视觉</p>
          <p className="marketing-screen-reader-text">宇宙星球主视觉</p>
        </section>
      </main>

      {isDownloadDialogOpen && (
        <div
          className="download-dialog-overlay"
          onClick={handleDownloadCancel}
          role="presentation"
        >
          <div
            className="download-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="download-dialog-title"
            aria-describedby="download-dialog-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="download-dialog-icon" aria-hidden="true">
              🖥️
            </div>
            <h2 id="download-dialog-title" className="download-dialog-title">
              下载 Windows 安装包
            </h2>
            <p id="download-dialog-desc" className="download-dialog-desc">
              此安装包仅适用于 <strong>Windows 系统（64位）</strong>。
              <br />
              请确认你的电脑是 Windows 操作系统后再下载。
            </p>
            <div className="download-dialog-actions">
              <button
                className="download-dialog-btn download-dialog-btn-cancel"
                type="button"
                onClick={handleDownloadCancel}
              >
                取消
              </button>
              <button
                className="download-dialog-btn download-dialog-btn-confirm"
                type="button"
                onClick={handleDownloadConfirm}
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
