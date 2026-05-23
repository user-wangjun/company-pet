use std::{fs::OpenOptions, io::Write};

mod desktop_icons;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, Runtime,
};

const MENU_SHOW: &str = "show-xiaoju";
const MENU_QUIT: &str = "quit-xiaoju";

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

fn setup_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, MENU_SHOW, "隐藏小橘", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, MENU_QUIT, "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;

    let show_item_menu = show.clone();
    let show_item_tray = show.clone();

    if let Some(icon) = app.default_window_icon().cloned() {
        TrayIconBuilder::with_id("xiaoju-tray")
            .tooltip("小橘桌宠")
            .icon(icon)
            .menu(&menu)
            .show_menu_on_left_click(true)
            .on_menu_event(move |app, event| match event.id().as_ref() {
                MENU_SHOW => {
                    if let Some(window) = app.get_webview_window("main") {
                        if let Ok(visible) = window.is_visible() {
                            let new_text = if visible {
                                let _ = window.hide();
                                "显示小橘"
                            } else {
                                let _ = window.show();
                                let _ = window.unminimize();
                                let _ = window.set_focus();
                                "隐藏小橘"
                            };
                            let _ = show_item_menu.set_text(new_text);
                        }
                    }
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
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                        let _ = show_item_tray.set_text("隐藏小橘");
                    }
                }
            })
            .build(app)?;
    }

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            record_interaction,
            desktop_icons::get_desktop_icons,
            desktop_icons::is_point_on_desktop
        ])
        .setup(|app| {
            setup_tray(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

