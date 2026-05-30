import { useEffect, useRef, useState } from "react";
import {
  MARKETING_FILE_NAME,
  socialLinks,
  type SocialLink,
} from "./marketingContent";

const MARKETING_MORNING_ART = "./marketing-assets/marketing-morning.png";
const WECHAT_QRCODE_ART = "./marketing-assets/wechat-qrcode.jpg";

function MarketingMorningHit({
  link,
  isWeChatActive,
  onWeChatToggle,
  onToast,
}: {
  link: SocialLink;
  isWeChatActive: boolean;
  onWeChatToggle: () => void;
  onToast: () => void;
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

  return (
    <button
      className={className}
      type="button"
      aria-label={link.label}
      title={link.label}
      onClick={(event) => {
        event.stopPropagation();
        onToast();
      }}
    />
  );
}

function MarketingPage() {
  const [isWeChatActive, setIsWeChatActive] = useState(false);
  const [isToastVisible, setIsToastVisible] = useState(false);
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

    const startedAt = window.performance.now();
    const setLayerProperty = (name: string, value: string) => {
      cloudSurge.style.setProperty(name, value);
    };

    const setCloudSurgeFrame = () => {
      const elapsed = (window.performance.now() - startedAt) / 1000;
      const a = Math.sin(elapsed * 0.62);
      const b = Math.cos(elapsed * 0.48);
      const c = Math.sin(elapsed * 0.38 + 1.4);

      setLayerProperty("--cloud-a-x", `${(-1.4 + a * 2.6).toFixed(3)}%`);
      setLayerProperty("--cloud-a-y", `${(0.5 - b * 1.4).toFixed(3)}%`);
      setLayerProperty("--cloud-a-scale-x", `${(1.05 + b * 0.045).toFixed(3)}`);
      setLayerProperty("--cloud-a-scale-y", `${(1.02 + a * 0.06).toFixed(3)}`);
      setLayerProperty("--cloud-a-opacity", `${(0.58 + c * 0.08).toFixed(3)}`);
      setLayerProperty("--cloud-a-bg", `${(elapsed * 2.1).toFixed(2)}% 0%`);

      setLayerProperty("--cloud-b-x", `${(1.8 - b * 3.1).toFixed(3)}%`);
      setLayerProperty("--cloud-b-y", `${(0.9 + a * 1.1).toFixed(3)}%`);
      setLayerProperty("--cloud-b-scale-x", `${(1.08 + a * 0.055).toFixed(3)}`);
      setLayerProperty("--cloud-b-scale-y", `${(1.0 + c * 0.08).toFixed(3)}`);
      setLayerProperty("--cloud-b-opacity", `${(0.46 + b * 0.07).toFixed(3)}`);
      setLayerProperty("--cloud-b-bg", `${(-elapsed * 1.7).toFixed(2)}% 0%`);

      setLayerProperty("--cloud-c-x", `${(-0.8 + c * 2.2).toFixed(3)}%`);
      setLayerProperty("--cloud-c-y", `${(0.6 - a * 1.3).toFixed(3)}%`);
      setLayerProperty("--cloud-c-scale-x", `${(1.06 + c * 0.05).toFixed(3)}`);
      setLayerProperty("--cloud-c-scale-y", `${(1.05 + b * 0.09).toFixed(3)}`);
      setLayerProperty("--cloud-c-opacity", `${(0.32 + a * 0.06).toFixed(3)}`);
      setLayerProperty("--cloud-c-bg", `${(elapsed * 1.25).toFixed(2)}% 0%`);
    };

    setCloudSurgeFrame();
    const cloudSurgeTimer = window.setInterval(setCloudSurgeFrame, 120);

    return () => {
      window.clearInterval(cloudSurgeTimer);
    };
  }, []);

  const showToast = () => {
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
      <link rel="preload" as="image" href={MARKETING_MORNING_ART} />
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
              />
            ))}
          </nav>

          <div
            className={`marketing-toast${isToastVisible ? " is-visible" : ""}`}
            role="status"
            aria-live="polite"
          >
            亟待展示
          </div>
          <h1 className="marketing-screen-reader-text">愈心桌宠</h1>
          <p className="marketing-screen-reader-text">彩色星空主视觉</p>
          <p className="marketing-screen-reader-text">宇宙星球主视觉</p>
        </section>
      </main>
    </>
  );
}

export default MarketingPage;
