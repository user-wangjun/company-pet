use std::{
    path::{Path, PathBuf},
    process::Command,
};

const RELEASE_DOWNLOAD_PREFIX: &str =
    "https://github.com/user-wangjun/company-pet/releases/download/";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum InstallerKind {
    Windows,
    Macos,
}

#[tauri::command]
pub async fn download_and_open_installer(download_url: String) -> Result<(), String> {
    let installer_path = installer_temp_path(&download_url)?;
    let kind = installer_kind_from_url(&download_url)?;
    ensure_supported_here(kind)?;

    tauri::async_runtime::spawn_blocking(move || {
        download_installer(&download_url, &installer_path)?;
        open_installer(&installer_path)
    })
    .await
    .map_err(|error| error.to_string())?
}

fn installer_kind_from_url(url: &str) -> Result<InstallerKind, String> {
    if !url.starts_with(RELEASE_DOWNLOAD_PREFIX) {
        return Err("安装包地址不可信。".to_string());
    }

    let clean_url = url.split(['?', '#']).next().unwrap_or(url).to_lowercase();
    if clean_url.ends_with(".exe") {
        Ok(InstallerKind::Windows)
    } else if clean_url.ends_with(".dmg") {
        Ok(InstallerKind::Macos)
    } else {
        Err("未找到适合当前系统的安装包。".to_string())
    }
}

fn installer_temp_path(url: &str) -> Result<PathBuf, String> {
    let kind = installer_kind_from_url(url)?;
    let extension = match kind {
        InstallerKind::Windows => ".exe",
        InstallerKind::Macos => ".dmg",
    };
    let clean_url = url.split(['?', '#']).next().unwrap_or(url);
    let raw_name = clean_url.rsplit('/').next().unwrap_or("");
    let safe_name = sanitize_file_name(raw_name);
    let file_name = if safe_name.to_lowercase().ends_with(extension) {
        safe_name
    } else {
        format!("yuxin-update{extension}")
    };

    Ok(std::env::temp_dir().join(file_name))
}

fn sanitize_file_name(name: &str) -> String {
    let sanitized: String = name
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-' | '_') {
                ch
            } else {
                '_'
            }
        })
        .collect();

    sanitized.trim_matches('.').to_string()
}

fn download_installer(download_url: &str, installer_path: &Path) -> Result<(), String> {
    let output = Command::new(curl_bin())
        .args(["-fL", "--retry", "2", "--connect-timeout", "20", "-o"])
        .arg(installer_path)
        .arg(download_url)
        .output()
        .map_err(|error| format!("下载安装包失败：{error}"))?;

    if output.status.success() {
        Ok(())
    } else {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        Err(if detail.is_empty() {
            "下载安装包失败。".to_string()
        } else {
            format!("下载安装包失败：{detail}")
        })
    }
}

#[cfg(target_os = "windows")]
fn curl_bin() -> &'static str {
    "curl.exe"
}

#[cfg(not(target_os = "windows"))]
fn curl_bin() -> &'static str {
    "curl"
}

#[cfg(target_os = "windows")]
fn ensure_supported_here(kind: InstallerKind) -> Result<(), String> {
    if kind == InstallerKind::Windows {
        Ok(())
    } else {
        Err("当前系统不支持这个安装包。".to_string())
    }
}

#[cfg(target_os = "macos")]
fn ensure_supported_here(kind: InstallerKind) -> Result<(), String> {
    if kind == InstallerKind::Macos {
        Ok(())
    } else {
        Err("当前系统不支持这个安装包。".to_string())
    }
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn ensure_supported_here(_kind: InstallerKind) -> Result<(), String> {
    Err("当前系统暂不支持自动安装。".to_string())
}

#[cfg(target_os = "windows")]
fn open_installer(installer_path: &Path) -> Result<(), String> {
    Command::new(installer_path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("打开安装包失败：{error}"))
}

#[cfg(target_os = "macos")]
fn open_installer(installer_path: &Path) -> Result<(), String> {
    Command::new("open")
        .arg(installer_path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("打开安装包失败：{error}"))
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn open_installer(_installer_path: &Path) -> Result<(), String> {
    Err("当前系统暂不支持自动安装。".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_only_release_installers() {
        assert_eq!(
            installer_kind_from_url(
                "https://github.com/user-wangjun/company-pet/releases/download/v0.2.4/yuxin.exe",
            ),
            Ok(InstallerKind::Windows),
        );
        assert_eq!(
            installer_kind_from_url(
                "https://github.com/user-wangjun/company-pet/releases/download/v0.2.4/yuxin.dmg",
            ),
            Ok(InstallerKind::Macos),
        );
        assert!(installer_kind_from_url("https://example.test/yuxin.exe").is_err());
        assert!(
            installer_kind_from_url(
                "https://github.com/user-wangjun/company-pet/releases/download/v0.2.4/yuxin.zip",
            )
            .is_err()
        );
    }

    #[test]
    fn builds_a_safe_temp_installer_path() {
        let path = installer_temp_path(
            "https://github.com/user-wangjun/company-pet/releases/download/v0.2.4/%E6%84%88%E5%BF%83.exe?download=1",
        )
        .expect("valid installer path");

        let file_name = path.file_name().unwrap().to_string_lossy();
        assert!(!file_name.contains('%'));
        assert!(file_name.ends_with(".exe"));
    }
}
