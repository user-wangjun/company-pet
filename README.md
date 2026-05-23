# Xiaoju Desktop Pet 小橘猫桌宠

Windows-first desktop pet prototype built with Tauri, React, TypeScript, and PixiJS.

## Local Environment

Prerequisites used by this workspace:

- Node.js 24+
- npm 11+
- Rust stable MSVC toolchain
- Microsoft Visual Studio C++ tools
- Microsoft Edge WebView2 Runtime

Install project dependencies:

```powershell
npm install
```

Run the frontend dev server:

```powershell
npm run dev
```

Run the Tauri desktop app:

```powershell
npm run tauri dev
```

Build the frontend:

```powershell
npm run build
```

If `cargo` is not found in a newly opened terminal, restart the terminal so `%USERPROFILE%\.cargo\bin` is loaded into `PATH`.
