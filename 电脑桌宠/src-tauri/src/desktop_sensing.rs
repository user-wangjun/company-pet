use serde::Serialize;

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub(crate) enum DesktopSurface {
    Desktop,
    ForegroundWindow,
    Unknown,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct Rect {
    x: i32,
    y: i32,
    width: i32,
    height: i32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DesktopInteractionContext {
    surface: DesktopSurface,
    #[serde(skip_serializing_if = "Option::is_none")]
    foreground_window_rect: Option<Rect>,
    #[serde(skip_serializing_if = "Option::is_none")]
    allow_unknown: Option<bool>,
}

#[tauri::command]
pub(crate) fn desktop_interaction_context_at(
    x: i32,
    y: i32,
    window: tauri::Window,
) -> DesktopInteractionContext {
    let (screen_x, screen_y) = resolve_screen_point(x, y, &window);
    let context = detect_desktop_interaction_context_at(screen_x, screen_y, &window);
    
    // Log outer window information and scale factor
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("desktop_sensing_debug.log")
    {
        use std::io::Write;
        let scale = window.scale_factor().unwrap_or(1.0);
        let pos = window.outer_position().map(|p| format!("x={}, y={}", p.x, p.y)).unwrap_or_else(|_| "Error".to_string());
        let _ = writeln!(
            file,
            "--- Command Call ---\nTime: {:?}\nInput logical: x={}, y={}\nScale factor: {}\nOuter position: {}\nResolved screen: x={}, y={}\nReturned context: surface={:?}, allow_unknown={:?}",
            std::time::SystemTime::now(),
            x,
            y,
            scale,
            pos,
            screen_x,
            screen_y,
            context.surface,
            context.allow_unknown
        );
    }
    
    context
}

fn classify_window_class(class_name: &str) -> DesktopSurface {
    match class_name {
        "Progman" | "WorkerW" | "SHELLDLL_DefView" | "SysListView32" => DesktopSurface::Desktop,
        "" => DesktopSurface::Unknown,
        _ => DesktopSurface::ForegroundWindow,
    }
}

fn unknown_context() -> DesktopInteractionContext {
    DesktopInteractionContext {
        surface: DesktopSurface::Unknown,
        foreground_window_rect: None,
        allow_unknown: Some(true),
    }
}

#[cfg(windows)]
fn resolve_screen_point(x: i32, y: i32, window: &tauri::Window) -> (i32, i32) {
    let scale_factor = window.scale_factor().unwrap_or(1.0);
    if let Ok(outer_pos) = window.outer_position() {
        let physical_x = outer_pos.x + (x as f64 * scale_factor).round() as i32;
        let physical_y = outer_pos.y + (y as f64 * scale_factor).round() as i32;
        (physical_x, physical_y)
    } else {
        (x, y)
    }
}

#[cfg(not(windows))]
fn resolve_screen_point(x: i32, y: i32, _window: &tauri::Window) -> (i32, i32) {
    (x, y)
}

#[cfg(windows)]
fn detect_desktop_interaction_context_at(
    x: i32,
    y: i32,
    window: &tauri::Window,
) -> DesktopInteractionContext {
    windows_desktop_interaction_context_at(x, y, window).unwrap_or_else(unknown_context)
}

#[cfg(not(windows))]
fn detect_desktop_interaction_context_at(
    _x: i32,
    _y: i32,
    _window: &tauri::Window,
) -> DesktopInteractionContext {
    unknown_context()
}

#[cfg(windows)]
fn windows_desktop_interaction_context_at(
    x: i32,
    y: i32,
    window: &tauri::Window,
) -> Option<DesktopInteractionContext> {
    use windows::Win32::Foundation::{HWND, POINT, RECT as WinRect};
    use windows::Win32::UI::WindowsAndMessaging::{
        GetAncestor, GetClassNameW, GetShellWindow, GetTopWindow, GetWindow, GetWindowRect,
        IsWindowVisible, GA_ROOT, GW_HWNDNEXT,
    };

    let log_file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("desktop_sensing_debug.log");

    unsafe fn first_visible_window_at(
        point: POINT,
        own_hwnd: Option<HWND>,
        own_root: Option<HWND>,
        mut log: Option<&mut std::fs::File>,
    ) -> Option<HWND> {
        let mut hwnd = GetTopWindow(None).ok()?;
        if let Some(ref mut f) = log {
            use std::io::Write;
            let _ = writeln!(
                f,
                "first_visible_window_at start: point=x:{}, y:{}, own_hwnd={:?}, own_root={:?}",
                point.x, point.y, own_hwnd, own_root
            );
        }
        for i in 0..512 {
            let root = GetAncestor(hwnd, GA_ROOT);
            let candidate = if root.is_invalid() { hwnd } else { root };
            
            let is_visible = IsWindowVisible(candidate).as_bool();
            let contains = window_contains_point(candidate, point);
            
            if let Some(ref mut f) = log {
                use std::io::Write;
                let class = class_name(candidate);
                let rect = window_rect(candidate).map(|r| format!("x={}, y={}, w={}, h={}", r.x, r.y, r.width, r.height)).unwrap_or_else(|| "Error".to_string());
                let _ = writeln!(
                    f,
                    "  [#{}] hwnd={:?}, candidate={:?}, class='{}', visible={}, contains={}, rect=[{}]",
                    i, hwnd, candidate, class, is_visible, contains, rect
                );
            }

            if Some(candidate) != own_hwnd
                && Some(candidate) != own_root
                && is_visible
                && contains
            {
                if let Some(ref mut f) = log {
                    use std::io::Write;
                    let _ = writeln!(f, "  => MATCHED candidate={:?}", candidate);
                }
                return Some(candidate);
            }

            hwnd = GetWindow(hwnd, GW_HWNDNEXT).ok()?;
        }

        None
    }

    unsafe fn window_contains_point(hwnd: HWND, point: POINT) -> bool {
        window_rect(hwnd)
            .map(|rect| {
                point.x >= rect.x
                    && point.x <= rect.x + rect.width
                    && point.y >= rect.y
                    && point.y <= rect.y + rect.height
            })
            .unwrap_or(false)
    }

    unsafe fn window_rect(hwnd: HWND) -> Option<Rect> {
        let mut rect = WinRect::default();
        GetWindowRect(hwnd, &mut rect).ok()?;
        Some(Rect {
            x: rect.left,
            y: rect.top,
            width: rect.right - rect.left,
            height: rect.bottom - rect.top,
        })
    }

    unsafe fn class_name(hwnd: HWND) -> String {
        let mut buffer = [0u16; 256];
        let len = GetClassNameW(hwnd, &mut buffer);
        String::from_utf16_lossy(&buffer[..len.max(0) as usize])
    }

    let point = POINT { x, y };
    let own_hwnd = window.hwnd().ok();
    let own_root = own_hwnd.map(|h| unsafe { GetAncestor(h, GA_ROOT) });
    
    let hwnd = unsafe {
        let mut file = log_file.ok();
        first_visible_window_at(point, own_hwnd, own_root, file.as_mut())?
    };
    let class_name = unsafe { class_name(hwnd) };
    let shell_hwnd = unsafe { GetShellWindow() };
    let surface = if hwnd == shell_hwnd {
        DesktopSurface::Desktop
    } else {
        classify_window_class(&class_name)
    };

    match surface {
        DesktopSurface::Desktop => Some(DesktopInteractionContext {
            surface,
            foreground_window_rect: None,
            allow_unknown: None,
        }),
        DesktopSurface::ForegroundWindow => {
            let rect = unsafe { window_rect(hwnd)? };
            Some(DesktopInteractionContext {
                surface,
                foreground_window_rect: Some(rect),
                allow_unknown: None,
            })
        }
        DesktopSurface::Unknown => Some(unknown_context()),
    }
}

#[cfg(test)]
mod tests {
    use super::{classify_window_class, DesktopSurface};

    #[test]
    fn treats_windows_desktop_shell_classes_as_desktop() {
        assert_eq!(classify_window_class("Progman"), DesktopSurface::Desktop);
        assert_eq!(classify_window_class("WorkerW"), DesktopSurface::Desktop);
        assert_eq!(
            classify_window_class("SHELLDLL_DefView"),
            DesktopSurface::Desktop
        );
    }

    #[test]
    fn treats_regular_application_windows_as_foreground_windows() {
        assert_eq!(
            classify_window_class("Chrome_WidgetWin_1"),
            DesktopSurface::ForegroundWindow
        );
        assert_eq!(
            classify_window_class("CabinetWClass"),
            DesktopSurface::ForegroundWindow
        );
    }
}
