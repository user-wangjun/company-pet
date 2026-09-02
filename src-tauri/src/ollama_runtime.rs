use std::{
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{async_runtime::Mutex, AppHandle, Emitter, Manager, State};

const OLLAMA_PULL_TIMEOUT: Duration = Duration::from_secs(30 * 60);
const OLLAMA_CHAT_TIMEOUT: Duration = Duration::from_secs(10 * 60);
const OLLAMA_HEALTH_TIMEOUT: Duration = Duration::from_secs(2);
const OLLAMA_STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
const MAX_OLLAMA_CHAT_REQUEST_BYTES: usize = 2 * 1024 * 1024;
const MAX_OLLAMA_MODEL_LIST_BYTES: u64 = 4 * 1024 * 1024;
const MAX_OLLAMA_CHAT_RESPONSE_BYTES: u64 = 4 * 1024 * 1024;
const MAX_OLLAMA_PULL_LINE_BYTES: usize = 64 * 1024;
const OLLAMA_PULL_EVENT: &str = "ollama-pull-progress";

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OllamaModelListResponse {
    pub status: u16,
    pub payload: Value,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OllamaChatResponse {
    pub status: u16,
    pub payload: Value,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OllamaRuntimeStatus {
    pub available: bool,
    pub running: bool,
    pub version: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct OllamaPullProgress {
    model: String,
    status: String,
    completed: Option<u64>,
    total: Option<u64>,
    done: bool,
}

struct ManagedOllamaProcess {
    child: Child,
    base_url: String,
    version: String,
}

pub struct OllamaRuntimeState {
    process: Mutex<Option<ManagedOllamaProcess>>,
    model_pull: Mutex<()>,
}

impl Default for OllamaRuntimeState {
    fn default() -> Self {
        Self {
            process: Mutex::new(None),
            model_pull: Mutex::new(()),
        }
    }
}

struct RuntimeConnection {
    base_url: String,
}

fn client(timeout: Duration) -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .connect_timeout(OLLAMA_HEALTH_TIMEOUT)
        .timeout(timeout)
        .build()
        .map_err(|_| "本地 Ollama 网络客户端初始化失败。".to_owned())
}

#[cfg(all(target_os = "windows", target_arch = "x86_64"))]
fn path_from_runtime_hint(value: &str) -> Option<PathBuf> {
    let path = PathBuf::from(value.trim());
    path.is_file().then_some(path)
}

#[cfg(all(target_os = "windows", target_arch = "x86_64"))]
fn executable_from_path() -> Option<PathBuf> {
    std::env::var_os("PATH")
        .into_iter()
        .flat_map(|value| std::env::split_paths(&value).collect::<Vec<_>>())
        .map(|directory| directory.join("ollama.exe"))
        .find(|path| path.is_file())
}

#[cfg(all(target_os = "windows", target_arch = "x86_64"))]
fn resolve_ollama_executable(app: &AppHandle) -> Result<PathBuf, String> {
    const RELATIVE_EXECUTABLE: &str = "resources/ollama/windows-x86_64/ollama.exe";

    let mut candidates = Vec::new();
    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join(RELATIVE_EXECUTABLE));
    }
    candidates.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(RELATIVE_EXECUTABLE));

    if cfg!(debug_assertions) {
        if let Ok(value) = std::env::var("YUXIN_OLLAMA_RUNTIME_PATH") {
            if let Some(path) = path_from_runtime_hint(&value) {
                candidates.insert(0, path);
            }
        }
        if let Some(path) = executable_from_path() {
            candidates.push(path);
        }
    }

    candidates
        .into_iter()
        .find(|path| path.is_file())
        .ok_or_else(|| "内置 Ollama 运行时未随安装包准备好，请重新构建安装包。".to_owned())
}

#[cfg(not(all(target_os = "windows", target_arch = "x86_64")))]
fn resolve_ollama_executable(_app: &AppHandle) -> Result<PathBuf, String> {
    Err("内置 Ollama 当前只支持 Windows x64。".into())
}

fn choose_loopback_port() -> Result<u16, String> {
    std::net::TcpListener::bind(("127.0.0.1", 0))
        .map_err(|_| "无法为内置 Ollama 分配本机端口。".to_owned())?
        .local_addr()
        .map(|address| address.port())
        .map_err(|_| "无法读取内置 Ollama 本机端口。".to_owned())
}

fn model_directory(app: &AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_data_dir()
        .map_err(|_| "无法确定本地模型存储目录。".to_owned())?
        .join("ollama")
        .join("models");
    fs::create_dir_all(&path).map_err(|_| "无法创建本地模型存储目录。".to_owned())?;
    Ok(path)
}

async fn read_json_response(
    response: reqwest::Response,
    max_bytes: u64,
    too_large_message: &'static str,
    read_error_message: &'static str,
) -> Result<(u16, Value), String> {
    if response
        .content_length()
        .is_some_and(|length| length > max_bytes)
    {
        return Err(too_large_message.into());
    }

    let status = response.status().as_u16();
    let body = response
        .bytes()
        .await
        .map_err(|_| read_error_message.to_owned())?;
    if body.len() as u64 > max_bytes {
        return Err(too_large_message.into());
    }

    Ok((status, serde_json::from_slice(&body).unwrap_or(Value::Null)))
}

fn payload_error(payload: &Value) -> Option<String> {
    payload
        .get("error")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

async fn server_version(base_url: &str) -> Result<String, String> {
    let client = client(OLLAMA_HEALTH_TIMEOUT)?;
    let response = client
        .get(format!("{base_url}/api/version"))
        .header(reqwest::header::ACCEPT, "application/json")
        .send()
        .await
        .map_err(|_| "内置 Ollama 尚未启动。".to_owned())?;
    let (status, payload) = read_json_response(
        response,
        64 * 1024,
        "内置 Ollama 版本响应过大。",
        "读取内置 Ollama 版本失败。",
    )
    .await?;
    if !(200..300).contains(&status) {
        return Err("内置 Ollama 健康检查失败。".into());
    }
    payload
        .get("version")
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .map(|value| value.trim().to_owned())
        .ok_or_else(|| "内置 Ollama 版本响应格式无效。".into())
}

async fn wait_for_server(base_url: &str) -> Result<String, String> {
    let deadline = Instant::now() + OLLAMA_STARTUP_TIMEOUT;
    loop {
        match server_version(base_url).await {
            Ok(version) => return Ok(version),
            Err(error) if Instant::now() < deadline => {
                let _ = error;
                std::thread::sleep(Duration::from_millis(200));
            }
            Err(error) => return Err(error),
        }
    }
}

fn kill_managed_process(managed: &mut ManagedOllamaProcess) {
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;

        // Ollama starts one or more runner children for a loaded model. Kill
        // the exact app-owned process tree so runners cannot outlive the app.
        let pid = managed.child.id().to_string();
        let mut taskkill = Command::new("taskkill");
        taskkill
            .args(["/PID", &pid, "/T", "/F"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x08000000);
        let _ = taskkill.status();
    }
    let _ = managed.child.kill();
    let _ = managed.child.wait();
}

async fn ensure_running(
    app: &AppHandle,
    state: &OllamaRuntimeState,
) -> Result<RuntimeConnection, String> {
    let mut process = state.process.lock().await;
    if let Some(managed) = process.as_mut() {
        let alive = managed
            .child
            .try_wait()
            .map_err(|_| "无法检查内置 Ollama 进程状态。".to_owned())?
            .is_none();
        if alive {
            if server_version(&managed.base_url).await.is_ok() {
                return Ok(RuntimeConnection {
                    base_url: managed.base_url.clone(),
                });
            }
        }
        kill_managed_process(managed);
        *process = None;
    }

    let executable = resolve_ollama_executable(app)?;
    let port = choose_loopback_port()?;
    let host = format!("127.0.0.1:{port}");
    let base_url = format!("http://{host}");
    let models = model_directory(app)?;
    let mut command = Command::new(&executable);
    command
        .arg("serve")
        .current_dir(executable.parent().unwrap_or_else(|| Path::new(".")))
        .env("OLLAMA_HOST", &host)
        .env("OLLAMA_MODELS", &models)
        .env("OLLAMA_NO_CLOUD", "1")
        .env("OLLAMA_KEEP_ALIVE", "5m")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let child = command
        .spawn()
        .map_err(|_| "无法启动内置 Ollama 运行时。".to_owned())?;
    let mut managed = ManagedOllamaProcess {
        child,
        base_url,
        version: String::new(),
    };
    let version = match wait_for_server(&managed.base_url).await {
        Ok(version) => version,
        Err(error) => {
            kill_managed_process(&mut managed);
            return Err(error);
        }
    };
    managed.version = version;
    let connection = RuntimeConnection {
        base_url: managed.base_url.clone(),
    };
    *process = Some(managed);
    Ok(connection)
}

fn safe_model_name(value: &str) -> Result<String, String> {
    let value = value.trim();
    if value.is_empty()
        || value.len() > 160
        || value.contains("..")
        || value.chars().any(|character| character.is_control())
    {
        return Err("本地模型名称无效。".into());
    }
    Ok(value.to_owned())
}

fn model_from_chat_body(body: &str) -> Result<(String, Value), String> {
    if body.len() > MAX_OLLAMA_CHAT_REQUEST_BYTES {
        return Err("聊天请求体过大，已拒绝发送。".into());
    }
    let payload: Value =
        serde_json::from_str(body).map_err(|_| "聊天请求体格式无效，已拒绝发送。".to_owned())?;
    let model = payload
        .get("model")
        .and_then(Value::as_str)
        .ok_or_else(|| "本地模型名称缺失。".to_owned())
        .and_then(safe_model_name)?;
    Ok((model, payload))
}

fn model_matches(payload: &Value, model: &str) -> bool {
    payload
        .get("models")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|entry| {
            entry
                .get("name")
                .or_else(|| entry.get("model"))
                .and_then(Value::as_str)
        })
        .any(|name| name == model || (!model.contains(':') && name == format!("{model}:latest")))
}

async fn list_models(base_url: &str) -> Result<(u16, Value), String> {
    let client = client(OLLAMA_CHAT_TIMEOUT)?;
    let response = client
        .get(format!("{base_url}/api/tags"))
        .header(reqwest::header::ACCEPT, "application/json")
        .send()
        .await
        .map_err(|_| "获取本地 Ollama 模型列表失败。".to_owned())?;
    read_json_response(
        response,
        MAX_OLLAMA_MODEL_LIST_BYTES,
        "本地 Ollama 模型列表响应过大。",
        "读取本地 Ollama 模型列表失败。",
    )
    .await
}

fn emit_pull_line(app: &AppHandle, model: &str, line: &[u8]) -> Result<bool, String> {
    let payload: Value =
        serde_json::from_slice(line).map_err(|_| "本地模型下载进度响应格式无效。".to_owned())?;
    if let Some(error) = payload_error(&payload) {
        return Err(format!("本地模型下载失败：{error}"));
    }
    let status = payload
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("下载中")
        .to_owned();
    let progress = OllamaPullProgress {
        model: model.to_owned(),
        status: status.clone(),
        completed: payload.get("completed").and_then(Value::as_u64),
        total: payload.get("total").and_then(Value::as_u64),
        done: payload
            .get("done")
            .and_then(Value::as_bool)
            .unwrap_or_else(|| status.eq_ignore_ascii_case("success")),
    };
    let done = progress.done;
    let _ = app.emit(OLLAMA_PULL_EVENT, progress);
    Ok(done)
}

async fn pull_model(app: &AppHandle, base_url: &str, model: &str) -> Result<(), String> {
    let client = client(OLLAMA_PULL_TIMEOUT)?;
    let response = client
        .post(format!("{base_url}/api/pull"))
        .header(reqwest::header::ACCEPT, "application/x-ndjson")
        .header(reqwest::header::CONTENT_TYPE, "application/json")
        .body(
            serde_json::to_vec(&json!({ "model": model, "stream": true }))
                .map_err(|_| "本地模型下载请求编码失败。".to_owned())?,
        )
        .send()
        .await
        .map_err(|_| "本地模型下载请求失败，请检查网络连接。".to_owned())?;
    if !response.status().is_success() {
        let (_, payload) = read_json_response(
            response,
            MAX_OLLAMA_CHAT_RESPONSE_BYTES,
            "本地模型下载错误响应过大。",
            "读取本地模型下载错误失败。",
        )
        .await?;
        return Err(payload_error(&payload).unwrap_or_else(|| "本地模型下载失败。".to_owned()));
    }

    let mut response = response;
    let mut buffer = Vec::new();
    while let Some(chunk) = response
        .chunk()
        .await
        .map_err(|_| "读取本地模型下载进度失败。".to_owned())?
    {
        buffer.extend_from_slice(&chunk);
        while let Some(position) = buffer.iter().position(|byte| *byte == b'\n') {
            let line = buffer.drain(..=position).collect::<Vec<_>>();
            let line = line.strip_suffix(&[b'\n']).unwrap_or(&line);
            let line = line.strip_suffix(&[b'\r']).unwrap_or(line);
            if !line.is_empty() && emit_pull_line(app, model, line)? {
                return Ok(());
            }
        }
        if buffer.len() > MAX_OLLAMA_PULL_LINE_BYTES {
            return Err("本地模型下载进度行过大，已拒绝读取。".into());
        }
    }
    if !buffer.is_empty() && emit_pull_line(app, model, &buffer)? {
        return Ok(());
    }
    Err("本地模型下载未返回完成状态。".into())
}

async fn ensure_model(
    app: &AppHandle,
    state: &OllamaRuntimeState,
    connection: &RuntimeConnection,
    model: &str,
) -> Result<(), String> {
    let _pull_guard = state.model_pull.lock().await;
    let (_, payload) = list_models(&connection.base_url).await?;
    if model_matches(&payload, model) {
        return Ok(());
    }
    let _ = app.emit(
        OLLAMA_PULL_EVENT,
        OllamaPullProgress {
            model: model.to_owned(),
            status: "准备下载模型".to_owned(),
            completed: None,
            total: None,
            done: false,
        },
    );
    pull_model(app, &connection.base_url, model).await?;
    let (_, payload) = list_models(&connection.base_url).await?;
    if model_matches(&payload, model) {
        Ok(())
    } else {
        Err("本地模型下载完成，但模型列表中未找到该模型。".into())
    }
}

#[tauri::command]
pub async fn get_bundled_ollama_status(
    app: AppHandle,
    state: State<'_, OllamaRuntimeState>,
) -> Result<OllamaRuntimeStatus, String> {
    let available = resolve_ollama_executable(&app).is_ok();
    let mut process = state.process.lock().await;
    let Some(managed) = process.as_mut() else {
        return Ok(OllamaRuntimeStatus {
            available,
            running: false,
            version: None,
        });
    };
    let running = managed
        .child
        .try_wait()
        .map_err(|_| "无法检查内置 Ollama 进程状态。".to_owned())?
        .is_none();
    if !running {
        kill_managed_process(managed);
        let version = None;
        *process = None;
        return Ok(OllamaRuntimeStatus {
            available,
            running: false,
            version,
        });
    }
    Ok(OllamaRuntimeStatus {
        available,
        running,
        version: Some(managed.version.clone()),
    })
}

#[tauri::command]
pub async fn fetch_bundled_ollama_models(
    app: AppHandle,
    state: State<'_, OllamaRuntimeState>,
) -> Result<OllamaModelListResponse, String> {
    let connection = ensure_running(&app, state.inner()).await?;
    let (status, payload) = list_models(&connection.base_url).await?;
    Ok(OllamaModelListResponse { status, payload })
}

#[tauri::command]
pub async fn fetch_bundled_ollama_chat(
    app: AppHandle,
    state: State<'_, OllamaRuntimeState>,
    body: String,
) -> Result<OllamaChatResponse, String> {
    let (model, mut payload) = model_from_chat_body(&body)?;
    let connection = ensure_running(&app, state.inner()).await?;
    ensure_model(&app, state.inner(), &connection, &model).await?;
    if let Some(object) = payload.as_object_mut() {
        object.insert("stream".to_owned(), Value::Bool(false));
    }
    let body = serde_json::to_vec(&payload).map_err(|_| "本地聊天请求编码失败。".to_owned())?;
    let client = client(OLLAMA_CHAT_TIMEOUT)?;
    let response = client
        .post(format!("{}/v1/chat/completions", connection.base_url))
        .header(reqwest::header::ACCEPT, "application/json")
        .header(reqwest::header::CONTENT_TYPE, "application/json")
        .body(body)
        .send()
        .await
        .map_err(|_| "发送本地 Ollama 聊天请求失败。".to_owned())?;
    let (status, payload) = read_json_response(
        response,
        MAX_OLLAMA_CHAT_RESPONSE_BYTES,
        "本地 Ollama 聊天响应过大。",
        "读取本地 Ollama 聊天响应失败。",
    )
    .await?;
    Ok(OllamaChatResponse { status, payload })
}

pub fn stop(state: &OllamaRuntimeState) {
    let mut process = state.process.blocking_lock();
    if let Some(mut managed) = process.take() {
        kill_managed_process(&mut managed);
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::{model_matches, safe_model_name};

    #[test]
    fn accepts_normal_ollama_model_references_and_rejects_controls() {
        assert_eq!(safe_model_name("qwen3:0.6b").unwrap(), "qwen3:0.6b");
        assert_eq!(
            safe_model_name("hf.co/example/model:latest").unwrap(),
            "hf.co/example/model:latest"
        );
        assert!(safe_model_name("qwen3\n0.6b").is_err());
        assert!(safe_model_name("../model").is_err());
    }

    #[test]
    fn matches_both_ollama_model_list_field_names() {
        let payload = json!({
            "models": [
                { "name": "qwen3:0.6b" },
                { "model": "gemma3:1b" }
            ]
        });
        assert!(model_matches(&payload, "qwen3:0.6b"));
        assert!(model_matches(&payload, "gemma3:1b"));
        assert!(model_matches(
            &json!({ "models": [{ "name": "qwen3:latest" }] }),
            "qwen3"
        ));
        assert!(!model_matches(&payload, "missing:latest"));
    }
}
