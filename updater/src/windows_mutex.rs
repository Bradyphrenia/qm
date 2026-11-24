use std::{
    ffi::c_void,
    os::windows::ffi::OsStringExt,
    path::{Path, PathBuf},
    ptr,
};

type Handle = *mut c_void;
const ERROR_ALREADY_EXISTS: u32 = 183;
const SYNCHRONIZE: u32 = 0x0010_0000;
const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;
const TH32CS_SNAPPROCESS: u32 = 0x0000_0002;
const INVALID_HANDLE_VALUE: Handle = -1isize as Handle;

#[repr(C)]
struct ProcessEntry32W {
    size: u32,
    usage: u32,
    process_id: u32,
    default_heap: usize,
    module_id: u32,
    threads: u32,
    parent_process_id: u32,
    priority: i32,
    flags: u32,
    exe_file: [u16; 260],
}

#[link(name = "kernel32")]
unsafe extern "system" {
    fn CreateMutexW(attributes: *mut c_void, initial_owner: i32, name: *const u16) -> Handle;
    fn OpenMutexW(access: u32, inherit: i32, name: *const u16) -> Handle;
    fn GetLastError() -> u32;
    fn CloseHandle(handle: Handle) -> i32;
    fn CreateToolhelp32Snapshot(flags: u32, process_id: u32) -> Handle;
    fn Process32FirstW(snapshot: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn Process32NextW(snapshot: Handle, entry: *mut ProcessEntry32W) -> i32;
    fn OpenProcess(access: u32, inherit: i32, process_id: u32) -> Handle;
    fn QueryFullProcessImageNameW(
        process: Handle,
        flags: u32,
        path: *mut u16,
        size: *mut u32,
    ) -> i32;
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(Some(0)).collect()
}

pub struct NamedMutex(Handle);

impl NamedMutex {
    pub fn acquire(name: &str) -> Result<Option<Self>, String> {
        let handle = unsafe { CreateMutexW(ptr::null_mut(), 0, wide(name).as_ptr()) };
        if handle.is_null() {
            return Err(std::io::Error::last_os_error().to_string());
        }
        if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
            unsafe {
                CloseHandle(handle);
            }
            return Ok(None);
        }
        Ok(Some(Self(handle)))
    }
}

impl Drop for NamedMutex {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}

pub fn mutex_exists(name: &str) -> bool {
    let handle = unsafe { OpenMutexW(SYNCHRONIZE, 0, wide(name).as_ptr()) };
    if handle.is_null() {
        false
    } else {
        unsafe {
            CloseHandle(handle);
        }
        true
    }
}

pub fn process_at_path_exists(expected: &Path) -> bool {
    let expected = canonical_lower(expected);
    let snapshot = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
    if snapshot == INVALID_HANDLE_VALUE {
        return false;
    }
    let mut entry: ProcessEntry32W = unsafe { std::mem::zeroed() };
    entry.size = std::mem::size_of::<ProcessEntry32W>() as u32;
    let mut found = false;
    let mut ok = unsafe { Process32FirstW(snapshot, &mut entry) };
    while ok != 0 && !found {
        let process =
            unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, entry.process_id) };
        if !process.is_null() {
            let mut buffer = [0u16; 32768];
            let mut length = buffer.len() as u32;
            if unsafe { QueryFullProcessImageNameW(process, 0, buffer.as_mut_ptr(), &mut length) }
                != 0
            {
                let actual =
                    PathBuf::from(std::ffi::OsString::from_wide(&buffer[..length as usize]));
                found = canonical_lower(&actual) == expected;
            }
            unsafe {
                CloseHandle(process);
            }
        }
        ok = unsafe { Process32NextW(snapshot, &mut entry) };
    }
    unsafe {
        CloseHandle(snapshot);
    }
    found
}

fn canonical_lower(path: &Path) -> String {
    path.canonicalize()
        .unwrap_or_else(|_| path.to_path_buf())
        .to_string_lossy()
        .to_lowercase()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn named_mutex_blocks_a_second_owner() {
        let name = format!(r"Local\QMDesktop-Updater-Test-{}", std::process::id());
        let first = NamedMutex::acquire(&name).unwrap().unwrap();
        assert!(mutex_exists(&name));
        assert!(NamedMutex::acquire(&name).unwrap().is_none());
        drop(first);
        assert!(NamedMutex::acquire(&name).unwrap().is_some());
    }

    #[test]
    fn process_lookup_finds_the_test_executable() {
        assert!(process_at_path_exists(&std::env::current_exe().unwrap()));
    }
}
