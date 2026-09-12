import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
// @ts-expect-error Node built-ins run only in the Vite configuration.
import { readdirSync, readFileSync, existsSync } from "node:fs";

// @ts-expect-error process is a nodejs global
const tauriDevHost = process.env.TAURI_DEV_HOST;
const devServerHost = tauriDevHost || "127.0.0.1";

// Unregistered local character packages are visible only to the development server.
const localPetPackages: Plugin = {
  name: "local-pet-packages",
  configureServer(server) {
    server.middlewares.use("/local-pets.json", (_request, response) => {
      try {
        const directory = `${server.config.root}/public/pets`;
        const builtIns = JSON.parse(readFileSync(`${directory}/index.json`, "utf8")).pets as string[];
        const pets = (readdirSync(directory) as string[]).filter(id =>
          /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(id) && !builtIns.includes(id)
          && existsSync(`${directory}/${id}/pet.json`));
        response.setHeader("Content-Type", "application/json");
        response.end(JSON.stringify({ pets }));
      } catch {
        response.statusCode = 500;
        response.end(JSON.stringify({ pets: [] }));
      }
    });
  },
};

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), localPetPackages],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: devServerHost,
    hmr: tauriDevHost
      ? {
          protocol: "ws",
          host: tauriDevHost,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
