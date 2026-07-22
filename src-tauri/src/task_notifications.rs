#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskNotificationAction {
    instance_id: String,
    action: String,
}

pub fn parse_activation(argument: &str) -> Option<TaskNotificationAction> {
    let rest = argument.strip_prefix("yuxin://task-action/")?;
    let (action, query) = rest.split_once('?').unwrap_or((rest, ""));
    let instance_id = query
        .split('&')
        .find_map(|part| part.strip_prefix("instance="))?;
    let valid_action = matches!(
        action,
        "complete"
            | "snooze-10"
            | "snooze-30"
            | "snooze-60"
            | "detail"
            | "dismiss"
            | "summary-detail"
            | "summary-close"
    );
    if !valid_action
        || instance_id.is_empty()
        || !instance_id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-')
    {
        return None;
    }
    Some(TaskNotificationAction {
        instance_id: instance_id.into(),
        action: action.into(),
    })
}

#[tauri::command]
pub fn get_initial_task_notification_actions() -> Vec<TaskNotificationAction> {
    std::env::args()
        .filter_map(|argument| parse_activation(&argument))
        .collect()
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

#[tauri::command]
pub fn show_task_notification(
    app: tauri::AppHandle,
    instance_id: String,
    title: String,
    body: String,
    sound_mode: String,
) -> Result<(), String> {
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app, instance_id, title, body, sound_mode);
        return Err("custom task notification is only available on Windows".into());
    }

    #[cfg(target_os = "windows")]
    {
        use tauri::Emitter;
        use windows::{
            core::{IInspectable, Interface, HSTRING},
            Data::Xml::Dom::XmlDocument,
            Foundation::TypedEventHandler,
            UI::Notifications::{
                ToastActivatedEventArgs, ToastDismissalReason, ToastDismissedEventArgs,
                ToastNotification, ToastNotificationManager,
            },
        };

        let audio = match sound_mode.as_str() {
            "off" => r#"<audio silent="true"/>"#,
            "gentle" => r#"<audio src="ms-winsoundevent:Notification.IM"/>"#,
            "pet" | "custom" => r#"<audio silent="true"/>"#,
            _ => "",
        };
        let action_uri =
            |action: &str| format!("yuxin://task-action/{action}?instance={instance_id}");
        let xml = format!(
            r#"<toast launch="{}" activationType="protocol"><visual><binding template="ToastGeneric"><text>{}</text><text>{}</text></binding></visual>{}<actions><action content="已完成" arguments="{}" activationType="protocol"/><action content="10分钟后" arguments="{}" activationType="protocol"/><action content="30分钟后" arguments="{}" activationType="protocol"/><action content="1小时后" arguments="{}" activationType="protocol"/><action content="查看详情" arguments="{}" activationType="protocol"/></actions></toast>"#,
            xml_escape(&action_uri("detail")),
            xml_escape(&title),
            xml_escape(&body),
            audio,
            xml_escape(&action_uri("complete")),
            xml_escape(&action_uri("snooze-10")),
            xml_escape(&action_uri("snooze-30")),
            xml_escape(&action_uri("snooze-60")),
            xml_escape(&action_uri("detail")),
        );
        let document = XmlDocument::new().map_err(|error| error.to_string())?;
        document
            .LoadXml(&HSTRING::from(xml))
            .map_err(|error| error.to_string())?;
        let toast = ToastNotification::CreateToastNotification(&document)
            .map_err(|error| error.to_string())?;
        let tag = HSTRING::from(instance_id.clone());
        let group = HSTRING::from("yuxin-tasks");
        toast.SetTag(&tag).map_err(|error| error.to_string())?;
        toast.SetGroup(&group).map_err(|error| error.to_string())?;

        let activated_app = app.clone();
        let activated_instance = instance_id.clone();
        toast
            .Activated(&TypedEventHandler::<ToastNotification, IInspectable>::new(
                move |_toast, args| {
                    let raw_action = args
                        .as_ref()
                        .and_then(|value| value.cast::<ToastActivatedEventArgs>().ok())
                        .and_then(|value| value.Arguments().ok())
                        .map(|value| value.to_string())
                        .filter(|value| !value.is_empty())
                        .unwrap_or_else(|| "detail".into());
                    let action = parse_activation(&raw_action)
                        .map(|payload| payload.action)
                        .unwrap_or(raw_action);
                    let _ = activated_app.emit(
                        "task-notification-action",
                        TaskNotificationAction {
                            instance_id: activated_instance.clone(),
                            action,
                        },
                    );
                    Ok(())
                },
            ))
            .map_err(|error| error.to_string())?;

        let dismissed_app = app.clone();
        let dismissed_instance = instance_id.clone();
        toast
            .Dismissed(&TypedEventHandler::<
                ToastNotification,
                ToastDismissedEventArgs,
            >::new(move |_toast, args| {
                if args.as_ref().and_then(|value| value.Reason().ok())
                    == Some(ToastDismissalReason::UserCanceled)
                {
                    let _ = dismissed_app.emit(
                        "task-notification-action",
                        TaskNotificationAction {
                            instance_id: dismissed_instance.clone(),
                            action: "dismiss".into(),
                        },
                    );
                }
                Ok(())
            }))
            .map_err(|error| error.to_string())?;

        let notifier = ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(
            app.config().identifier.clone(),
        ))
        .map_err(|error| error.to_string())?;
        notifier.Show(&toast).map_err(|error| error.to_string())
    }
}

#[tauri::command]
pub fn show_task_summary_notification(
    app: tauri::AppHandle,
    summary_id: String,
    count: usize,
    sound_mode: String,
) -> Result<(), String> {
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app, summary_id, count, sound_mode);
        return Err("custom task notification is only available on Windows".into());
    }
    #[cfg(target_os = "windows")]
    {
        use windows::{
            core::HSTRING,
            Data::Xml::Dom::XmlDocument,
            UI::Notifications::{ToastNotification, ToastNotificationManager},
        };
        let audio = match sound_mode.as_str() {
            "off" => r#"<audio silent="true"/>"#,
            "gentle" => r#"<audio src="ms-winsoundevent:Notification.IM"/>"#,
            "pet" | "custom" => r#"<audio silent="true"/>"#,
            _ => "",
        };
        let detail = format!("yuxin://task-action/summary-detail?instance={summary_id}");
        let close = format!("yuxin://task-action/summary-close?instance={summary_id}");
        let xml = format!(
            r#"<toast launch="{}" activationType="protocol"><visual><binding template="ToastGeneric"><text>错过的待办提醒</text><text>你有 {} 条提醒待查看</text></binding></visual>{}<actions><action content="查看全部" arguments="{}" activationType="protocol"/><action content="关闭" arguments="{}" activationType="protocol"/></actions></toast>"#,
            xml_escape(&detail),
            count,
            audio,
            xml_escape(&detail),
            xml_escape(&close)
        );
        let document = XmlDocument::new().map_err(|e| e.to_string())?;
        document
            .LoadXml(&HSTRING::from(xml))
            .map_err(|e| e.to_string())?;
        let toast =
            ToastNotification::CreateToastNotification(&document).map_err(|e| e.to_string())?;
        toast
            .SetTag(&HSTRING::from(summary_id))
            .map_err(|e| e.to_string())?;
        toast
            .SetGroup(&HSTRING::from("yuxin-tasks"))
            .map_err(|e| e.to_string())?;
        let notifier = ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from(
            app.config().identifier.clone(),
        ))
        .map_err(|e| e.to_string())?;
        notifier.Show(&toast).map_err(|e| e.to_string())
    }
}

#[tauri::command]
pub fn clear_task_notification(app: tauri::AppHandle, instance_id: String) -> Result<(), String> {
    #[cfg(not(target_os = "windows"))]
    {
        let _ = (app, instance_id);
        return Ok(());
    }

    #[cfg(target_os = "windows")]
    {
        use windows::{core::HSTRING, UI::Notifications::ToastNotificationManager};
        ToastNotificationManager::History()
            .and_then(|history| {
                history.RemoveGroupedTagWithId(
                    &HSTRING::from(instance_id),
                    &HSTRING::from("yuxin-tasks"),
                    &HSTRING::from(app.config().identifier.clone()),
                )
            })
            .map_err(|error| error.to_string())
    }
}

#[cfg(all(test, target_os = "windows"))]
mod tests {
    use super::{parse_activation, xml_escape};

    #[test]
    fn escapes_task_text_for_toast_xml() {
        assert_eq!(
            xml_escape("A&B <提醒> \"完成\""),
            "A&amp;B &lt;提醒&gt; &quot;完成&quot;"
        );
    }

    #[test]
    fn parses_persistent_notification_action() {
        let action =
            parse_activation("yuxin://task-action/snooze-10?instance=instance-123").unwrap();
        assert_eq!(action.instance_id, "instance-123");
        assert_eq!(action.action, "snooze-10");
        assert!(parse_activation("https://example.com").is_none());
    }
}
