#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod config;
mod integrity;
mod logging;
mod update;
mod windows_mutex;

use config::*;
use std::{
    env, ffi::c_void, os::windows::process::CommandExt, path::Path, process::Command,
    time::Duration,
};
use update::Decision;
use windows_mutex::{NamedMutex, mutex_exists, process_at_path_exists};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[link(name = "user32")]
unsafe extern "system" {
    fn MessageBoxW(window: *mut c_void, text: *const u16, caption: *const u16, kind: u32) -> i32;
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}
fn message(title: &str, body: &str, error: bool) {
    unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            wide(body).as_ptr(),
            wide(title).as_ptr(),
            if error { 0x10 } else { 0x40 },
        );
    }
}
fn log(message: &str) {
    logging::write(&updater_log(), message);
}

fn validate_location() -> Result<(), String> {
    let current = env::current_exe().map_err(|error| error.to_string())?;
    let expected_dir = Path::new(LOCAL_INSTALL_DIR)
        .canonicalize()
        .unwrap_or_else(|_| LOCAL_INSTALL_DIR.into());
    let actual_dir = current
        .parent()
        .unwrap_or(Path::new(""))
        .canonicalize()
        .unwrap_or_else(|_| current.parent().unwrap_or(Path::new("")).into());
    if !current
        .file_name()
        .is_some_and(|name| name.eq_ignore_ascii_case("qm-updater.exe"))
        || actual_dir != expected_dir
    {
        return Err(format!(
            "Der Updater muss als {}\\qm-updater.exe gestartet werden.",
            LOCAL_INSTALL_DIR
        ));
    }
    Ok(())
}

fn start_local() -> Result<(), String> {
    let executable = local_exe();
    if !executable.is_file() {
        return Err(format!("Lokale Anwendung fehlt: {}", executable.display()));
    }
    Command::new(&executable)
        .current_dir(LOCAL_INSTALL_DIR)
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|error| format!("QM konnte nicht gestartet werden: {error}"))?;
    log("Lokale QM-Anwendung gestartet");
    Ok(())
}

fn run() -> Result<(), String> {
    validate_location()?;
    let _updater = NamedMutex::acquire(UPDATER_MUTEX_NAME)?
        .ok_or_else(|| "Der QM-Updater läuft bereits.".to_string())?;
    let local = local_exe();
    if mutex_exists(APP_MUTEX_NAME) || process_at_path_exists(&local) {
        return Err("QM ist bereits geöffnet. Bitte zunächst vollständig schließen.".into());
    }
    log("Updater gestartet");
    let remote = Path::new(NETWORK_EXE);
    let remote_meta = match update::stable_metadata(remote, Duration::from_millis(750)) {
        Ok(metadata) => metadata,
        Err(error) => {
            log(&format!(
                "Netzquelle nicht verwendbar: {error}; lokale Version wird gestartet"
            ));
            return start_local();
        }
    };
    let local_meta = std::fs::metadata(&local).ok();
    if update::decide(local_meta.as_ref(), &remote_meta) == Decision::Current {
        log("Kein Update erforderlich");
        return start_local();
    }
    log("Update erforderlich; Staging beginnt");
    let staged = local_new();
    if let Err(error) = update::stage(remote, &staged, &remote_meta) {
        update::cleanup_staged(staged);
        log(&format!(
            "Updateprüfung fehlgeschlagen: {error}; lokale Version wird gestartet"
        ));
        message(
            "QM-Updater",
            "Das Update konnte nicht sicher geprüft werden. Die vorhandene lokale Version wird gestartet.",
            true,
        );
        return start_local();
    }
    if mutex_exists(APP_MUTEX_NAME) || process_at_path_exists(&local) {
        update::cleanup_staged(staged);
        return Err("QM wurde während des Updates geöffnet; Austausch abgebrochen.".into());
    }
    if let Err(error) = update::replace(&local, &staged, &local_old()) {
        update::cleanup_staged(staged);
        log(&format!(
            "Austausch fehlgeschlagen: {error}; lokale Version wird gestartet"
        ));
        message(
            "QM-Updater",
            "Das Update konnte nicht eingesetzt werden. Die vorhandene lokale Version wird gestartet.",
            true,
        );
        return start_local();
    }
    log("Update erfolgreich eingesetzt");
    start_local()
}

fn self_test() -> Result<(), String> {
    if config::local_exe()
        .file_name()
        .and_then(|name| name.to_str())
        != Some("qm.exe")
    {
        return Err("Pfadtest fehlgeschlagen".into());
    }
    let current = env::current_exe().map_err(|error| error.to_string())?;
    if !integrity::plausible_pe(&current)? {
        return Err("Updater ist keine plausible PE-Datei".into());
    }
    let _ = integrity::sha256(&current)?;
    Ok(())
}

fn main() {
    let result = if env::args_os().any(|arg| arg == "--self-test") {
        self_test()
    } else {
        run()
    };
    if let Err(error) = result {
        log(&format!("Fehler: {error}"));
        message("QM-Updater", &error, true);
        std::process::exit(1);
    }
}
