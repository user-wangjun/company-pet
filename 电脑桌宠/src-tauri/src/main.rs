// Rust/Cargo is not installed on the current machine yet, so the first visible
// milestone runs through Vite. This shell is ready for the Windows Tauri layer.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running orange cat desktop pet");
}

fn main() {
    run();
}
