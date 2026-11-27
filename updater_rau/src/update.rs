use std::{
    fs::{self, File, FileTimes, Metadata},
    path::{Path, PathBuf},
    thread,
    time::{Duration, SystemTime},
};

use crate::integrity::{plausible_pe, sha256};

pub const TIMESTAMP_TOLERANCE: Duration = Duration::from_secs(2);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Install,
    Current,
}

pub fn decide(local: Option<&Metadata>, remote: &Metadata) -> Decision {
    let Some(local) = local else {
        return Decision::Install;
    };
    let local_time = local.modified().unwrap_or(SystemTime::UNIX_EPOCH);
    let remote_time = remote.modified().unwrap_or(SystemTime::UNIX_EPOCH);
    let remote_delta = remote_time.duration_since(local_time).ok();
    let newer = remote_delta.is_some_and(|delta| delta >= TIMESTAMP_TOLERANCE);
    let same_time_different_size = remote_delta.is_some_and(|delta| delta < TIMESTAMP_TOLERANCE)
        && remote.len() != local.len();
    if newer || same_time_different_size {
        Decision::Install
    } else {
        Decision::Current
    }
}

pub fn stable_metadata(path: &Path, pause: Duration) -> Result<Metadata, String> {
    let first = fs::metadata(path).map_err(|error| error.to_string())?;
    thread::sleep(pause);
    let second = fs::metadata(path).map_err(|error| error.to_string())?;
    if first.len() != second.len() || first.modified().ok() != second.modified().ok() {
        return Err("Die Netzdatei wird noch verändert".into());
    }
    Ok(second)
}

pub fn stage(remote: &Path, staged: &Path, remote_meta: &Metadata) -> Result<(), String> {
    if staged.exists() {
        fs::remove_file(staged).map_err(|error| error.to_string())?;
    }
    fs::copy(remote, staged).map_err(|error| error.to_string())?;
    let staged_meta = fs::metadata(staged).map_err(|error| error.to_string())?;
    if staged_meta.len() != remote_meta.len() {
        return Err("Dateigröße der Kopie stimmt nicht".into());
    }
    if sha256(remote)? != sha256(staged)? {
        return Err("SHA-256 der Kopie stimmt nicht".into());
    }
    if !plausible_pe(staged)? {
        return Err("Die neue Datei ist keine plausible Windows-EXE".into());
    }
    if let Ok(modified) = remote_meta.modified() {
        File::options()
            .write(true)
            .open(staged)
            .map_err(|error| error.to_string())?
            .set_times(FileTimes::new().set_modified(modified))
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}

pub fn replace(local: &Path, staged: &Path, old: &Path) -> Result<(), String> {
    if old.exists() {
        fs::remove_file(old)
            .map_err(|error| format!("Alte Sicherung kann nicht entfernt werden: {error}"))?;
    }
    let had_local = local.exists();
    if had_local {
        fs::rename(local, old)
            .map_err(|error| format!("Vorversion kann nicht gesichert werden: {error}"))?;
    }
    if let Err(error) = fs::rename(staged, local) {
        if had_local {
            let _ = fs::rename(old, local);
        }
        return Err(format!(
            "Neue Version kann nicht eingesetzt werden: {error}"
        ));
    }
    Ok(())
}

pub fn cleanup_staged(path: PathBuf) {
    if path.exists() {
        let _ = fs::remove_file(path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{env, io::Write};

    fn temp_dir(label: &str) -> PathBuf {
        let path = env::temp_dir().join(format!("qm-updater-{label}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        fs::create_dir_all(&path).unwrap();
        path
    }

    #[test]
    fn missing_local_requires_install() {
        let dir = temp_dir("decision");
        let remote = dir.join("remote.exe");
        fs::write(&remote, b"x").unwrap();
        assert_eq!(
            decide(None, &fs::metadata(remote).unwrap()),
            Decision::Install
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn equal_metadata_is_current() {
        let dir = temp_dir("equal");
        let first = dir.join("first.exe");
        let second = dir.join("second.exe");
        fs::write(&first, b"same").unwrap();
        fs::copy(&first, &second).unwrap();
        let time = fs::metadata(&first).unwrap().modified().unwrap();
        File::options()
            .write(true)
            .open(&second)
            .unwrap()
            .set_times(FileTimes::new().set_modified(time))
            .unwrap();
        assert_eq!(
            decide(
                Some(&fs::metadata(first).unwrap()),
                &fs::metadata(second).unwrap()
            ),
            Decision::Current
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn newer_remote_requires_install() {
        let dir = temp_dir("newer");
        let local = dir.join("local.exe");
        let remote = dir.join("remote.exe");
        fs::write(&local, b"same").unwrap();
        fs::copy(&local, &remote).unwrap();
        let local_time = fs::metadata(&local).unwrap().modified().unwrap();
        File::options()
            .write(true)
            .open(&remote)
            .unwrap()
            .set_times(FileTimes::new().set_modified(local_time + Duration::from_secs(3)))
            .unwrap();
        assert_eq!(
            decide(
                Some(&fs::metadata(local).unwrap()),
                &fs::metadata(remote).unwrap()
            ),
            Decision::Install
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn older_remote_is_not_installed() {
        let dir = temp_dir("older");
        let local = dir.join("local.exe");
        let remote = dir.join("remote.exe");
        fs::write(&local, b"same").unwrap();
        fs::copy(&local, &remote).unwrap();
        let remote_time = fs::metadata(&remote).unwrap().modified().unwrap();
        File::options()
            .write(true)
            .open(&local)
            .unwrap()
            .set_times(FileTimes::new().set_modified(remote_time + Duration::from_secs(3)))
            .unwrap();
        assert_eq!(
            decide(
                Some(&fs::metadata(local).unwrap()),
                &fs::metadata(remote).unwrap()
            ),
            Decision::Current
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn equal_timestamp_with_different_size_requires_install() {
        let dir = temp_dir("size");
        let local = dir.join("local.exe");
        let remote = dir.join("remote.exe");
        fs::write(&local, b"short").unwrap();
        fs::write(&remote, b"longer").unwrap();
        let time = fs::metadata(&local).unwrap().modified().unwrap();
        File::options()
            .write(true)
            .open(&remote)
            .unwrap()
            .set_times(FileTimes::new().set_modified(time))
            .unwrap();
        assert_eq!(
            decide(
                Some(&fs::metadata(local).unwrap()),
                &fs::metadata(remote).unwrap()
            ),
            Decision::Install
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn staging_verifies_a_real_executable() {
        let dir = temp_dir("stage");
        let remote = std::env::current_exe().unwrap();
        let staged = dir.join("qm.exe.new");
        let metadata = fs::metadata(&remote).unwrap();
        stage(&remote, &staged, &metadata).unwrap();
        assert_eq!(fs::metadata(staged).unwrap().len(), metadata.len());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn staging_rejects_non_executable_content() {
        let dir = temp_dir("invalid");
        let remote = dir.join("remote.exe");
        let staged = dir.join("qm.exe.new");
        fs::write(&remote, vec![0u8; 128]).unwrap();
        let result = stage(&remote, &staged, &fs::metadata(&remote).unwrap());
        assert!(result.unwrap_err().contains("keine plausible Windows-EXE"));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn first_install_does_not_create_backup() {
        let dir = temp_dir("first");
        let local = dir.join("qm.exe");
        let staged = dir.join("qm.exe.new");
        let old = dir.join("qm.exe.old");
        fs::write(&staged, b"new").unwrap();
        replace(&local, &staged, &old).unwrap();
        assert_eq!(fs::read(local).unwrap(), b"new");
        assert!(!old.exists());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn replacement_keeps_old_version() {
        let dir = temp_dir("replace");
        let local = dir.join("qm.exe");
        let staged = dir.join("qm.exe.new");
        let old = dir.join("qm.exe.old");
        File::create(&local).unwrap().write_all(b"old").unwrap();
        File::create(&staged).unwrap().write_all(b"new").unwrap();
        replace(&local, &staged, &old).unwrap();
        assert_eq!(fs::read(local).unwrap(), b"new");
        assert_eq!(fs::read(old).unwrap(), b"old");
        fs::remove_dir_all(dir).unwrap();
    }
}
