import {
  createHash,
} from "node:crypto";
import {
  cpSync,
  createReadStream,
  createWriteStream,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";
import { fileURLToPath } from "node:url";

const OLLAMA_VERSION = "v0.33.2";
const OLLAMA_ARCHIVE_SHA256 =
  "2439cbea65310b1aadf7d8fc41d7faf5d033f920d42e00a476c58bf9bff6950e";
const OLLAMA_ARCHIVE_URL =
  `https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-windows-amd64.zip`;

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectDirectory = resolve(scriptDirectory, "..");
const runtimeDirectory = join(
  projectDirectory,
  "src-tauri",
  "resources",
  "ollama",
  "windows-x86_64",
);
const runtimeManifestPath = join(runtimeDirectory, ".runtime-manifest.json");

function findFile(directory, fileName) {
  if (!existsSync(directory)) return null;
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const entryPath = join(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = findFile(entryPath, fileName);
      if (nested) return nested;
    } else if (entry.isFile() && entry.name.toLowerCase() === fileName.toLowerCase()) {
      return entryPath;
    }
  }
  return null;
}

function runtimeAlreadyPrepared() {
  if (
    !existsSync(join(runtimeDirectory, "ollama.exe"))
    || !existsSync(join(runtimeDirectory, "lib", "ollama", "llama-server.exe"))
    || !existsSync(runtimeManifestPath)
  ) {
    return false;
  }
  try {
    const manifest = JSON.parse(readFileSync(runtimeManifestPath, "utf8"));
    return manifest.version === OLLAMA_VERSION
      && manifest.archiveSha256 === OLLAMA_ARCHIVE_SHA256;
  } catch {
    return false;
  }
}

async function sha256File(filePath) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(filePath)) hash.update(chunk);
  return hash.digest("hex");
}

async function downloadArchive(archivePath) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(OLLAMA_ARCHIVE_URL, {
      redirect: "follow",
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error(`下载 Ollama ${OLLAMA_VERSION} 失败（HTTP ${response.status}）。`);
    }
    await pipeline(
      Readable.fromWeb(response.body),
      createWriteStream(archivePath),
    );
    return;
  } catch (error) {
    console.warn("Node 下载流未能在 30 秒内完成，改用 Windows curl.exe 重试。", error.message);
  } finally {
    clearTimeout(timeout);
  }

  execFileSync(
    "curl.exe",
    [
      "--location",
      "--fail",
      "--retry",
      "3",
      "--retry-delay",
      "2",
      "--output",
      archivePath,
      OLLAMA_ARCHIVE_URL,
    ],
    { stdio: "inherit" },
  );
}

function extractArchive(archivePath, extractDirectory) {
  const environment = {
    ...process.env,
    YUXIN_OLLAMA_ARCHIVE: archivePath,
    YUXIN_OLLAMA_EXTRACT: extractDirectory,
  };
  try {
    execFileSync(
      "powershell.exe",
      [
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$ErrorActionPreference = 'Stop'; Expand-Archive -LiteralPath $env:YUXIN_OLLAMA_ARCHIVE -DestinationPath $env:YUXIN_OLLAMA_EXTRACT -Force",
      ],
      { stdio: "inherit", env: environment },
    );
  } catch {
    console.warn("Expand-Archive 不可用，改用 Windows 自带 tar.exe 解压。\n");
    execFileSync(
      "tar.exe",
      ["-xf", archivePath, "-C", extractDirectory],
      { stdio: "inherit" },
    );
  }
}

function findRuntimeRoot(executablePath) {
  let root = dirname(executablePath);
  const parent = dirname(root);
  if (!existsSync(join(root, "lib")) && existsSync(join(parent, "lib"))) root = parent;
  return root;
}

async function prepareRuntime() {
  if (process.platform !== "win32") {
    console.log("Skipping bundled Ollama preparation outside Windows.");
    return;
  }
  if (process.arch !== "x64") {
    throw new Error(`Bundled Ollama currently requires Windows x64; found ${process.arch}.`);
  }
  if (runtimeAlreadyPrepared()) {
    console.log(`Bundled Ollama ${OLLAMA_VERSION} is already prepared.`);
    return;
  }

  mkdirSync(dirname(runtimeDirectory), { recursive: true });
  const temporaryDirectory = mkdtempSync(join(tmpdir(), "yuxin-ollama-"));
  const archivePath = join(temporaryDirectory, "ollama-windows-amd64.zip");
  const extractDirectory = join(temporaryDirectory, "extracted");
  const stagingDirectory = `${runtimeDirectory}.staging-${process.pid}`;

  try {
    const archiveOverride = process.env.YUXIN_OLLAMA_ARCHIVE_PATH?.trim();
    if (archiveOverride) {
      const sourceArchive = resolve(archiveOverride);
      if (!existsSync(sourceArchive)) {
        throw new Error(`指定的 Ollama 归档不存在：${sourceArchive}`);
      }
      console.log(`Using verified local Ollama archive ${sourceArchive}...`);
      cpSync(sourceArchive, archivePath);
    } else {
      console.log(`Downloading bundled Ollama ${OLLAMA_VERSION}...`);
      await downloadArchive(archivePath);
    }
    const actualHash = await sha256File(archivePath);
    if (actualHash !== OLLAMA_ARCHIVE_SHA256) {
      throw new Error(
        `Ollama archive SHA-256 mismatch: expected ${OLLAMA_ARCHIVE_SHA256}, got ${actualHash}.`,
      );
    }

    mkdirSync(extractDirectory, { recursive: true });
    extractArchive(archivePath, extractDirectory);
    const executablePath = findFile(extractDirectory, "ollama.exe");
    if (!executablePath) throw new Error("Ollama archive did not contain ollama.exe.");

    rmSync(stagingDirectory, { recursive: true, force: true });
    const runtimeRoot = findRuntimeRoot(executablePath);
    mkdirSync(stagingDirectory, { recursive: true });
    cpSync(executablePath, join(stagingDirectory, "ollama.exe"));
    const libraryDirectory = join(runtimeRoot, "lib");
    if (!existsSync(libraryDirectory)) {
      throw new Error("Ollama archive is missing its lib directory.");
    }
    cpSync(libraryDirectory, join(stagingDirectory, "lib"), { recursive: true });
    const readmePath = join(runtimeDirectory, "README.md");
    if (existsSync(readmePath)) cpSync(readmePath, join(stagingDirectory, "README.md"));
    if (!existsSync(join(stagingDirectory, "ollama.exe"))) {
      throw new Error("Prepared Ollama runtime is missing ollama.exe.");
    }
    if (!existsSync(join(stagingDirectory, "lib", "ollama", "llama-server.exe"))) {
      throw new Error("Prepared Ollama runtime is missing lib/ollama/llama-server.exe.");
    }
    writeFileSync(
      join(stagingDirectory, ".runtime-manifest.json"),
      `${JSON.stringify({
        source: "official Ollama Windows standalone archive",
        version: OLLAMA_VERSION,
        archiveUrl: OLLAMA_ARCHIVE_URL,
        archiveSha256: OLLAMA_ARCHIVE_SHA256,
      }, null, 2)}\n`,
      "utf8",
    );

    rmSync(runtimeDirectory, { recursive: true, force: true });
    renameSync(stagingDirectory, runtimeDirectory);
    console.log(`Bundled Ollama ${OLLAMA_VERSION} prepared in ${runtimeDirectory}.`);
  } finally {
    rmSync(stagingDirectory, { recursive: true, force: true });
    rmSync(temporaryDirectory, { recursive: true, force: true });
  }
}

await prepareRuntime();
