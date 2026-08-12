const KEYRING_SERVICE: &str = "com.yuxin.desktop.companion-provider";

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

fn keyring_entry(profile_id: &str, credential_ref: &str) -> Result<keyring::Entry, String> {
    validate_reference(profile_id, "Profile ID", 64)?;
    let account = keyring_account(credential_ref)?;
    keyring::Entry::new(KEYRING_SERVICE, &account)
        .map_err(|error| format!("系统安全存储不可用：{error}"))
}

#[tauri::command]
pub fn get_companion_provider_credential(
    profile_id: String,
    credential_ref: String,
) -> Result<Option<String>, String> {
    let entry = keyring_entry(&profile_id, &credential_ref)?;
    match entry.get_password() {
        Ok(value) => Ok(Some(value)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(error) => Err(format!("系统安全存储不可用：{error}")),
    }
}

#[tauri::command]
pub fn set_companion_provider_credential(
    profile_id: String,
    credential_ref: String,
    secret: String,
) -> Result<(), String> {
    let value = secret.trim();
    if value.is_empty() {
        return Err("凭据不能为空。".into());
    }

    let entry = keyring_entry(&profile_id, &credential_ref)?;
    entry
        .set_password(value)
        .map_err(|error| format!("系统安全存储不可用：{error}"))
}

#[tauri::command]
pub fn clear_companion_provider_credential(
    profile_id: String,
    credential_ref: String,
) -> Result<(), String> {
    let entry = keyring_entry(&profile_id, &credential_ref)?;
    match entry.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(error) => Err(format!("系统安全存储不可用：{error}")),
    }
}

#[cfg(test)]
mod tests {
    use super::validate_reference;

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
