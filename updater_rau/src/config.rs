use std::path::PathBuf;

pub const NETWORK_EXE: &str = r"J:\EPZ\Daten OA Troeger\qm.exe";
pub const LOCAL_INSTALL_DIR: &str = r"C:\Users\rau\Documents\qm";
pub const APP_MUTEX_NAME: &str = r"Local\QMDesktop-Application";
pub const UPDATER_MUTEX_NAME: &str = r"Local\QMDesktop-Updater";

pub fn local_exe() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("qm.exe")
}
pub fn local_old() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("qm.exe.old")
}
pub fn local_new() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("qm.exe.new")
}
pub fn updater_log() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR)
        .join("logs")
        .join("updater.log")
}
