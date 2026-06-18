// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { existsSync, readFileSync } from "node:fs";
// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { resolve } from "node:path";
// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { inflateSync } from "node:zlib";
import { describe, expect, test } from "vitest";
import { WINDOWS_DOWNLOAD_URL } from "./marketingContent";

const staticMarketingHtmlPath = resolve("public/marketing.html");
const staticHeroImagePath = resolve(
  "public/marketing-assets/marketing-morning.png",
);
const staticBlinkImagePath = resolve(
  "public/marketing-assets/marketing-morning-blink.png",
);
const staticTailClearImagePath = resolve(
  "public/marketing-assets/marketing-xiaoju-tail-clear.png",
);
const staticTailImagePath = resolve(
  "public/marketing-assets/marketing-xiaoju-tail.png",
);
const appStylesPath = resolve("src/App.css");

type PngImage = {
  width: number;
  height: number;
  data: Uint8Array;
};

function readUint32(bytes: Uint8Array, offset: number): number {
  return (
    ((bytes[offset] << 24) |
      (bytes[offset + 1] << 16) |
      (bytes[offset + 2] << 8) |
      bytes[offset + 3]) >>>
    0
  );
}

function concatChunks(chunks: Uint8Array[]): Uint8Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(totalLength);
  let offset = 0;

  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }

  return output;
}

function paethPredictor(left: number, above: number, upperLeft: number): number {
  const prediction = left + above - upperLeft;
  const leftDistance = Math.abs(prediction - left);
  const aboveDistance = Math.abs(prediction - above);
  const upperLeftDistance = Math.abs(prediction - upperLeft);

  if (leftDistance <= aboveDistance && leftDistance <= upperLeftDistance) {
    return left;
  }

  return aboveDistance <= upperLeftDistance ? above : upperLeft;
}

function readPngRgba(filePath: string): PngImage {
  const bytes = new Uint8Array(readFileSync(filePath));
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idatChunks: Uint8Array[] = [];

  while (offset < bytes.length) {
    const length = readUint32(bytes, offset);
    const type = String.fromCharCode(
      bytes[offset + 4],
      bytes[offset + 5],
      bytes[offset + 6],
      bytes[offset + 7],
    );
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    const chunk = bytes.slice(dataStart, dataEnd);

    if (type === "IHDR") {
      width = readUint32(chunk, 0);
      height = readUint32(chunk, 4);
      bitDepth = chunk[8];
      colorType = chunk[9];
    } else if (type === "IDAT") {
      idatChunks.push(chunk);
    } else if (type === "IEND") {
      break;
    }

    offset = dataEnd + 4;
  }

  expect(bitDepth).toBe(8);
  expect([2, 6]).toContain(colorType);

  const inflated = new Uint8Array(inflateSync(concatChunks(idatChunks)));
  const sourceBytesPerPixel = colorType === 6 ? 4 : 3;
  const sourceStride = width * sourceBytesPerPixel;
  const pixels = new Uint8Array(height * width * 4);
  let inputOffset = 0;
  let previousSourceRow = new Uint8Array(sourceStride);

  for (let y = 0; y < height; y += 1) {
    const filterType = inflated[inputOffset];
    inputOffset += 1;
    const row = inflated.slice(inputOffset, inputOffset + sourceStride);

    inputOffset += sourceStride;

    for (let x = 0; x < sourceStride; x += 1) {
      const left = x >= sourceBytesPerPixel ? row[x - sourceBytesPerPixel] : 0;
      const above = previousSourceRow[x];
      const upperLeft =
        x >= sourceBytesPerPixel ? previousSourceRow[x - sourceBytesPerPixel] : 0;

      if (filterType === 1) {
        row[x] = (row[x] + left) & 0xff;
      } else if (filterType === 2) {
        row[x] = (row[x] + above) & 0xff;
      } else if (filterType === 3) {
        row[x] = (row[x] + Math.floor((left + above) / 2)) & 0xff;
      } else if (filterType === 4) {
        row[x] = (row[x] + paethPredictor(left, above, upperLeft)) & 0xff;
      }
    }

    for (let x = 0; x < width; x += 1) {
      const sourceOffset = x * sourceBytesPerPixel;
      const outputOffset = (y * width + x) * 4;

      pixels[outputOffset] = row[sourceOffset];
      pixels[outputOffset + 1] = row[sourceOffset + 1];
      pixels[outputOffset + 2] = row[sourceOffset + 2];
      pixels[outputOffset + 3] =
        sourceBytesPerPixel === 4 ? row[sourceOffset + 3] : 255;
    }

    previousSourceRow = row;
  }

  return { width, height, data: pixels };
}

function luminanceAt(image: PngImage, x: number, y: number): number {
  expect(x).toBeGreaterThanOrEqual(0);
  expect(x).toBeLessThan(image.width);
  expect(y).toBeGreaterThanOrEqual(0);
  expect(y).toBeLessThan(image.height);

  const offset = (y * image.width + x) * 4;

  return (
    image.data[offset] * 0.2126 +
    image.data[offset + 1] * 0.7152 +
    image.data[offset + 2] * 0.0722
  );
}

describe("static marketing file", () => {
  test("can be opened from file:// without a Vite module script", () => {
    expect(existsSync(staticMarketingHtmlPath)).toBe(true);
    expect(existsSync(staticHeroImagePath)).toBe(true);
    expect(existsSync(staticBlinkImagePath)).toBe(true);
    expect(existsSync(staticTailClearImagePath)).toBe(true);
    expect(existsSync(staticTailImagePath)).toBe(true);

    const html = readFileSync(staticMarketingHtmlPath, "utf8");

    expect(html).toContain("彩色星空主视觉");
    expect(html).toContain("marketing-stage-shell");
    expect(html).toContain("marketing-morning-art");
    expect(html).toContain("marketing-morning-blink-art");
    expect(html).toContain("marketing-xiaoju-tail-clear-art");
    expect(html).toContain("marketing-xiaoju-tail-art");
    expect(html).toContain("marketing-morning-hit");
    expect(html).toContain("marketing-cloud-surge");
    expect(html).toContain("marketing-cloud-surge-layer-a");
    expect(html).toContain("data-cloud-surge");
    expect(html).toContain("marketing-morning-wechat");
    expect(html).toContain("marketing-morning-download");
    expect(html).toContain("下载");
    expect(html).toContain('data-toast-message="亟待展示"');
    expect(html).not.toContain('type="module"');
    expect(html).not.toContain("/src/main.tsx");
    expect(html).not.toContain("./assets/main-");
    expect(html).toContain("./marketing-assets/marketing-morning.png");
    expect(html).toContain("./marketing-assets/marketing-morning-blink.png");
    expect(html).toContain("./marketing-assets/marketing-xiaoju-tail-clear.png");
    expect(html).toContain("./marketing-assets/marketing-xiaoju-tail.png");
    expect(html).not.toContain("./marketing-assets/marketing-cloud-flow.png");
    expect(html).not.toContain("./marketing-assets/yuxin-floating-motion.png");
    expect(html).not.toContain("./marketing-assets/yuxin-clouds-clean.png");
    expect(html).toContain("object-fit: cover;");
    expect(html).toContain("marketing-xiaoju-blink");
    expect(html).toContain("marketing-xiaoju-tail-sway");
    expect(html).toContain("15s linear");
    expect(html).toContain("radial-gradient");
    expect(html).toContain("setCloudSurgeFrame");
    expect(html).toContain("window.requestAnimationFrame");
    expect(html).not.toContain("window.setInterval");
    expect(html).not.toContain("--cloud-a-bg");
    expect(html).not.toContain("--cloud-b-bg");
    expect(html).not.toContain("--cloud-c-bg");
    expect(html).not.toContain("marketing-cloud-surge-roll");
    expect(html).toContain(
      'href="https://discord.gg/AEQqraAtER" target="_blank"',
    );
    expect(html).toContain("./marketing-assets/wechat-qrcode.jpg");
    expect(html).toContain("微信二维码");
    expect(html).toContain("亟待展示");
    expect(html).not.toContain("亟待开发中");
    expect(html).toContain("愈心桌宠_0.2.0_x64-setup.exe");
    expect(WINDOWS_DOWNLOAD_URL).toContain(
      "%E6%84%88%E5%BF%83%E6%A1%8C%E5%AE%A0_0.2.0_x64-setup.exe",
    );
  });

  test("keeps React marketing WeChat popover styles wired to the morning hit target", () => {
    const css = readFileSync(appStylesPath, "utf8");

    expect(css).toContain(
      ".marketing-morning-wechat.is-active .marketing-wechat-popover",
    );
    expect(css).toContain("animation: marketing-xiaoju-blink 15s linear");
    expect(css).toContain("animation: marketing-xiaoju-tail-sway 4.6s");
    expect(css).toContain(".marketing-xiaoju-tail-clear-art");
    expect(css).toContain(".marketing-xiaoju-tail-art");
    expect(css).toContain("transform-origin: 31.8% 32.2%");
    expect(css).toContain("transform: rotate(1.8deg)");
    expect(css).not.toContain("transform: rotate(3.2deg)");
    expect(css).not.toContain("transform: rotate(6.4deg)");
    expect(css).toContain("will-change: transform, opacity");
    expect(css).not.toContain("--cloud-a-bg");
    expect(css).not.toContain("--cloud-b-bg");
    expect(css).not.toContain("--cloud-c-bg");
    expect(css).not.toContain(".marketing-hotspot::before");
    expect(css).not.toContain(".marketing-hotspot:hover::before");
  });

  test("keeps the morning artwork free of visible dashed interaction guides", () => {
    const image = readPngRgba(staticHeroImagePath);
    const guidePixels = [
      [408, 397],
      [424, 387],
      [440, 379],
      [457, 371],
      [490, 359],
      [347, 472],
      [351, 513],
      [358, 528],
      [1093, 226],
      [1111, 222],
      [1128, 219],
      [1147, 216],
      [1198, 215],
      [1217, 217],
      [1236, 221],
      [1254, 227],
      [1303, 297],
      [1294, 314],
      [1282, 330],
      [1267, 344],
    ] as const;

    for (const [x, y] of guidePixels) {
      expect(luminanceAt(image, x, y), `pixel ${x},${y}`).toBeLessThan(220);
    }
  });
});
