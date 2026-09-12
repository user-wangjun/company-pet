use std::{fs::OpenOptions, io::Write, path::PathBuf, sync::OnceLock, time::Instant};

use serde::{Deserialize, Serialize};

mod companion_provider;
mod desktop_icons;
mod installer_update;
mod ollama_runtime;
mod pet_plugins;
mod startup_guard;
mod task_notifications;
mod task_scheduler;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager,
};

const MENU_SHOW: &str = "show-yuxin";
const MENU_OPEN_PLATFORM: &str = "open-platform-yuxin";
const MENU_NEW_TASK: &str = "new-task-yuxin";
const MENU_TODAY_TASKS: &str = "today-tasks-yuxin";
const MENU_REMINDERS: &str = "reminders-yuxin";
const MENU_TOGGLE_SOUND: &str = "toggle-sound-yuxin";
const MENU_CHECK_UPDATE: &str = "check-update-yuxin";
const MENU_QUIT: &str = "quit-yuxin";
const OPEN_PLATFORM_EVENT: &str = "open-platform";
const TOGGLE_SOUND_EVENT: &str = "toggle-sound";
const CHAT_OBSERVATION_PREFIX: &str = "chat_observation:";
const SAFE_SELF_TEST_INTERACTION_EVENTS: &[&str] = &[
    "companion_chat_open",
    "companion_chat_retry",
    "companion_chat_stop",
    "companion_provider_key_cleared",
    "companion_provider_saved",
    "platform_pet_selected",
];

static CHAT_OBSERVATION_CLOCK: OnceLock<Instant> = OnceLock::new();

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum ChatObservationEvent {
    ChatRequestStarted,
    ChatStopClicked,
    ChatTurnCancelled,
    ChatFallbackStarted,
    ChatResultCommitted,
    ChatResultDiscarded,
    ProviderListenerAttached,
    ProviderListenerDetached,
    ProviderSyncNotified,
    ProviderHydrated,
    PetSwitched,
    ConfirmationStarted,
    ConfirmationCommitted,
    DomainWriteCommitted,
    MemorySaveCommitted,
    MemoryForgetCommitted,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct ChatObservationInput {
    window_label: String,
    case_id: Option<String>,
    event: ChatObservationEvent,
    http_status: Option<u16>,
    listener_count: Option<u32>,
    call_count: Option<u32>,
    commit_count: Option<u32>,
    write_count: Option<u32>,
    cancelled: Option<bool>,
    fallback: Option<bool>,
    late_discarded: Option<bool>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ChatObservationRecord {
    run_id_hash: String,
    process_id: u32,
    window_label: String,
    case_id: String,
    event: ChatObservationEvent,
    monotonic_ms: u128,
    #[serde(skip_serializing_if = "Option::is_none")]
    http_status: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    listener_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    call_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    commit_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    write_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    cancelled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    fallback: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    late_discarded: Option<bool>,
}

fn is_short_hash(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    (8..=64).contains(&hex.len()) && hex.chars().all(|character| character.is_ascii_hexdigit())
}

fn build_chat_observation_record(
    payload: &str,
    run_id_hash: &str,
    monotonic_ms: u128,
) -> Result<String, String> {
    if !is_short_hash(run_id_hash) {
        return Err("验收运行标识哈希无效。".into());
    }

    let input: ChatObservationInput =
        serde_json::from_str(payload).map_err(|_| "验收观测事件格式无效。".to_owned())?;
    if !matches!(input.window_label.as_str(), "main" | "platform") {
        return Err("验收观测窗口无效。".into());
    }
    let case_id = input
        .case_id
        .or_else(|| std::env::var("XIAOJU_SELF_TEST_CASE").ok())
        .ok_or_else(|| "验收观测 case 缺失。".to_owned())?;
    if !matches!(
        case_id.as_str(),
        "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H"
    ) {
        return Err("验收观测 case 无效。".into());
    }
    if input
        .http_status
        .is_some_and(|status| !(100..=599).contains(&status))
    {
        return Err("验收观测 HTTP 状态无效。".into());
    }

    serde_json::to_string(&ChatObservationRecord {
        run_id_hash: run_id_hash.to_owned(),
        process_id: std::process::id(),
        window_label: input.window_label,
        case_id,
        event: input.event,
        monotonic_ms,
        http_status: input.http_status,
        listener_count: input.listener_count,
        call_count: input.call_count,
        commit_count: input.commit_count,
        write_count: input.write_count,
        cancelled: input.cancelled,
        fallback: input.fallback,
        late_discarded: input.late_discarded,
    })
    .map_err(|_| "验收观测事件无法序列化。".into())
}

fn append_self_test_line(path: &str, line: &str) -> Result<(), String> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| error.to_string())?;

    writeln!(file, "{line}").map_err(|error| error.to_string())
}

fn is_safe_self_test_interaction(event: &str) -> bool {
    SAFE_SELF_TEST_INTERACTION_EVENTS.contains(&event)
}

pub(crate) fn record_credential_audit(operation: &str, service: &str, account: &str) {
    let Ok(path) = std::env::var("XIAOJU_SELF_TEST_LOG") else {
        return;
    };
    let Ok(run_id_hash) = std::env::var("XIAOJU_SELF_TEST_RUN_HASH") else {
        return;
    };
    if !is_short_hash(&run_id_hash) {
        return;
    }
    let record = serde_json::json!({
        "runIdHash": run_id_hash,
        "processId": std::process::id(),
        "operation": operation,
        "service": service,
        "account": account,
    });
    let _ = append_self_test_line(&path, &format!("credential_audit:{record}"));
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct OpenPlatformPayload {
    reset_pet_position: bool,
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct TaskSchedulerWakeupPayload {
    care_kind: Option<String>,
}

#[tauri::command]
fn record_interaction(event: String) -> Result<(), String> {
    let Ok(path) = std::env::var("XIAOJU_SELF_TEST_LOG") else {
        return Ok(());
    };

    let line = if let Some(payload) = event.strip_prefix(CHAT_OBSERVATION_PREFIX) {
        let run_id_hash = std::env::var("XIAOJU_SELF_TEST_RUN_HASH")
            .map_err(|_| "验收运行标识哈希缺失。".to_owned())?;
        let monotonic_ms = CHAT_OBSERVATION_CLOCK
            .get_or_init(Instant::now)
            .elapsed()
            .as_millis();
        build_chat_observation_record(payload, &run_id_hash, monotonic_ms)?
    } else if is_safe_self_test_interaction(&event) {
        event
    } else {
        // Self-test evidence is intentionally narrower than the legacy
        // interaction telemetry surface. Unknown strings may contain debug
        // payloads, correlation data, or user text, so they must never reach
        // the run-owned evidence file.
        return Ok(());
    };

    append_self_test_line(&path, &line)
}

#[cfg(test)]
mod tests {
    use super::{build_chat_observation_record, is_safe_self_test_interaction};

    #[test]
    fn accepts_only_fixed_observation_fields_and_never_logs_hostile_sentinel() {
        let payload = r#"{
            "windowLabel":"main",
            "caseId":"B",
            "event":"chat_result_committed",
            "callCount":1,
            "commitCount":1
        }"#;
        let line = build_chat_observation_record(payload, "sha256:0123456789abcdef", 42)
            .expect("fixed observation should be accepted");
        assert!(line.contains("chat_result_committed"));
        assert!(!line.contains("PROMPT_HOSTILE_SENTINEL"));

        let hostile = r#"{
            "windowLabel":"main",
            "caseId":"B",
            "event":"chat_result_committed",
            "prompt":"PROMPT_HOSTILE_SENTINEL"
        }"#;
        assert!(build_chat_observation_record(hostile, "sha256:0123456789abcdef", 43).is_err());
    }

    #[test]
    fn rejects_unknown_event_window_case_and_run_hash() {
        let unknown_event = r#"{"windowLabel":"main","caseId":"B","event":"user_text"}"#;
        assert!(
            build_chat_observation_record(unknown_event, "sha256:0123456789abcdef", 1).is_err()
        );

        let unknown_window =
            r#"{"windowLabel":"unknown","caseId":"B","event":"chat_result_committed"}"#;
        assert!(
            build_chat_observation_record(unknown_window, "sha256:0123456789abcdef", 1).is_err()
        );

        let unknown_case = r#"{"windowLabel":"main","caseId":"X","event":"chat_result_committed"}"#;
        assert!(build_chat_observation_record(unknown_case, "sha256:0123456789abcdef", 1).is_err());

        let invalid_hash = r#"{"windowLabel":"main","caseId":"B","event":"chat_result_committed"}"#;
        assert!(build_chat_observation_record(invalid_hash, "the-real-run-id", 1).is_err());
    }

    #[test]
    fn drops_legacy_debug_strings_and_hostile_sentinels_from_self_test_logs() {
        assert!(is_safe_self_test_interaction("companion_chat_open"));
        assert!(is_safe_self_test_interaction("platform_pet_selected"));
        assert!(!is_safe_self_test_interaction("app_ready"));
        assert!(!is_safe_self_test_interaction(
            "settings_trace:client_command_emit:{\"prompt\":\"PROMPT_HOSTILE_SENTINEL\"}"
        ));
    }
}

fn emit_open_platform(app: &tauri::AppHandle, reset_pet_position: bool) {
    let _ = app.emit(
        OPEN_PLATFORM_EVENT,
        OpenPlatformPayload { reset_pet_position },
    );
}

fn show_window(app: &tauri::AppHandle, label: &str) {
    if let Some(window) = app.get_webview_window(label) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn show_platform(app: &tauri::AppHandle, reset_pet_position: bool) {
    show_window(app, "platform");
    emit_open_platform(app, reset_pet_position);
}

fn setup_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let new_task = MenuItem::with_id(app, MENU_NEW_TASK, "新建待办", true, None::<&str>)?;
    let today_tasks = MenuItem::with_id(app, MENU_TODAY_TASKS, "查看今日待办", true, None::<&str>)?;
    let reminders = MenuItem::with_id(app, MENU_REMINDERS, "查看全部提醒", true, None::<&str>)?;
    let open_platform = MenuItem::with_id(app, MENU_OPEN_PLATFORM, "打开平台", true, None::<&str>)?;
    let show = MenuItem::with_id(app, MENU_SHOW, "隐藏愈心桌宠", true, None::<&str>)?;
    let toggle_sound = MenuItem::with_id(
        app,
        MENU_TOGGLE_SOUND,
        "打开声音（需谨慎）",
        true,
        None::<&str>,
    )?;
    let check_update = MenuItem::with_id(app, MENU_CHECK_UPDATE, "检查更新", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, MENU_QUIT, "退出", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[
            &new_task,
            &today_tasks,
            &reminders,
            &open_platform,
            &show,
            &toggle_sound,
            &check_update,
            &quit,
        ],
    )?;

    let show_item_menu = show.clone();
    let show_item_tray = show.clone();
    let toggle_sound_item = toggle_sound.clone();

    if let Some(icon) = app.default_window_icon().cloned() {
        TrayIconBuilder::with_id("yuxin-tray")
            .tooltip("愈心桌宠")
            .icon(icon)
            .menu(&menu)
            .show_menu_on_left_click(false)
            .on_menu_event(move |app, event| match event.id().as_ref() {
                MENU_NEW_TASK => {
                    show_platform(app, false);
                    let _ = app.emit("open-task-quick-create", ());
                }
                MENU_TODAY_TASKS | MENU_REMINDERS => {
                    show_platform(app, false);
                    let event_name = if event.id().as_ref() == MENU_TODAY_TASKS {
                        "open-task-today"
                    } else {
                        "open-task-reminders"
                    };
                    let _ = app.emit(event_name, ());
                }
                MENU_OPEN_PLATFORM => {
                    show_platform(app, false);
                }
                MENU_SHOW => {
                    if let Some(window) = app.get_webview_window("main") {
                        if let Ok(visible) = window.is_visible() {
                            let new_text = if visible {
                                let _ = window.hide();
                                "显示愈心桌宠"
                            } else {
                                let _ = window.show();
                                let _ = window.unminimize();
                                let _ = window.set_focus();
                                "隐藏愈心桌宠"
                            };
                            let _ = show_item_menu.set_text(new_text);
                        }
                    }
                }
                MENU_TOGGLE_SOUND => {
                    let _ = app.emit(TOGGLE_SOUND_EVENT, ());
                    // Toggle the menu label based on current text
                    if let Ok(text) = toggle_sound_item.text() {
                        let new_text = if text.contains("打开") {
                            "关闭声音"
                        } else {
                            "打开声音（需谨慎）"
                        };
                        let _ = toggle_sound_item.set_text(new_text);
                    }
                }
                MENU_CHECK_UPDATE => {
                    let _ = app.emit("check-update", ());
                }
                MENU_QUIT => app.exit(0),
                _ => {}
            })
            .on_tray_icon_event(move |tray, event| {
                if let TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                }
                | TrayIconEvent::DoubleClick {
                    button: MouseButton::Left,
                    ..
                } = event
                {
                    let app = tray.app_handle();
                    show_window(&app, "main");
                    show_platform(&app, false);
                    let _ = show_item_tray.set_text("隐藏愈心桌宠");
                }
            })
            .build(app)?;
    }

    Ok(())
}

fn setup_self_test_windows(
    app: &tauri::App,
    self_test: &startup_guard::ValidatedSelfTest,
) -> tauri::Result<()> {
    for config in &self_test.window_configs {
        tauri::WebviewWindowBuilder::from_config(app.handle(), config)?
            // Both windows must share one isolated WebView profile so the
            // ordinary non-secret settings store remains authoritative across
            // the main/platform sync seam. The app identifier still keeps the
            // whole profile isolated from the formal application namespace.
            .data_directory(self_test.data_root.clone())
            .build()?;
    }
    Ok(())
}

fn runtime_config_path() -> Result<Option<PathBuf>, String> {
    let mut path = None;
    let mut arguments = std::env::args().skip(1);
    while let Some(argument) = arguments.next() {
        if let Some(value) = argument.strip_prefix("--config=") {
            if value.is_empty() {
                return Err("--config 路径缺失。".into());
            }
            if path.replace(PathBuf::from(value)).is_some() {
                return Err("--config 只能指定一次。".into());
            }
        } else if argument == "--config" {
            let value = arguments
                .next()
                .ok_or_else(|| "--config 路径缺失。".to_owned())?;
            if value.is_empty() || path.replace(PathBuf::from(value)).is_some() {
                return Err("--config 只能指定一次且路径不能为空。".into());
            }
        }
    }
    Ok(path)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // `Builder::build` creates every config window whose `create` flag is
    // true. Validate the final merged context before constructing the builder
    // so a malformed self-test cannot briefly create a formal WebView first.
    let mut context = tauri::generate_context!();
    match runtime_config_path() {
        Ok(Some(path)) => {
            let config_text = match std::fs::read_to_string(&path) {
                Ok(value) => value,
                Err(error) => {
                    eprintln!("拒绝启动验收实例：无法读取 --config：{error}");
                    return;
                }
            };
            let config = match serde_json::from_str::<tauri::utils::config::Config>(&config_text) {
                Ok(value) => value,
                Err(error) => {
                    eprintln!("拒绝启动验收实例：--config 不是有效 Tauri 配置：{error}");
                    return;
                }
            };
            *context.config_mut() = config;
        }
        Ok(None) => {}
        Err(error) => {
            eprintln!("拒绝启动验收实例：{error}");
            return;
        }
    }
    let startup_mode = match startup_guard::validate_startup_config(
        context.config(),
        &startup_guard::collect_self_test_environment(),
    ) {
        Ok(mode) => mode,
        Err(error) => {
            eprintln!("拒绝启动验收实例：{error}");
            return;
        }
    };
    let validated_self_test = match startup_mode {
        startup_guard::StartupMode::Normal => None,
        startup_guard::StartupMode::SelfTest(config) => Some(config),
    };

    let app = tauri::Builder::default()
        .register_uri_scheme_protocol("pet-plugin", |context, request| pet_plugins::serve(context.app_handle(), request))
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            if let Some(action) = args
                .iter()
                .find_map(|argument| task_notifications::parse_activation(argument))
            {
                let _ = app.emit("task-notification-action", action);
            } else if args
                .iter()
                .any(|argument| argument == "--task-reminder-wakeup")
            {
                let _ = app.emit(
                    "task-scheduler-wakeup",
                    TaskSchedulerWakeupPayload {
                        care_kind: task_scheduler::task_scheduler_wakeup_kind_from_args(&args),
                    },
                );
            } else {
                show_window(app, "main");
                show_platform(app, false);
            }
        }))
        .plugin(tauri_plugin_deep_link::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init())
        .manage(ollama_runtime::OllamaRuntimeState::default())
        .invoke_handler(tauri::generate_handler![
            record_interaction,
            pet_plugins::list_pet_plugins,
            pet_plugins::open_pet_plugins_folder,
            companion_provider::get_companion_provider_credential,
            companion_provider::set_companion_provider_credential,
            companion_provider::clear_companion_provider_credential,
            companion_provider::fetch_companion_provider_models,
            companion_provider::fetch_companion_provider_chat,
            ollama_runtime::get_bundled_ollama_status,
            ollama_runtime::fetch_bundled_ollama_models,
            ollama_runtime::fetch_bundled_ollama_chat,
            installer_update::download_and_open_installer,
            desktop_icons::get_desktop_icons,
            desktop_icons::is_point_on_desktop,
            task_scheduler::sync_task_schedules,
            task_scheduler::is_task_scheduler_wakeup,
            task_scheduler::get_task_scheduler_wakeup_kind,
            task_notifications::show_task_notification,
            task_notifications::show_care_notification,
            task_notifications::show_task_summary_notification,
            task_notifications::get_initial_task_notification_actions,
            task_notifications::clear_task_notification
        ])
        .setup(move |app| {
            if let Some(self_test) = validated_self_test.as_ref() {
                setup_self_test_windows(app, self_test)?;
            }
            setup_tray(app)?;
            Ok(())
        })
        .build(context)
        .expect("error while building tauri application");

    app.run(|app, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(state) = app.try_state::<ollama_runtime::OllamaRuntimeState>() {
                ollama_runtime::stop(state.inner());
            }
        }
    });
}
