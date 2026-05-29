# 愈心桌宠更新接口

应用已预留远程更新检查入口。打包时通过环境变量传入 manifest 地址：

```powershell
$env:VITE_UPDATE_MANIFEST_URL="https://example.com/yuxin/update.json"
$env:VITE_APP_VERSION="0.1.0"
npm run tauri build
```

manifest JSON 格式：

```json
{
  "version": "0.2.0",
  "downloadUrl": "https://example.com/yuxin/愈心桌宠-0.2.0-setup.exe",
  "notes": "更新说明"
}
```

当 `version` 高于当前版本时，应用内“更新”按钮会识别为有新版本。没有配置 `VITE_UPDATE_MANIFEST_URL` 时，按钮会提示更新接口已预留。
