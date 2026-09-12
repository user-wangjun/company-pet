use std::{fs, path::{Path, PathBuf}};
use serde::Serialize;
use tauri::Manager;
use tauri_plugin_opener::OpenerExt;

fn plugin_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path().app_data_dir().map(|path| path.join("pet-plugins")).map_err(|_| "无法定位插件目录".into())
}

fn valid_id(id: &str) -> bool {
    id.len() <= 80 && id.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
        && id.split('-').all(|part| !part.is_empty() && part.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit()))
}

// Resolve actual files, including junction targets, before serving any package data.
fn resolve_asset(root: &Path, relative: &str) -> Result<PathBuf, String> {
    let parts: Vec<_> = relative.split('/').collect();
    if parts.len() < 2 || !valid_id(parts[0]) || parts.iter().any(|part| part.is_empty()
        || *part == "." || *part == ".." || part.ends_with(['.', ' '])
        || part.chars().any(|c| c.is_control() || "%\\:?#".contains(c))) {
        return Err("插件资源路径无效".into());
    }
    let root = root.canonicalize().map_err(|_| "插件目录不可用")?;
    let package = root.join(parts[0]).canonicalize().map_err(|_| "插件不存在")?;
    if package.parent() != Some(root.as_path()) { return Err("插件目录越界".into()); }
    let file = package.join(parts[1..].join("/")).canonicalize().map_err(|_| "插件资源不存在")?;
    if !file.starts_with(&package) || !file.is_file() { return Err("插件资源越界".into()); }
    Ok(file)
}

fn mime(path: &Path) -> Option<&'static str> {
    match path.extension()?.to_str()?.to_ascii_lowercase().as_str() {
        "json" => Some("application/json"), "png" => Some("image/png"),
        "jpg" | "jpeg" => Some("image/jpeg"), "webp" => Some("image/webp"),
        "ogg" => Some("audio/ogg"), "mp3" => Some("audio/mpeg"), "wav" => Some("audio/wav"),
        _ => None,
    }
}

fn read_manifest(root: &Path, id: &str) -> Result<(), String> {
    let path = resolve_asset(root, &format!("{id}/pet.json"))?;
    if fs::metadata(&path).map_err(|_| "无法读取插件")?.len() > 1024 * 1024 { return Err("插件清单过大".into()); }
    let manifest: serde_json::Value = serde_json::from_slice(&fs::read(path).map_err(|_| "无法读取插件")?).map_err(|_| "插件清单格式无效")?;
    if manifest["id"].as_str() != Some(id) || manifest["displayName"].as_str().is_none_or(str::is_empty)
        || !manifest["interactions"].is_object() || (!manifest["rig2d"].is_object() && !manifest["spritesheetPath"].is_string())
        || manifest.get("kind").is_some_and(|kind| !matches!(kind.as_str(), Some("pet" | "human"))) {
        return Err("插件角色清单无效".into());
    }
    Ok(())
}

#[derive(Serialize)]
pub struct PetPluginCatalog { pets: Vec<String>, errors: Vec<String> }

fn scan_plugins(root: &Path) -> Result<PetPluginCatalog, String> {
    let mut catalog = PetPluginCatalog { pets: Vec::new(), errors: Vec::new() };
    if !root.exists() { return Ok(catalog); }
    for entry in fs::read_dir(root).map_err(|_| "无法读取插件目录")? {
        let entry = entry.map_err(|_| "无法读取插件目录")?;
        let id = entry.file_name().to_string_lossy().into_owned();
        if !entry.path().is_dir() { continue; }
        match read_manifest(root, &id) {
            Ok(()) => catalog.pets.push(id),
            Err(error) => catalog.errors.push(format!("{id}: {error}")),
        }
    }
    catalog.pets.sort();
    Ok(catalog)
}

#[tauri::command]
pub fn list_pet_plugins(app: tauri::AppHandle) -> Result<PetPluginCatalog, String> {
    scan_plugins(&plugin_root(&app)?)
}

#[tauri::command]
pub fn open_pet_plugins_folder(app: tauri::AppHandle) -> Result<(), String> {
    let root = plugin_root(&app)?;
    fs::create_dir_all(&root).map_err(|_| "无法创建插件目录")?;
    app.opener().open_path(root.to_string_lossy(), None::<String>).map_err(|_| "无法打开插件目录".into())
}

pub fn serve(app: &tauri::AppHandle, request: tauri::http::Request<Vec<u8>>) -> tauri::http::Response<Vec<u8>> {
    let origin = request.headers().get("origin").and_then(|value| value.to_str().ok());
    let allowed_origin = origin.is_none_or(|value| matches!(value,
        "http://tauri.localhost" | "https://tauri.localhost" | "tauri://localhost" | "http://localhost:1420" | "http://127.0.0.1:1420"));
    let result = (|| {
        if !allowed_origin || request.method() != tauri::http::Method::GET { return Err("请求不允许".to_owned()); }
        let root = plugin_root(app)?;
        let path = resolve_asset(&root, request.uri().path().trim_start_matches('/'))?;
        let content_type = mime(&path).ok_or("插件不允许加载此文件类型")?;
        if fs::metadata(&path).map_err(|_| "无法读取插件资源")?.len() > 128 * 1024 * 1024 { return Err("插件资源过大".into()); }
        let bytes = fs::read(path).map_err(|_| "无法读取插件资源")?;
        Ok((content_type, bytes))
    })();
    let (status, content_type, body) = match result {
        Ok((content_type, bytes)) => (200, content_type, bytes),
        Err(_) => (404, "text/plain", b"Plugin asset unavailable".to_vec()),
    };
    tauri::http::Response::builder().status(status)
        .header("Content-Type", content_type)
        .header("Access-Control-Allow-Origin", if allowed_origin { origin.unwrap_or("http://tauri.localhost") } else { "null" })
        .header("Cache-Control", "no-store")
        .header("X-Content-Type-Options", "nosniff")
        .body(body).unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scans_valid_plugins_and_rejects_bad_ids_paths_and_executables() {
        let root = std::env::temp_dir().join(format!("yuxin-plugin-test-{}", std::process::id()));
        fs::create_dir_all(root.join("test-human")).unwrap();
        fs::write(root.join("test-human/pet.json"), r#"{"id":"test-human","displayName":"Test","kind":"human","interactions":{},"rig2d":{}}"#).unwrap();
        assert_eq!(scan_plugins(&root).unwrap().pets, vec!["test-human"]);
        for path in ["../test-human/pet.json", "test-human/../secret.json", "test-human/%2e%2e/secret.json", "test-human/C:/secret.json", "test-human/pet.json."] {
            assert!(resolve_asset(&root, path).is_err());
        }
        assert_eq!(mime(Path::new("payload.js")), None);
        assert_eq!(mime(Path::new("payload.exe")), None);
        assert_eq!(mime(Path::new("sprite.png")), Some("image/png"));
        fs::write(root.join("test-human/pet.json"), r#"{"id":"wrong"}"#).unwrap();
        assert!(scan_plugins(&root).unwrap().pets.is_empty());
        assert_eq!(scan_plugins(&root).unwrap().errors.len(), 1);
        fs::remove_dir_all(root).unwrap();
    }
}
