import { existsSync, readdirSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, resolve } from "node:path";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const defaultDistDirectory = resolve(scriptDirectory, "../dist");

export function pruneDeferredAccountAssets(distDirectory = defaultDistDirectory) {
  const deferredDirectories = [
    join(distDirectory, "vendor/live2d-cubism-core"),
    join(distDirectory, "pets/xiaoju-cat/live2d"),
  ];

  for (const directory of deferredDirectories) {
    if (existsSync(directory)) rmSync(directory, { recursive: true, force: true });
  }

  const xiaojuDirectory = join(distDirectory, "pets/xiaoju-cat");
  if (!existsSync(xiaojuDirectory)) return;

  for (const name of readdirSync(xiaojuDirectory)) {
    if (/^login-.*\.png$/i.test(name)) {
      rmSync(join(xiaojuDirectory, name), { force: true });
    }
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (invokedPath === import.meta.url) pruneDeferredAccountAssets();
