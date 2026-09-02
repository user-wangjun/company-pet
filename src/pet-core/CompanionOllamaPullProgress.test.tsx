import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import {
  CompanionOllamaPullProgress,
  formatBundledOllamaPullProgress,
} from "./CompanionOllamaPullProgress";

describe("CompanionOllamaPullProgress", () => {
  test("formats an indeterminate preparation state", () => {
    const progress = {
      model: "qwen3.5:0.8b",
      status: "准备下载模型",
      completed: null,
      total: null,
      done: false,
    };

    expect(formatBundledOllamaPullProgress(progress)).toBe(
      "正在准备 qwen3.5:0.8b：准备下载模型…",
    );
    expect(renderToStaticMarkup(
      <CompanionOllamaPullProgress progress={progress} />,
    )).not.toContain("<progress");
  });

  test("renders a completed model state and bounded percentage", () => {
    const html = renderToStaticMarkup(
      <CompanionOllamaPullProgress
        progress={{
          model: "qwen3.5:2b",
          status: "success",
          completed: 120,
          total: 100,
          done: true,
        }}
      />,
    );

    expect(html).toContain("模型已准备好");
    expect(html).toContain("qwen3.5:2b 已准备完成，可以开始生成。");
    expect(html).toContain('value="100"');
  });
});
