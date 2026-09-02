#[cfg(test)]
mod tests {
    use std::{
        collections::BTreeMap,
        ffi::OsString,
        path::PathBuf,
        time::{SystemTime, UNIX_EPOCH},
    };

    use tauri::utils::config::{Config, WebviewUrl, WindowConfig};

    use super::{validate_startup_config, StartupMode};

    fn unique_scope() -> PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock should be after unix epoch")
            .as_nanos();
        let scope = std::env::temp_dir().join(format!("yuxin-startup-guard-{suffix}"));
        std::fs::create_dir_all(&scope).expect("test scope should be creatable");
        scope
    }

    fn environment(scope: &std::path::Path, case_id: &str) -> BTreeMap<OsString, OsString> {
        let mut values: BTreeMap<OsString, OsString> = BTreeMap::new();
        values.insert(
            "XIAOJU_SELF_TEST_RUN_ID".into(),
            "tauri-chat-test-20260827-0001".into(),
        );
        values.insert(
            "XIAOJU_SELF_TEST_RUN_SEGMENTS".into(),
            "A,B,C,D,E,F,G,H".into(),
        );
        values.insert("XIAOJU_SELF_TEST_CASE".into(), case_id.into());
        values.insert(
            "XIAOJU_SELF_TEST_RUN_HASH".into(),
            "sha256:0123456789abcdef".into(),
        );
        values.insert(
            "XIAOJU_SELF_TEST_LOG".into(),
            scope
                .join("sanitized-events.ndjson")
                .display()
                .to_string()
                .into(),
        );
        values.insert(
            "XIAOJU_SELF_TEST_DATA_ROOT".into(),
            scope.join("runtime").display().to_string().into(),
        );
        values
    }

    fn config(identifier: &str, create_windows: bool) -> Config {
        let mut config = Config::default();
        config.product_name = Some("愈心桌宠".into());
        config.identifier = identifier.into();

        let mut main = WindowConfig::default();
        main.label = "main".into();
        main.create = create_windows;
        main.title = "愈心桌宠".into();
        main.width = 165.0;
        main.height = 215.0;
        main.transparent = true;
        main.decorations = false;
        main.always_on_top = true;
        main.skip_taskbar = true;
        main.visible = false;
        main.resizable = false;
        main.shadow = false;

        let mut platform = WindowConfig::default();
        platform.label = "platform".into();
        platform.create = create_windows;
        platform.title = "愈心桌宠".into();
        platform.url = WebviewUrl::App(PathBuf::from("index.html?window=platform"));
        platform.width = 860.0;
        platform.height = 590.0;
        platform.min_width = Some(560.0);
        platform.min_height = Some(420.0);
        platform.center = true;
        platform.transparent = true;
        platform.decorations = false;
        platform.always_on_top = true;
        platform.skip_taskbar = false;
        platform.visible = false;
        platform.resizable = true;
        platform.maximizable = true;
        platform.minimizable = true;
        platform.shadow = false;

        config.app.windows = vec![main, platform];
        config
    }

    fn isolated_identifier() -> &'static str {
        "com.yuxin.desktop.tauri-chat-evidence-tauri-chat-test-20260827-0001"
    }

    #[test]
    fn rejects_partial_acceptance_environment_before_any_effect() {
        let scope = unique_scope();
        let mut values: BTreeMap<OsString, OsString> = BTreeMap::new();
        values.insert(
            "XIAOJU_SELF_TEST_LOG".into(),
            scope.join("events.ndjson").display().to_string().into(),
        );
        let mut effects = 0;
        let result = validate_startup_config(&config(isolated_identifier(), false), &values);
        if result.is_ok() {
            effects += 1;
        }
        assert!(
            result.is_err(),
            "partial acceptance parameters must fail closed"
        );
        assert_eq!(effects, 0, "the build/window side-effect gate must not run");
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }

    #[test]
    fn rejects_default_window_creation_in_strict_mode() {
        let scope = unique_scope();
        let values = environment(&scope, "B");
        let result = validate_startup_config(&config(isolated_identifier(), true), &values);
        assert!(
            result.is_err(),
            "strict mode must reject framework-created windows"
        );
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }

    #[test]
    fn rejects_data_root_traversal_and_out_of_scope_paths() {
        let scope = unique_scope();
        let mut values = environment(&scope, "B");

        values.insert(
            "XIAOJU_SELF_TEST_DATA_ROOT".into(),
            scope
                .join("..")
                .join("escaped-runtime")
                .display()
                .to_string()
                .into(),
        );
        assert!(validate_startup_config(&config(isolated_identifier(), false), &values).is_err());

        values.insert(
            "XIAOJU_SELF_TEST_DATA_ROOT".into(),
            scope
                .parent()
                .expect("temporary scope should have a parent")
                .join("outside-runtime")
                .display()
                .to_string()
                .into(),
        );
        assert!(validate_startup_config(&config(isolated_identifier(), false), &values).is_err());
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }

    #[test]
    fn rejects_identifier_that_does_not_match_declared_run_and_case() {
        let scope = unique_scope();
        let values = environment(&scope, "B");
        let result = validate_startup_config(
            &config("com.yuxin.desktop.tauri-chat-evidence-other-run", false),
            &values,
        );
        assert!(result.is_err());
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }

    #[test]
    fn accepts_valid_isolated_config_and_normal_formal_config() {
        let scope = unique_scope();
        let values = environment(&scope, "B");
        let isolated = validate_startup_config(&config(isolated_identifier(), false), &values)
            .expect("valid isolated config should pass");
        assert!(matches!(isolated, StartupMode::SelfTest(_)));

        let normal = validate_startup_config(&config("com.yuxin.desktop", true), &BTreeMap::new())
            .expect("normal formal config should remain compatible");
        assert!(matches!(normal, StartupMode::Normal));
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }

    #[test]
    fn accepts_formal_identifier_only_for_read_only_a_segment() {
        let scope = unique_scope();
        let values = environment(&scope, "A");
        let result = validate_startup_config(&config("com.yuxin.desktop", false), &values)
            .expect("A must be allowed to retain the formal identifier");
        assert!(matches!(result, StartupMode::SelfTest(_)));
        std::fs::remove_dir_all(scope).expect("test scope should be removable");
    }
}
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::{OsStr, OsString},
    fs,
    path::{Component, Path, PathBuf},
};

use tauri::utils::config::{Config, WebviewUrl, WindowConfig};

const SELF_TEST_PREFIX: &str = "XIAOJU_SELF_TEST_";
const SELF_TEST_ENV_NAMES: [&str; 6] = [
    "XIAOJU_SELF_TEST_CASE",
    "XIAOJU_SELF_TEST_DATA_ROOT",
    "XIAOJU_SELF_TEST_LOG",
    "XIAOJU_SELF_TEST_RUN_HASH",
    "XIAOJU_SELF_TEST_RUN_ID",
    "XIAOJU_SELF_TEST_RUN_SEGMENTS",
];
const FORMAL_IDENTIFIER: &str = "com.yuxin.desktop";
const ISOLATED_IDENTIFIER_PREFIX: &str = "com.yuxin.desktop.tauri-chat-evidence-";
const EXPECTED_PRODUCT_NAME: &str = "愈心桌宠";

#[derive(Clone, Debug)]
pub(crate) struct ValidatedSelfTest {
    pub(crate) _case_id: String,
    pub(crate) data_root: PathBuf,
    pub(crate) _log_path: PathBuf,
    pub(crate) _run_id: String,
    pub(crate) _run_id_hash: String,
    pub(crate) window_configs: Vec<WindowConfig>,
}

#[derive(Clone, Debug)]
pub(crate) enum StartupMode {
    Normal,
    SelfTest(ValidatedSelfTest),
}

pub(crate) fn collect_self_test_environment() -> BTreeMap<OsString, OsString> {
    std::env::vars_os()
        .filter(|(key, _)| key.to_string_lossy().starts_with(SELF_TEST_PREFIX))
        .collect()
}

pub(crate) fn validate_startup_config(
    config: &Config,
    environment: &BTreeMap<OsString, OsString>,
) -> Result<StartupMode, String> {
    let has_acceptance_environment = environment
        .keys()
        .any(|key| key.to_string_lossy().starts_with(SELF_TEST_PREFIX));
    if !has_acceptance_environment {
        return Ok(StartupMode::Normal);
    }

    let allowed_names: BTreeSet<&str> = SELF_TEST_ENV_NAMES.into_iter().collect();
    for key in environment.keys() {
        let name = key.to_string_lossy();
        if name.starts_with(SELF_TEST_PREFIX) && !allowed_names.contains(name.as_ref()) {
            return Err(format!("未知的验收启动参数：{name}。"));
        }
    }

    let case_id = required_value(environment, "XIAOJU_SELF_TEST_CASE")?;
    let data_root_raw = required_value(environment, "XIAOJU_SELF_TEST_DATA_ROOT")?;
    let log_path_raw = required_value(environment, "XIAOJU_SELF_TEST_LOG")?;
    let run_id = required_value(environment, "XIAOJU_SELF_TEST_RUN_ID")?;
    let run_id_hash = required_value(environment, "XIAOJU_SELF_TEST_RUN_HASH")?;
    let run_segments = required_value(environment, "XIAOJU_SELF_TEST_RUN_SEGMENTS")?;

    validate_case_id(&case_id)?;
    validate_run_id(&run_id)?;
    if run_segments != "A,B,C,D,E,F,G,H" {
        return Err("验收运行段必须完整声明为 A,B,C,D,E,F,G,H。".into());
    }
    if !is_run_hash(&run_id_hash) {
        return Err("验收运行标识哈希无效。".into());
    }

    let log_path = resolve_absolute_path(&log_path_raw, "验收日志")?;
    let log_path = canonicalize_with_missing_tail(&log_path, "验收日志", true)?;
    let scope_root = log_path
        .parent()
        .ok_or_else(|| "验收日志必须位于明确的运行目录中。".to_owned())?;
    let scope_root = canonical_existing_directory(scope_root, "验收运行目录")?;
    if log_path.parent() != Some(scope_root.as_path()) {
        return Err("验收日志必须是运行目录的直接子文件。".into());
    }

    let data_root = resolve_absolute_path(&data_root_raw, "隔离 WebView 数据目录")?;
    let data_root = canonicalize_with_missing_tail(&data_root, "隔离 WebView 数据目录", false)?;
    if !is_strict_child_of(&data_root, &scope_root) {
        return Err("隔离 WebView 数据目录越出本轮运行目录。".into());
    }
    if is_formal_data_root(&data_root) {
        return Err("隔离 WebView 数据目录不能落入正式应用根。".into());
    }

    let window_configs = validate_window_config(config)?;
    let expected_identifier = if case_id == "A" {
        FORMAL_IDENTIFIER.to_owned()
    } else {
        format!("{ISOLATED_IDENTIFIER_PREFIX}{run_id}")
    };
    if config.identifier != expected_identifier {
        return Err(format!(
            "验收 identifier 与运行段不匹配：期望 {expected_identifier}，实际 {}。",
            config.identifier
        ));
    }

    Ok(StartupMode::SelfTest(ValidatedSelfTest {
        _case_id: case_id,
        data_root,
        _log_path: log_path,
        _run_id: run_id,
        _run_id_hash: run_id_hash,
        window_configs,
    }))
}

fn required_value(
    environment: &BTreeMap<OsString, OsString>,
    name: &str,
) -> Result<String, String> {
    let value = environment
        .get(OsStr::new(name))
        .ok_or_else(|| format!("验收启动参数不完整，缺少 {name}。"))?;
    let value = value
        .to_str()
        .ok_or_else(|| format!("验收启动参数 {name} 不是有效 UTF-8。"))?
        .trim();
    if value.is_empty() {
        return Err(format!("验收启动参数 {name} 不能为空。"));
    }
    Ok(value.to_owned())
}

fn validate_case_id(case_id: &str) -> Result<(), String> {
    if matches!(case_id, "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H") {
        Ok(())
    } else {
        Err("验收 case 必须是 A-H 之一。".into())
    }
}

fn validate_run_id(run_id: &str) -> Result<(), String> {
    if !(run_id.starts_with("tauri-chat-")
        && (12..=96).contains(&run_id.len())
        && run_id.chars().all(|character| {
            character.is_ascii_lowercase()
                || character.is_ascii_digit()
                || matches!(character, '-' | '.')
        }))
    {
        return Err("验收 runId 无效。".into());
    }
    Ok(())
}

fn is_run_hash(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    (8..=64).contains(&hex.len()) && hex.chars().all(|character| character.is_ascii_hexdigit())
}

fn resolve_absolute_path(raw: &str, label: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw);
    if !path.is_absolute() {
        return Err(format!("{label}必须是绝对路径。"));
    }
    for component in path.components() {
        if matches!(component, Component::ParentDir | Component::CurDir) {
            return Err(format!("{label}不能包含路径穿越组件。"));
        }
    }
    reject_reparse_components(&path, label)?;
    Ok(path)
}

fn reject_reparse_components(path: &Path, label: &str) -> Result<(), String> {
    let mut current = PathBuf::new();
    for component in path.components() {
        current.push(component.as_os_str());
        if let Ok(metadata) = fs::symlink_metadata(&current) {
            if is_reparse_point(&metadata) {
                return Err(format!("{label}不能经过链接或 junction。"));
            }
        }
    }
    Ok(())
}

fn is_reparse_point(metadata: &fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;

        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0400;
        metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

fn canonical_existing_directory(path: &Path, label: &str) -> Result<PathBuf, String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|error| format!("{label}不存在或不可读：{error}"))?;
    if !metadata.is_dir() {
        return Err(format!("{label}必须是目录。"));
    }
    if is_reparse_point(&metadata) {
        return Err(format!("{label}不能是链接或 junction。"));
    }
    fs::canonicalize(path).map_err(|error| format!("{label}无法规范化：{error}"))
}

fn canonicalize_with_missing_tail(
    path: &Path,
    label: &str,
    allow_file: bool,
) -> Result<PathBuf, String> {
    let mut current = path.to_owned();
    let mut missing_tail = Vec::new();
    loop {
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if is_reparse_point(&metadata) {
                    return Err(format!("{label}不能是链接或 junction。"));
                }
                if !metadata.is_dir() && !(allow_file && current == path) {
                    return Err(format!("{label}的已存在部分不是目录。"));
                }
                let canonical = fs::canonicalize(&current)
                    .map_err(|error| format!("{label}无法规范化：{error}"))?;
                let result = missing_tail
                    .iter()
                    .rev()
                    .fold(canonical, |base, component| base.join(component));
                return Ok(result);
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                let component = current
                    .file_name()
                    .ok_or_else(|| format!("{label}缺少可解析的末级路径。"))?;
                missing_tail.push(component.to_owned());
                if !current.pop() {
                    return Err(format!("{label}无法找到已存在的父目录。"));
                }
            }
            Err(error) => return Err(format!("{label}无法读取：{error}")),
        }
    }
}

fn is_strict_child_of(path: &Path, root: &Path) -> bool {
    let path = normalized_path_text(path);
    let root = normalized_path_text(root);
    is_strict_child_text(&path, &root)
}

fn is_formal_data_root(path: &Path) -> bool {
    ["APPDATA", "LOCALAPPDATA"]
        .into_iter()
        .filter_map(|name| std::env::var_os(name))
        .map(PathBuf::from)
        .map(|base| base.join(FORMAL_IDENTIFIER))
        .any(|formal_root| is_same_or_child_of(path, &formal_root))
}

fn is_same_or_child_of(path: &Path, root: &Path) -> bool {
    let path = normalized_path_text(path);
    let root = normalized_path_text(root);
    path.eq_ignore_ascii_case(&root) || is_strict_child_text(&path, &root)
}

fn normalized_path_text(path: &Path) -> String {
    let mut value = path.to_string_lossy().replace('/', "\\");
    if let Some(without_device_prefix) = value.strip_prefix(r"\\?\") {
        value = without_device_prefix.to_owned();
    }
    value = value.trim_end_matches('\\').to_owned();
    value
}

fn is_strict_child_text(path: &str, root: &str) -> bool {
    path.len() > root.len()
        && path[..root.len()].eq_ignore_ascii_case(root)
        && path
            .as_bytes()
            .get(root.len())
            .is_some_and(|separator| *separator == b'\\')
}

fn validate_window_config(config: &Config) -> Result<Vec<WindowConfig>, String> {
    if config.product_name.as_deref() != Some(EXPECTED_PRODUCT_NAME) {
        return Err("验收 productName 与正式桌面应用不匹配。".into());
    }
    if config.app.windows.len() != 2 {
        return Err("验收配置必须只声明 main/platform 两个窗口。".into());
    }

    let mut main = None;
    let mut platform = None;
    let configured_data_directory = config.app.windows[0].data_directory.clone();
    for window in &config.app.windows {
        if window.data_directory != configured_data_directory {
            return Err("main/platform 的配置数据目录不一致。".into());
        }
        if window.create {
            return Err(format!("验收窗口 {} 不能由框架自动创建。", window.label));
        }
        if window.visible {
            return Err(format!("验收窗口 {} 必须保持初始隐藏。", window.label));
        }
        match window.label.as_str() {
            "main" if main.is_none() => main = Some(window),
            "platform" if platform.is_none() => platform = Some(window),
            _ => return Err("验收窗口 label 必须唯一且只能是 main/platform。".into()),
        }
    }

    let main = main.ok_or_else(|| "验收配置缺少 main 窗口。".to_owned())?;
    if main.title != EXPECTED_PRODUCT_NAME
        || main.width != 165.0
        || main.height != 215.0
        || !main.transparent
        || main.decorations
        || !main.always_on_top
        || !main.skip_taskbar
        || main.resizable
        || main.shadow
    {
        return Err("main 窗口配置不符合验收合同。".into());
    }
    if !matches!(&main.url, WebviewUrl::App(_)) {
        return Err("main 窗口必须使用内置页面。".into());
    }

    let platform = platform.ok_or_else(|| "验收配置缺少 platform 窗口。".to_owned())?;
    let platform_url_ok = match &platform.url {
        WebviewUrl::App(path) => path.to_string_lossy() == "index.html?window=platform",
        _ => false,
    };
    if !platform_url_ok
        || platform.title != EXPECTED_PRODUCT_NAME
        || platform.width != 860.0
        || platform.height != 590.0
        || platform.min_width != Some(560.0)
        || platform.min_height != Some(420.0)
        || !platform.center
        || !platform.transparent
        || platform.decorations
        || !platform.always_on_top
        || platform.skip_taskbar
        || !platform.resizable
        || !platform.maximizable
        || !platform.minimizable
        || platform.shadow
    {
        return Err("platform 窗口配置不符合验收合同。".into());
    }

    Ok(config.app.windows.clone())
}
