use std::time::Duration;

use serde::Serialize;
use tauri::AppHandle;

const COMPANION_PROVIDER_REQUEST_TIMEOUT: Duration = Duration::from_secs(15);
const MAX_COMPANION_PROVIDER_MODEL_LIST_BYTES: u64 = 4 * 1024 * 1024;
const MAX_COMPANION_PROVIDER_CHAT_REQUEST_BYTES: usize = 2 * 1024 * 1024;
const MAX_COMPANION_PROVIDER_CHAT_RESPONSE_BYTES: u64 = 4 * 1024 * 1024;

#[derive(Debug, Serialize)]
pub struct CompanionProviderModelListResponse {
    pub status: u16,
    pub payload: serde_json::Value,
}

#[derive(Debug, Serialize)]
pub struct CompanionProviderChatResponse {
    pub status: u16,
    pub payload: serde_json::Value,
}

fn is_loopback_hostname(hostname: &str) -> bool {
    let normalized = hostname
        .trim_start_matches('[')
        .trim_end_matches(']')
        .to_ascii_lowercase();
    matches!(normalized.as_str(), "localhost" | "127.0.0.1" | "::1")
}

fn validate_model_list_request(
    protocol: &str,
    url: &str,
    credential: &str,
) -> Result<reqwest::Url, String> {
    if !matches!(protocol, "openai-compatible" | "gemini-native") {
        return Err("当前 Provider 不支持获取模型列表。".into());
    }
    if credential.trim().is_empty() {
        return Err("远程 Provider 凭据未配置。".into());
    }

    let parsed = reqwest::Url::parse(url.trim()).map_err(|_| "模型列表地址无效。".to_owned())?;
    let scheme = parsed.scheme();
    let hostname = parsed.host_str().unwrap_or_default();
    if !matches!(scheme, "http" | "https")
        || hostname.is_empty()
        || parsed.username() != ""
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
        || (scheme == "http" && !is_loopback_hostname(hostname))
    {
        return Err("模型列表地址无效；远程地址必须使用 HTTPS，且不能包含凭据或查询参数。".into());
    }

    let path = parsed.path().trim_end_matches('/');
    if !path.ends_with("/models") {
        return Err("模型列表地址必须指向 /models。".into());
    }

    Ok(parsed)
}

fn validate_chat_request(
    protocol: &str,
    url: &str,
    credential: &str,
    body: &str,
) -> Result<reqwest::Url, String> {
    if !matches!(protocol, "openai-compatible" | "gemini-native") {
        return Err("当前 Provider 不支持远程聊天请求。".into());
    }
    if credential.trim().is_empty() {
        return Err("远程 Provider 凭据未配置。".into());
    }
    if body.len() > MAX_COMPANION_PROVIDER_CHAT_REQUEST_BYTES {
        return Err("聊天请求体过大，已拒绝发送。".into());
    }
    if serde_json::from_str::<serde_json::Value>(body).is_err() {
        return Err("聊天请求体格式无效，已拒绝发送。".into());
    }

    let parsed = reqwest::Url::parse(url.trim()).map_err(|_| "聊天地址无效。".to_owned())?;
    let scheme = parsed.scheme();
    let hostname = parsed.host_str().unwrap_or_default();
    if !matches!(scheme, "http" | "https")
        || hostname.is_empty()
        || parsed.username() != ""
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
        || (scheme == "http" && !is_loopback_hostname(hostname))
    {
        return Err("聊天地址无效；远程地址必须使用 HTTPS，且不能包含凭据或查询参数。".into());
    }

    let path = parsed.path().trim_end_matches('/');
    let valid_path = if protocol == "gemini-native" {
        path.ends_with(":generateContent")
    } else {
        path.ends_with("/chat/completions")
    };
    if !valid_path {
        return Err("聊天地址与当前 Provider 协议不匹配。".into());
    }

    Ok(parsed)
}

fn apply_provider_auth(
    request: reqwest::RequestBuilder,
    protocol: &str,
    credential: &str,
) -> reqwest::RequestBuilder {
    if protocol == "gemini-native" {
        request.header("x-goog-api-key", credential.trim())
    } else {
        request.bearer_auth(credential.trim())
    }
}

struct ProviderJsonResponse {
    status: u16,
    payload: serde_json::Value,
}

async fn read_provider_json_response(
    response: reqwest::Response,
    max_bytes: u64,
    too_large_message: &'static str,
    read_error_message: &'static str,
) -> Result<ProviderJsonResponse, String> {
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

    Ok(ProviderJsonResponse {
        status,
        payload: serde_json::from_slice(&body).unwrap_or(serde_json::Value::Null),
    })
}

#[tauri::command]
pub async fn fetch_companion_provider_models(
    protocol: String,
    url: String,
    credential: String,
) -> Result<CompanionProviderModelListResponse, String> {
    let url = validate_model_list_request(&protocol, &url, &credential)?;
    let client = reqwest::Client::builder()
        .timeout(COMPANION_PROVIDER_REQUEST_TIMEOUT)
        .build()
        .map_err(|_| "模型列表网络客户端初始化失败。".to_owned())?;

    let request = apply_provider_auth(
        client
            .get(url)
            .header(reqwest::header::ACCEPT, "application/json"),
        &protocol,
        &credential,
    );
    let response = request
        .send()
        .await
        .map_err(|_| "获取上游模型列表失败，请检查网络或 Endpoint。".to_owned())?;

    let response = read_provider_json_response(
        response,
        MAX_COMPANION_PROVIDER_MODEL_LIST_BYTES,
        "上游模型列表响应过大，已拒绝读取。",
        "读取上游模型列表失败。",
    )
    .await?;
    Ok(CompanionProviderModelListResponse {
        status: response.status,
        payload: response.payload,
    })
}

#[tauri::command]
pub async fn fetch_companion_provider_chat(
    protocol: String,
    url: String,
    credential: String,
    body: String,
) -> Result<CompanionProviderChatResponse, String> {
    let url = validate_chat_request(&protocol, &url, &credential, &body)?;
    let client = reqwest::Client::builder()
        .timeout(COMPANION_PROVIDER_REQUEST_TIMEOUT)
        .build()
        .map_err(|_| "聊天网络客户端初始化失败。".to_owned())?;

    let request = apply_provider_auth(
        client
            .post(url)
            .header(reqwest::header::ACCEPT, "application/json")
            .header(reqwest::header::CONTENT_TYPE, "application/json")
            .body(body),
        &protocol,
        &credential,
    );
    let response = request
        .send()
        .await
        .map_err(|_| "发送上游聊天请求失败，请检查网络或 Endpoint。".to_owned())?;
    let response = read_provider_json_response(
        response,
        MAX_COMPANION_PROVIDER_CHAT_RESPONSE_BYTES,
        "上游聊天响应过大，已拒绝读取。",
        "读取上游聊天响应失败。",
    )
    .await?;
    Ok(CompanionProviderChatResponse {
        status: response.status,
        payload: response.payload,
    })
}

fn keyring_service_for_identifier(identifier: &str) -> String {
    format!("{identifier}.companion-provider")
}

fn validate_reference(value: &str, name: &str, max_len: usize) -> Result<(), String> {
    let trimmed = value.trim();
    let valid = !trimmed.is_empty()
        && trimmed.len() <= max_len
        && trimmed
            .chars()
            .next()
            .is_some_and(|character| character.is_ascii_lowercase() || character.is_ascii_digit())
        && trimmed.chars().all(|character| {
            character.is_ascii_lowercase()
                || character.is_ascii_digit()
                || matches!(character, '.' | '_' | '-')
        });

    if valid {
        Ok(())
    } else {
        Err(format!(
            "{name} 无效，只能包含小写字母、数字、点、下划线和连字符。"
        ))
    }
}

fn keyring_account(credential_ref: &str) -> Result<String, String> {
    validate_reference(credential_ref, "credentialRef", 96)?;
    Ok(credential_ref.trim().to_owned())
}

fn keyring_entry(
    app: &AppHandle,
    profile_id: &str,
    credential_ref: &str,
    operation: &str,
) -> Result<keyring::Entry, String> {
    validate_reference(profile_id, "Profile ID", 64)?;
    let account = keyring_account(credential_ref)?;
    let service = keyring_service_for_identifier(&app.config().identifier);
    crate::record_credential_audit(operation, &service, &account);
    keyring::Entry::new(&service, &account).map_err(|error| format!("系统安全存储不可用：{error}"))
}

#[tauri::command]
pub fn get_companion_provider_credential(
    app: AppHandle,
    profile_id: String,
    credential_ref: String,
) -> Result<Option<String>, String> {
    let entry = keyring_entry(&app, &profile_id, &credential_ref, "get")?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(format!("系统安全存储不可用：{error}")),
    }
}

#[tauri::command]
pub fn set_companion_provider_credential(
    app: AppHandle,
    profile_id: String,
    credential_ref: String,
    secret: String,
) -> Result<(), String> {
    let value = secret.trim();
    if value.is_empty() {
        return Err("凭据不能为空。".into());
    }

    let entry = keyring_entry(&app, &profile_id, &credential_ref, "set")?;
    entry
        .set_password(value)
        .map_err(|error| format!("系统安全存储不可用：{error}"))
}

#[tauri::command]
pub fn clear_companion_provider_credential(
    app: AppHandle,
    profile_id: String,
    credential_ref: String,
) -> Result<(), String> {
    let entry = keyring_entry(&app, &profile_id, &credential_ref, "clear")?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(format!("系统安全存储不可用：{error}")),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        keyring_service_for_identifier, validate_chat_request, validate_model_list_request,
        validate_reference, MAX_COMPANION_PROVIDER_CHAT_REQUEST_BYTES,
    };

    #[test]
    fn accepts_https_model_list_urls_and_loopback_http() {
        assert_eq!(
            validate_model_list_request(
                "openai-compatible",
                "https://models.example/v1/models",
                "test-secret",
            )
            .expect("HTTPS model URL should be accepted")
            .as_str(),
            "https://models.example/v1/models",
        );
        assert!(validate_model_list_request(
            "openai-compatible",
            "http://127.0.0.1:8317/v1/models",
            "test-secret",
        )
        .is_ok());
    }

    #[test]
    fn rejects_unsafe_model_list_urls_without_echoing_credentials() {
        for url in [
            "http://models.example/v1/models",
            "https://models.example/v1/models?key=secret",
            "https://user:secret@models.example/v1/models",
            "https://models.example/v1/chat/completions",
        ] {
            assert!(validate_model_list_request("openai-compatible", url, "test-secret").is_err());
        }
        let missing_credential = validate_model_list_request(
            "openai-compatible",
            "https://models.example/v1/models",
            "",
        );
        assert!(missing_credential.is_err());
        assert!(!missing_credential
            .expect_err("empty credentials should be rejected")
            .contains("test-secret"));
    }

    #[test]
    fn accepts_protocol_specific_chat_urls_and_json_bodies() {
        assert_eq!(
            validate_chat_request(
                "openai-compatible",
                "https://api.example/v1/chat/completions",
                "test-secret",
                r#"{"model":"demo","messages":[]}"#,
            )
            .expect("OpenAI-compatible chat URL should be accepted")
            .as_str(),
            "https://api.example/v1/chat/completions",
        );
        assert!(validate_chat_request(
            "gemini-native",
            "https://generativelanguage.googleapis.com/v1beta/models/demo:generateContent",
            "test-secret",
            r#"{"contents":[]}"#,
        )
        .is_ok());
        assert!(validate_chat_request(
            "openai-compatible",
            "http://127.0.0.1:8317/v1/chat/completions",
            "test-secret",
            r#"{}"#,
        )
        .is_ok());
    }

    #[test]
    fn rejects_chat_requests_before_network_without_echoing_secrets() {
        for (protocol, url, body) in [
            (
                "openai-compatible",
                "http://remote.example/v1/chat/completions",
                r#"{}"#,
            ),
            (
                "openai-compatible",
                "https://api.example/v1/models",
                r#"{}"#,
            ),
            (
                "gemini-native",
                "https://api.example/v1/chat/completions",
                r#"{}"#,
            ),
            (
                "openai-compatible",
                "https://user:secret@api.example/v1/chat/completions",
                r#"{}"#,
            ),
        ] {
            assert!(validate_chat_request(protocol, url, "test-secret", body).is_err());
        }
        let invalid_json = validate_chat_request(
            "openai-compatible",
            "https://api.example/v1/chat/completions",
            "test-secret",
            "not-json",
        );
        assert!(invalid_json.is_err());
        let too_large = validate_chat_request(
            "openai-compatible",
            "https://api.example/v1/chat/completions",
            "test-secret",
            &format!(
                "{{\"padding\":\"{}\"}}",
                "x".repeat(MAX_COMPANION_PROVIDER_CHAT_REQUEST_BYTES)
            ),
        );
        assert!(too_large.is_err());
        let missing_credential = validate_chat_request(
            "openai-compatible",
            "https://api.example/v1/chat/completions",
            "test-secret",
            r#"{}"#,
        )
        .expect("sentinel credential should be accepted");
        assert_eq!(
            missing_credential.as_str(),
            "https://api.example/v1/chat/completions"
        );
        let missing_credential = validate_chat_request(
            "openai-compatible",
            "https://api.example/v1/chat/completions",
            "",
            r#"{}"#,
        );
        assert!(missing_credential.is_err());
        assert!(!missing_credential
            .expect_err("empty credentials should be rejected")
            .contains("test-secret"));
    }

    #[test]
    fn preserves_the_formal_keyring_service_name() {
        assert_eq!(
            keyring_service_for_identifier("com.yuxin.desktop"),
            "com.yuxin.desktop.companion-provider",
        );
    }

    #[test]
    fn isolates_each_evidence_identifier_without_touching_keyring() {
        let formal = keyring_service_for_identifier("com.yuxin.desktop");
        let first = keyring_service_for_identifier(
            "com.yuxin.desktop.tauri-chat-evidence-tauri-chat-root-fix-20260825-120000",
        );
        let second = keyring_service_for_identifier(
            "com.yuxin.desktop.tauri-chat-evidence-tauri-chat-root-fix-20260825-120001",
        );

        assert_ne!(formal, first);
        assert_ne!(first, second);
    }

    #[test]
    fn accepts_stable_profile_and_credential_references() {
        assert!(validate_reference("google-gemini", "Profile ID", 64).is_ok());
        assert!(validate_reference("custom-gemini", "credentialRef", 96).is_ok());
        assert!(validate_reference("openai.default", "credentialRef", 96).is_ok());
    }

    #[test]
    fn rejects_path_like_or_secret_bearing_references() {
        assert!(validate_reference("../provider", "Profile ID", 64).is_err());
        assert!(validate_reference("Provider", "Profile ID", 64).is_err());
        assert!(validate_reference("provider:secret", "credentialRef", 96).is_err());
        assert!(validate_reference("", "credentialRef", 96).is_err());
    }
}
