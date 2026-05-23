mod desktop_sensing;

use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::TrayIconBuilder,
    Manager,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Create menu items
            let toggle_item = MenuItemBuilder::new("隐藏小橘")
                .id("toggle")
                .build(app)?;
            let exit_item = MenuItemBuilder::new("退出")
                .id("exit")
                .build(app)?;

            let menu = MenuBuilder::new(app)
                .item(&toggle_item)
                .item(&exit_item)
                .build()?;

            let toggle_item_clone = toggle_item.clone();

            // Set up system tray icon
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {
                        "toggle" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let is_visible = window.is_visible().unwrap_or(true);
                                if is_visible {
                                    let _ = window.hide();
                                    let _ = toggle_item_clone.set_text("显示小橘");
                                } else {
                                    let _ = window.show();
                                    let _ = window.set_focus();
                                    let _ = toggle_item_clone.set_text("隐藏小橘");
                                }
                            }
                        }
                        "exit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            desktop_sensing::desktop_interaction_context_at
        ])
        .run(tauri::generate_context!())
        .expect("error while running orange cat desktop pet");
}
