use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct DesktopIcon {
    pub title: String,
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[tauri::command]
pub fn get_desktop_icons() -> Result<Vec<DesktopIcon>, String> {
    if let Some(icons) = read_fixture_icons()? {
        return Ok(icons);
    }

    #[cfg(windows)]
    {
        read_windows_desktop_icons()
    }

    #[cfg(not(windows))]
    {
        Ok(Vec::new())
    }
}

#[tauri::command]
pub fn is_point_on_desktop(x: i32, y: i32, window: tauri::Window) -> bool {
    #[cfg(windows)]
    {
        windows_desktop_sensing::is_point_on_desktop(x, y, &window)
    }

    #[cfg(not(windows))]
    {
        let _ = x;
        let _ = y;
        let _ = window;
        true
    }
}

#[cfg(windows)]
mod windows_desktop_sensing {
    use tauri::Window;
    use windows_sys::Win32::{
        Foundation::{HWND, RECT},
        UI::WindowsAndMessaging::{
            GetAncestor, GetClassNameW, GetShellWindow, GetTopWindow, GetWindow, GetWindowRect,
            IsWindowVisible, GA_ROOT, GW_HWNDNEXT,
        },
    };

    pub fn is_point_on_desktop(x: i32, y: i32, window: &Window) -> bool {
        let scale_factor = window.scale_factor().unwrap_or(1.0);
        let outer_pos = match window.outer_position() {
            Ok(pos) => pos,
            Err(_) => return false,
        };

        let physical_x = outer_pos.x + (x as f64 * scale_factor).round() as i32;
        let physical_y = outer_pos.y + (y as f64 * scale_factor).round() as i32;

        unsafe {
            let own_hwnd = match window.hwnd() {
                Ok(h) => h.0 as HWND,
                Err(_) => std::ptr::null_mut(),
            };
            let own_root = if !own_hwnd.is_null() {
                GetAncestor(own_hwnd, GA_ROOT)
            } else {
                std::ptr::null_mut()
            };

            let shell_window = GetShellWindow();

            let mut hwnd = GetTopWindow(std::ptr::null_mut());
            while !hwnd.is_null() {
                if hwnd == own_hwnd || hwnd == own_root {
                    hwnd = GetWindow(hwnd, GW_HWNDNEXT);
                    continue;
                }

                if IsWindowVisible(hwnd) != 0 {
                    let mut rect = RECT::default();
                    if GetWindowRect(hwnd, &mut rect) != 0 {
                        let width = rect.right - rect.left;
                        let height = rect.bottom - rect.top;
                        if width <= 0 || height <= 0 {
                            hwnd = GetWindow(hwnd, GW_HWNDNEXT);
                            continue;
                        }

                        if physical_x >= rect.left
                            && physical_x < rect.right
                            && physical_y >= rect.top
                            && physical_y < rect.bottom
                        {
                            if hwnd == shell_window {
                                return true;
                            }

                            let mut class_name = [0u16; 256];
                            let len = GetClassNameW(hwnd, class_name.as_mut_ptr(), class_name.len() as i32);
                            if len > 0 {
                                let name = String::from_utf16_lossy(&class_name[..len as usize]);
                                let lower_name = name.to_lowercase();
                                
                                // Skip known system-level transparent helper/overlay windows
                                if lower_name.contains("helper")
                                    || lower_name.contains("dummy")
                                    || lower_name.contains("event")
                                    || lower_name.contains("hidden")
                                    || lower_name.starts_with("atl:")
                                    || lower_name == "bkshadowwndclass"
                                    || lower_name == "tao thread event target"
                                    || lower_name == "windows.ui.core.corewindow"
                                    || lower_name == "islandwindow"
                                    || lower_name == "edgeuiinputtopwndclass"
                                    || lower_name == "shell_inputswitchtoplevelwindow"
                                {
                                    hwnd = GetWindow(hwnd, GW_HWNDNEXT);
                                    continue;
                                }

                                if name == "Progman" || name == "WorkerW" || name == "Shell_TrayWnd" {
                                    return true;
                                }
                            }

                            return false;
                        }
                    }
                }

                hwnd = GetWindow(hwnd, GW_HWNDNEXT);
            }
        }

        true
    }
}


fn read_fixture_icons() -> Result<Option<Vec<DesktopIcon>>, String> {
    if let Ok(json) = std::env::var("XIAOJU_DESKTOP_ICON_FIXTURE") {
        return parse_desktop_icon_fixture(&json).map(Some);
    }

    let Ok(path) = std::env::var("XIAOJU_DESKTOP_ICON_FIXTURE_FILE") else {
        return Ok(None);
    };

    match std::fs::read_to_string(path) {
        Ok(json) if json.trim().is_empty() => Ok(Some(Vec::new())),
        Ok(json) => parse_desktop_icon_fixture(&json).map(Some),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(Some(Vec::new())),
        Err(error) => Err(format!("desktop icon fixture file: {error}")),
    }
}

pub fn parse_desktop_icon_fixture(json: &str) -> Result<Vec<DesktopIcon>, String> {
    serde_json::from_str(json).map_err(|error| format!("desktop icon fixture: {error}"))
}

#[cfg(windows)]
fn read_windows_desktop_icons() -> Result<Vec<DesktopIcon>, String> {
    windows_desktop_icons::read_desktop_icons()
}

#[cfg(windows)]
mod windows_desktop_icons {
    use super::DesktopIcon;
    use std::{ffi::c_void, mem::size_of, ptr::null};
    use windows_sys::{
        core::PCWSTR,
        Win32::{
            Foundation::{CloseHandle, HANDLE, HWND, LPARAM, POINT, RECT, WPARAM},
            System::{
                Diagnostics::Debug::{ReadProcessMemory, WriteProcessMemory},
                Memory::{
                    VirtualAllocEx, VirtualFreeEx, MEM_COMMIT, MEM_RELEASE, MEM_RESERVE,
                    PAGE_READWRITE,
                },
                Threading::{
                    OpenProcess, PROCESS_VM_OPERATION, PROCESS_VM_READ, PROCESS_VM_WRITE,
                },
            },
            UI::{
                Controls::{
                    LVIF_TEXT, LVIR_BOUNDS, LVITEMW, LVM_GETITEMCOUNT, LVM_GETITEMPOSITION,
                    LVM_GETITEMRECT, LVM_GETITEMTEXTW,
                },
                WindowsAndMessaging::{
                    EnumWindows, FindWindowExW, FindWindowW, GetWindowRect,
                    GetWindowThreadProcessId, SendMessageW,
                },
            },
        },
    };

    const DEFAULT_ICON_WIDTH: i32 = 74;
    const DEFAULT_ICON_HEIGHT: i32 = 82;
    const MAX_ICON_TEXT_CHARS: usize = 260;

    struct ProcessHandle(HANDLE);

    impl Drop for ProcessHandle {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe {
                    CloseHandle(self.0);
                }
            }
        }
    }

    struct RemoteMemory {
        process: HANDLE,
        ptr: *mut c_void,
    }

    impl RemoteMemory {
        fn new(process: HANDLE, bytes: usize) -> Result<Self, String> {
            let ptr = unsafe {
                VirtualAllocEx(
                    process,
                    null(),
                    bytes,
                    MEM_COMMIT | MEM_RESERVE,
                    PAGE_READWRITE,
                )
            };

            if ptr.is_null() {
                return Err("unable to allocate Explorer memory for desktop icons".to_string());
            }

            Ok(Self { process, ptr })
        }
    }

    impl Drop for RemoteMemory {
        fn drop(&mut self) {
            if !self.ptr.is_null() {
                unsafe {
                    VirtualFreeEx(self.process, self.ptr, 0, MEM_RELEASE);
                }
            }
        }
    }

    pub fn read_desktop_icons() -> Result<Vec<DesktopIcon>, String> {
        let list_view = unsafe { find_desktop_list_view() };
        if list_view.is_null() {
            return Ok(Vec::new());
        }

        let item_count = unsafe { SendMessageW(list_view, LVM_GETITEMCOUNT, 0, 0) };
        if item_count <= 0 {
            return Ok(Vec::new());
        }

        let mut process_id = 0;
        unsafe {
            GetWindowThreadProcessId(list_view, &mut process_id);
        }
        if process_id == 0 {
            return Err("unable to locate Explorer process for desktop icons".to_string());
        }

        let process = unsafe {
            OpenProcess(
                PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
                0,
                process_id,
            )
        };
        if process.is_null() {
            return Err("unable to open Explorer process for desktop icons".to_string());
        }
        let process = ProcessHandle(process);

        let remote_item = RemoteMemory::new(process.0, size_of::<LVITEMW>())?;
        let remote_text = RemoteMemory::new(process.0, MAX_ICON_TEXT_CHARS * size_of::<u16>())?;
        let remote_point = RemoteMemory::new(process.0, size_of::<POINT>())?;
        let remote_rect = RemoteMemory::new(process.0, size_of::<RECT>())?;

        let mut list_view_rect = RECT::default();
        unsafe {
            GetWindowRect(list_view, &mut list_view_rect);
        }

        let mut icons = Vec::new();
        for index in 0..item_count as i32 {
            let title = read_item_title(list_view, process.0, &remote_item, &remote_text, index)?;
            let rect = read_item_rect(
                list_view,
                process.0,
                &remote_rect,
                &remote_point,
                index,
                list_view_rect,
            )?;

            icons.push(DesktopIcon {
                title,
                x: rect.left,
                y: rect.top,
                width: (rect.right - rect.left).max(DEFAULT_ICON_WIDTH),
                height: (rect.bottom - rect.top).max(DEFAULT_ICON_HEIGHT),
            });
        }

        Ok(icons)
    }

    fn read_item_title(
        list_view: HWND,
        process: HANDLE,
        remote_item: &RemoteMemory,
        remote_text: &RemoteMemory,
        index: i32,
    ) -> Result<String, String> {
        let item = LVITEMW {
            mask: LVIF_TEXT,
            iItem: index,
            iSubItem: 0,
            pszText: remote_text.ptr as *mut u16,
            cchTextMax: MAX_ICON_TEXT_CHARS as i32,
            ..Default::default()
        };
        write_remote(process, remote_item.ptr, &item)?;

        unsafe {
            SendMessageW(
                list_view,
                LVM_GETITEMTEXTW,
                index as WPARAM,
                remote_item.ptr as LPARAM,
            );
        }

        let mut buffer = [0u16; MAX_ICON_TEXT_CHARS];
        read_remote_slice(process, remote_text.ptr, &mut buffer)?;
        let end = buffer.iter().position(|code| *code == 0).unwrap_or(buffer.len());

        Ok(String::from_utf16_lossy(&buffer[..end]))
    }

    fn read_item_rect(
        list_view: HWND,
        process: HANDLE,
        remote_rect: &RemoteMemory,
        remote_point: &RemoteMemory,
        index: i32,
        list_view_rect: RECT,
    ) -> Result<RECT, String> {
        let mut bounds = RECT {
            left: LVIR_BOUNDS as i32,
            ..Default::default()
        };
        write_remote(process, remote_rect.ptr, &bounds)?;

        let rect_ok = unsafe {
            SendMessageW(
                list_view,
                LVM_GETITEMRECT,
                index as WPARAM,
                remote_rect.ptr as LPARAM,
            )
        } != 0;

        if rect_ok {
            read_remote(process, remote_rect.ptr, &mut bounds)?;
            if bounds.right > bounds.left && bounds.bottom > bounds.top {
                return Ok(RECT {
                    left: list_view_rect.left + bounds.left,
                    top: list_view_rect.top + bounds.top,
                    right: list_view_rect.left + bounds.right,
                    bottom: list_view_rect.top + bounds.bottom,
                });
            }
        }

        let mut point = POINT::default();
        write_remote(process, remote_point.ptr, &point)?;
        unsafe {
            SendMessageW(
                list_view,
                LVM_GETITEMPOSITION,
                index as WPARAM,
                remote_point.ptr as LPARAM,
            );
        }
        read_remote(process, remote_point.ptr, &mut point)?;

        Ok(RECT {
            left: list_view_rect.left + point.x,
            top: list_view_rect.top + point.y,
            right: list_view_rect.left + point.x + DEFAULT_ICON_WIDTH,
            bottom: list_view_rect.top + point.y + DEFAULT_ICON_HEIGHT,
        })
    }

    fn write_remote<T>(process: HANDLE, remote: *mut c_void, value: &T) -> Result<(), String> {
        let ok = unsafe {
            WriteProcessMemory(
                process,
                remote,
                value as *const T as *const c_void,
                size_of::<T>(),
                std::ptr::null_mut(),
            )
        };

        if ok == 0 {
            return Err("unable to write Explorer memory for desktop icons".to_string());
        }

        Ok(())
    }

    fn read_remote<T>(process: HANDLE, remote: *mut c_void, value: &mut T) -> Result<(), String> {
        let ok = unsafe {
            ReadProcessMemory(
                process,
                remote,
                value as *mut T as *mut c_void,
                size_of::<T>(),
                std::ptr::null_mut(),
            )
        };

        if ok == 0 {
            return Err("unable to read Explorer memory for desktop icons".to_string());
        }

        Ok(())
    }

    fn read_remote_slice<T>(
        process: HANDLE,
        remote: *mut c_void,
        buffer: &mut [T],
    ) -> Result<(), String> {
        let ok = unsafe {
            ReadProcessMemory(
                process,
                remote,
                buffer.as_mut_ptr() as *mut c_void,
                std::mem::size_of_val(buffer),
                std::ptr::null_mut(),
            )
        };

        if ok == 0 {
            return Err("unable to read Explorer text for desktop icons".to_string());
        }

        Ok(())
    }

    unsafe fn find_desktop_list_view() -> HWND {
        let progman = {
            let class_name = wide_null("Progman");
            FindWindowW(class_name.as_ptr(), std::ptr::null())
        };

        let direct = find_list_view_under(progman);
        if !direct.is_null() {
            return direct;
        }

        let mut found: HWND = std::ptr::null_mut();
        EnumWindows(Some(enum_desktop_windows), &mut found as *mut HWND as LPARAM);
        found
    }

    unsafe extern "system" fn enum_desktop_windows(hwnd: HWND, lparam: LPARAM) -> i32 {
        let found = lparam as *mut HWND;
        let list_view = find_list_view_under(hwnd);

        if !list_view.is_null() {
            *found = list_view;
            return 0;
        }

        1
    }

    unsafe fn find_list_view_under(parent: HWND) -> HWND {
        if parent.is_null() {
            return std::ptr::null_mut();
        }

        let shell_view = {
            let class_name = wide_null("SHELLDLL_DefView");
            FindWindowExW(parent, std::ptr::null_mut(), class_name.as_ptr(), null_pcwstr())
        };

        if shell_view.is_null() {
            return std::ptr::null_mut();
        }

        let list_view_class = wide_null("SysListView32");
        let folder_view = wide_null("FolderView");
        FindWindowExW(
            shell_view,
            std::ptr::null_mut(),
            list_view_class.as_ptr(),
            folder_view.as_ptr(),
        )
    }

    fn wide_null(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn null_pcwstr() -> PCWSTR {
        std::ptr::null()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_desktop_icon_fixture_json() {
        let icons = parse_desktop_icon_fixture(
            r#"[{"title":"Visual Studio Code","x":120,"y":180,"width":74,"height":82}]"#,
        )
        .expect("fixture should parse");

        assert_eq!(icons.len(), 1);
        assert_eq!(icons[0].title, "Visual Studio Code");
        assert_eq!(icons[0].x, 120);
        assert_eq!(icons[0].y, 180);
        assert_eq!(icons[0].width, 74);
        assert_eq!(icons[0].height, 82);
    }

    #[test]
    fn rejects_invalid_desktop_icon_fixture_json() {
        let error = parse_desktop_icon_fixture("not json").expect_err("fixture should fail");

        assert!(error.contains("desktop icon fixture"));
    }
}
