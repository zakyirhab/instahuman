import subprocess
import time
import os
import shutil
import logging

logger = logging.getLogger(__name__)

def _find_adb_path() -> str:
    adb = shutil.which("adb")
    if adb and os.path.isfile(adb):
        return adb
    common = [
        r"C:\adb\adb.exe",
        r"C:\platform-tools\adb.exe",
        os.path.expanduser(r"~\adb\adb.exe"),
    ]
    for path in common:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("adb.exe tidak ditemukan. Pastikan C:\\adb\\adb.exe ada atau tambahkan ke PATH.")

def _run_adb_raw(args: list[str]) -> subprocess.CompletedProcess:
    """Jalankan perintah ADB, kembalikan CompletedProcess tanpa raise error."""
    adb_path = _find_adb_path()
    full_cmd = [adb_path] + args
    return subprocess.run(full_cmd, capture_output=True, text=True)

def check_adb_connection(ip_port: str) -> bool:
    try:
        result = _run_adb_raw(["devices"])
        lines = result.stdout.strip().split('\n')[1:]
        for line in lines:
            if ip_port in line and "device" in line:
                return True
        return False
    except Exception:
        logger.exception("Gagal cek ADB devices")
        return False

def connect_device(ip_port: str) -> bool:
    """Sambungkan ADB ke perangkat tertentu. True jika berhasil."""
    try:
        res = _run_adb_raw(["connect", ip_port])
        logger.info(f"ADB connect {ip_port}: {res.stdout.strip()}")
        return "connected" in res.stdout.lower()
    except Exception:
        logger.exception("Gagal connect ADB")
        return False

def wait_for_device(ip_port: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if check_adb_connection(ip_port):
            return True
        time.sleep(2)
    return False

def restart_adb_server() -> None:
    try:
        _run_adb_raw(["kill-server"])
    except:
        pass
    time.sleep(2)
    _run_adb_raw(["start-server"])
    time.sleep(2)
    logger.info("ADB server direstart.")
