use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

fn find_rc() -> Option<PathBuf> {
    if let Some(paths) = env::var_os("PATH") {
        for dir in env::split_paths(&paths) {
            let candidate = dir.join("rc.exe");
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    let base = env::var_os("ProgramFiles(x86)")
        .map(PathBuf::from)?
        .join("Windows Kits")
        .join("10")
        .join("bin");
    let arch = match env::var("CARGO_CFG_TARGET_ARCH").as_deref() {
        Ok("x86_64") => "x64",
        Ok("aarch64") => "arm64",
        _ => "x86",
    };
    let mut versions: Vec<_> = fs::read_dir(base)
        .ok()?
        .flatten()
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect();
    versions.sort();
    versions
        .into_iter()
        .rev()
        .map(|version| version.join(arch).join("rc.exe"))
        .find(|path| path.is_file())
}

fn escaped(path: &Path) -> String {
    path.to_string_lossy()
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
}

fn main() {
    println!("cargo:rerun-if-changed=../frontend/qm.ico");
    if env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }
    let manifest = PathBuf::from(env::var_os("CARGO_MANIFEST_DIR").unwrap());
    let icon = manifest.join("..").join("frontend").join("qm.ico");
    assert!(icon.is_file(), "QM-Icon fehlt: {}", icon.display());
    let out = PathBuf::from(env::var_os("OUT_DIR").unwrap());
    let rc_source = out.join("qm-updater.rc");
    let resource = out.join("qm-updater.res");
    fs::write(&rc_source, format!("1 ICON \"{}\"\n", escaped(&icon))).unwrap();
    let rc = find_rc().expect("rc.exe aus dem Windows SDK wurde nicht gefunden");
    let status = Command::new(rc)
        .args(["/nologo", "/fo"])
        .arg(&resource)
        .arg(&rc_source)
        .status()
        .expect("rc.exe konnte nicht gestartet werden");
    assert!(
        status.success(),
        "Windows-Ressource konnte nicht erstellt werden"
    );
    println!("cargo:rustc-link-arg={}", resource.display());
}
