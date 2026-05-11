import subprocess
import time

def check_adb_connection(ip_port):
    """Cek apakah ADB terkoneksi ke perangkat tertentu."""
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, check=True
        )
        devices = result.stdout.strip().split('\n')[1:]  # skip header
        for line in devices:
            if ip_port in line and "device" in line:
                return True
        return False
    except Exception as e:
        print(f"Gagal cek ADB devices: {e}")
        return False

def wait_for_device(ip_port, timeout=30):
    """Tunggu hingga perangkat terkoneksi, timeout dalam detik."""
    start = time.time()
    while time.time() - start < timeout:
        if check_adb_connection(ip_port):
            return True
        time.sleep(2)
    return False

def restart_adb_server():
    """Restart ADB server jika bermasalah."""
    subprocess.run(["adb", "kill-server"], capture_output=True)
    time.sleep(2)
    subprocess.run(["adb", "start-server"], capture_output=True)
    time.sleep(2)
    print("ADB server direstart.")