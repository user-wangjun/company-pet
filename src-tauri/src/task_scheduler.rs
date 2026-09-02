use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskSchedule {
    instance_id: String,
    scheduled_at: String,
    wake_kind: Option<String>,
}

#[cfg(target_os = "windows")]
fn schedule_name(instance_id: &str) -> String {
    let safe: String = instance_id
        .chars()
        .filter(|character| character.is_ascii_alphanumeric() || *character == '-')
        .take(96)
        .collect();
    format!("YuxinReminder_{safe}")
}

#[cfg(target_os = "windows")]
fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

#[cfg(target_os = "windows")]
fn task_xml(executable: &std::path::Path, start_boundary: &str, wake_kind: Option<&str>) -> String {
    let arguments = wake_kind
        .map(|kind| format!("--task-reminder-wakeup --care-kind {kind}"))
        .unwrap_or_else(|| "--task-reminder-wakeup".into());
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><TimeTrigger><StartBoundary>{}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><WakeToRun>true</WakeToRun><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><DeleteExpiredTaskAfter>PT1H</DeleteExpiredTaskAfter><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>{}</Command><Arguments>{}</Arguments></Exec></Actions>
</Task>"#,
        xml_escape(start_boundary),
        xml_escape(&executable.display().to_string()),
        xml_escape(&arguments),
    )
}

#[cfg(target_os = "windows")]
fn should_write_schedule_index(existing: Option<&[u8]>, next: &[u8]) -> bool {
    match existing {
        Some(previous) => previous != next,
        None => next != b"[]",
    }
}

#[cfg(target_os = "windows")]
fn delete_schedule(name: &str) {
    let _ = std::process::Command::new("schtasks.exe")
        .args(["/Delete", "/TN", name, "/F"])
        .creation_flags(0x08000000)
        .status();
}

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[tauri::command]
pub fn sync_task_schedules(
    app: tauri::AppHandle,
    schedules: Vec<TaskSchedule>,
) -> Result<(), String> {
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app, schedules);
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        use chrono::{DateTime, Local};
        use std::collections::HashSet;
        use std::fs;
        use tauri::Manager;

        let data_dir = app
            .path()
            .app_data_dir()
            .map_err(|error| error.to_string())?;
        let index_path = data_dir.join("task-schedules.json");
        let previous: Vec<String> = fs::read_to_string(&index_path)
            .ok()
            .and_then(|text| serde_json::from_str(&text).ok())
            .unwrap_or_default();
        let now = Local::now();
        let future: Vec<(String, DateTime<Local>, Option<String>)> = schedules
            .into_iter()
            .filter_map(|schedule| {
                let date = DateTime::parse_from_rfc3339(&schedule.scheduled_at)
                    .ok()?
                    .with_timezone(&Local);
                (date > now).then(|| {
                    (
                        schedule_name(&schedule.instance_id),
                        date,
                        schedule.wake_kind,
                    )
                })
            })
            .collect();
        let desired: HashSet<&str> = future.iter().map(|(name, _, _)| name.as_str()).collect();
        for name in previous
            .iter()
            .filter(|name| !desired.contains(name.as_str()))
        {
            delete_schedule(name);
        }
        drop(desired);

        if future.is_empty() && !index_path.exists() {
            return Ok(());
        }
        fs::create_dir_all(&data_dir).map_err(|error| error.to_string())?;

        let executable = std::env::current_exe().map_err(|error| error.to_string())?;
        let mut created = Vec::new();
        for (name, date, wake_kind) in future {
            let start_boundary = date.format("%Y-%m-%dT%H:%M:%S").to_string();
            let xml_path = data_dir.join(format!("{name}.xml"));
            fs::write(
                &xml_path,
                task_xml(&executable, &start_boundary, wake_kind.as_deref()),
            )
            .map_err(|error| error.to_string())?;
            let status = std::process::Command::new("schtasks.exe")
                .args([
                    "/Create",
                    "/TN",
                    &name,
                    "/XML",
                    &xml_path.display().to_string(),
                    "/F",
                ])
                .creation_flags(0x08000000)
                .status();
            let _ = fs::remove_file(xml_path);
            if status.is_ok_and(|value| value.success()) {
                created.push(name);
            }
        }
        let serialized = serde_json::to_vec(&created).map_err(|error| error.to_string())?;
        if should_write_schedule_index(fs::read(&index_path).ok().as_deref(), &serialized) {
            fs::write(index_path, serialized).map_err(|error| error.to_string())?;
        }
        Ok(())
    }
}

#[tauri::command]
pub fn is_task_scheduler_wakeup() -> bool {
    std::env::args().any(|argument| argument == "--task-reminder-wakeup")
}

pub fn task_scheduler_wakeup_kind_from_args(args: &[String]) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == "--care-kind")
        .map(|pair| pair[1].clone())
}

#[tauri::command]
pub fn get_task_scheduler_wakeup_kind() -> Option<String> {
    task_scheduler_wakeup_kind_from_args(&std::env::args().collect::<Vec<_>>())
}

#[cfg(all(test, target_os = "windows"))]
mod tests {
    use super::{
        schedule_name, should_write_schedule_index, task_scheduler_wakeup_kind_from_args, task_xml,
    };

    #[test]
    fn builds_safe_windows_task_names() {
        assert_eq!(
            schedule_name("instance-123/unsafe"),
            "YuxinReminder_instance-123unsafe"
        );
    }

    #[test]
    fn scheduler_xml_wakes_and_runs_missed_tasks() {
        let xml = task_xml(
            std::path::Path::new(r#"C:\Apps\Yuxin & Pet.exe"#),
            "2026-07-13T10:30:00",
            None,
        );
        assert!(xml.contains("<StartWhenAvailable>true</StartWhenAvailable>"));
        assert!(xml.contains("<WakeToRun>true</WakeToRun>"));
        assert!(xml.contains("<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"));
        assert!(xml.contains("<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"));
        assert!(xml.contains("<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"));
        assert!(xml.contains("Yuxin &amp; Pet.exe"));
    }

    #[test]
    fn adds_care_kind_to_scheduler_arguments() {
        let xml = task_xml(
            std::path::Path::new(r#"C:\Apps\Yuxin.exe"#),
            "2026-07-13T10:30:00",
            Some("wellness"),
        );
        assert!(xml.contains("--task-reminder-wakeup --care-kind wellness"));
    }

    #[test]
    fn parses_care_kind_from_scheduler_arguments() {
        let args = vec![
            "yuxin-desktop-pet.exe".into(),
            "--task-reminder-wakeup".into(),
            "--care-kind".into(),
            "meal".into(),
        ];
        assert_eq!(
            task_scheduler_wakeup_kind_from_args(&args).as_deref(),
            Some("meal")
        );
    }

    #[test]
    fn does_not_rewrite_an_unchanged_empty_schedule_index() {
        assert!(!should_write_schedule_index(Some(b"[]"), b"[]"));
        assert!(!should_write_schedule_index(None, b"[]"));
        assert!(should_write_schedule_index(None, br#"["YuxinReminder_1"]"#));
        assert!(should_write_schedule_index(
            Some(b"[]"),
            br#"["YuxinReminder_1"]"#
        ));
    }
}
