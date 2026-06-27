import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";

type InstallerUpdateDeps = {
  invoke?: (command: string, args?: Record<string, string>) => Promise<unknown>;
  openUrl?: (url: string) => Promise<unknown>;
  isTauriRuntime?: () => boolean;
};

function defaultIsTauriRuntime(): boolean {
  return (
    typeof window !== "undefined" &&
    "__TAURI_INTERNALS__" in window
  );
}

export function startInstallerUpdate(
  downloadUrl: string,
  deps: InstallerUpdateDeps = {},
): Promise<unknown> {
  const invokeCommand = deps.invoke ?? invoke;
  const openDirectUrl = deps.openUrl ?? openUrl;
  const isTauriRuntime = deps.isTauriRuntime ?? defaultIsTauriRuntime;

  if (isTauriRuntime()) {
    return invokeCommand("download_and_open_installer", { downloadUrl });
  }

  return openDirectUrl(downloadUrl);
}
