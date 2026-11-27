use std::{
    ffi::c_void,
    fs::File,
    io::{Read, Seek, SeekFrom},
    path::Path,
    ptr,
};

type AlgHandle = *mut c_void;
type HashHandle = *mut c_void;
const BCRYPT_SHA256_ALGORITHM: &[u16] = &[83, 72, 65, 50, 53, 54, 0];

#[link(name = "bcrypt")]
unsafe extern "system" {
    fn BCryptOpenAlgorithmProvider(
        handle: *mut AlgHandle,
        id: *const u16,
        implementation: *const u16,
        flags: u32,
    ) -> i32;
    fn BCryptCreateHash(
        algorithm: AlgHandle,
        hash: *mut HashHandle,
        object: *mut u8,
        object_len: u32,
        secret: *const u8,
        secret_len: u32,
        flags: u32,
    ) -> i32;
    fn BCryptHashData(hash: HashHandle, input: *const u8, input_len: u32, flags: u32) -> i32;
    fn BCryptFinishHash(hash: HashHandle, output: *mut u8, output_len: u32, flags: u32) -> i32;
    fn BCryptDestroyHash(hash: HashHandle) -> i32;
    fn BCryptCloseAlgorithmProvider(algorithm: AlgHandle, flags: u32) -> i32;
}

pub fn sha256(path: &Path) -> Result<[u8; 32], String> {
    let mut algorithm = ptr::null_mut();
    if unsafe {
        BCryptOpenAlgorithmProvider(
            &mut algorithm,
            BCRYPT_SHA256_ALGORITHM.as_ptr(),
            ptr::null(),
            0,
        )
    } < 0
    {
        return Err("Windows SHA-256 konnte nicht initialisiert werden".into());
    }
    let mut hash = ptr::null_mut();
    if unsafe { BCryptCreateHash(algorithm, &mut hash, ptr::null_mut(), 0, ptr::null(), 0, 0) } < 0
    {
        unsafe {
            BCryptCloseAlgorithmProvider(algorithm, 0);
        }
        return Err("Windows SHA-256-Kontext konnte nicht erstellt werden".into());
    }
    let result = (|| {
        let mut file = File::open(path).map_err(|error| error.to_string())?;
        let mut buffer = vec![0u8; 1024 * 1024];
        loop {
            let read = file.read(&mut buffer).map_err(|error| error.to_string())?;
            if read == 0 {
                break;
            }
            if unsafe { BCryptHashData(hash, buffer.as_ptr(), read as u32, 0) } < 0 {
                return Err("SHA-256-Berechnung fehlgeschlagen".into());
            }
        }
        let mut output = [0u8; 32];
        if unsafe { BCryptFinishHash(hash, output.as_mut_ptr(), output.len() as u32, 0) } < 0 {
            return Err("SHA-256-Abschluss fehlgeschlagen".into());
        }
        Ok(output)
    })();
    unsafe {
        BCryptDestroyHash(hash);
        BCryptCloseAlgorithmProvider(algorithm, 0);
    }
    result
}

pub fn plausible_pe(path: &Path) -> Result<bool, String> {
    let mut file = File::open(path).map_err(|error| error.to_string())?;
    let mut dos = [0u8; 64];
    file.read_exact(&mut dos)
        .map_err(|error| error.to_string())?;
    if &dos[..2] != b"MZ" {
        return Ok(false);
    }
    let offset = u32::from_le_bytes(dos[60..64].try_into().unwrap()) as u64;
    file.seek(SeekFrom::Start(offset))
        .map_err(|error| error.to_string())?;
    let mut signature = [0u8; 4];
    file.read_exact(&mut signature)
        .map_err(|error| error.to_string())?;
    Ok(signature == *b"PE\0\0")
}
