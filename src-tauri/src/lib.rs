use std::{fs::OpenOptions, io::Write};

mod companion_provider;
mod desktop_icons;
mod installer_update;
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

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| error.to_string())?;

    writeln!(file, "{event}").map_err(|error| error.to_string())
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
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
        .invoke_handler(tauri::generate_handler![
            record_interaction,
            companion_provider::get_companion_provider_credential,
            companion_provider::set_companion_provider_credential,
            companion_provider::clear_companion_provider_credential,
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
        .setup(|app| {
            setup_tray(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
