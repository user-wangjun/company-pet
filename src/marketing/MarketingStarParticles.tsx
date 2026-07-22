import { useEffect, useRef } from "react";

type Star = {
  x: number;
  y: number;
  radius: number;
  phase: number;
  speed: number;
  drift: number;
  warm: boolean;
};

function MarketingStarParticles() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let frame = 0;
    let stars: Star[] = [];

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = bounds.width;
      height = bounds.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count = Math.max(42, Math.round((width * height) / 12800));
      stars = Array.from({ length: count }, (_, index) => ({
        x: Math.random() * width,
        y: Math.random() * height * 0.88,
        radius: index % 17 === 0 ? 2.1 + Math.random() * 1.4 : 0.55 + Math.random() * 1.2,
        phase: Math.random() * Math.PI * 2,
        speed: 0.45 + Math.random() * 1.15,
        drift: (Math.random() - 0.5) * 0.045,
        warm: index % 7 === 0,
      }));
    };

    const draw = (time: number) => {
      context.clearRect(0, 0, width, height);
      for (const star of stars) {
        const pulse = reducedMotion ? 0.72 : 0.42 + Math.sin(time * 0.001 * star.speed + star.phase) * 0.34;
        star.y += reducedMotion ? 0 : star.drift;
        if (star.y < -5) star.y = height * 0.88;
        if (star.y > height * 0.9) star.y = 0;

        const color = star.warm ? "255, 226, 139" : "221, 239, 255";
        context.beginPath();
        context.fillStyle = `rgba(${color}, ${Math.max(0.14, pulse)})`;
        context.shadowColor = `rgba(${color}, ${Math.max(0.2, pulse)})`;
        context.shadowBlur = star.radius > 2 ? 12 : 5;
        context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        context.fill();

        if (star.radius > 2) {
          context.strokeStyle = `rgba(${color}, ${pulse * 0.72})`;
          context.lineWidth = 0.75;
          context.beginPath();
          context.moveTo(star.x - star.radius * 3.4, star.y);
          context.lineTo(star.x + star.radius * 3.4, star.y);
          context.moveTo(star.x, star.y - star.radius * 3.4);
          context.lineTo(star.x, star.y + star.radius * 3.4);
          context.stroke();
        }
      }

      if (!reducedMotion) frame = window.requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    draw(0);
    if (reducedMotion) return () => window.removeEventListener("resize", resize);

    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return <canvas ref={canvasRef} className="marketing-star-particles" aria-hidden="true" />;
}

export default MarketingStarParticles;
