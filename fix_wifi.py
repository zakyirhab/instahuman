import yaml
import subprocess
import time

def try_reconnect(ip):
    """Coba sambungkan ADB ke IP, return True jika berhasil."""
    result = subprocess.run(["adb", "connect", ip], capture_output=True, text=True)
    return "connected" in result.stdout.lower() or "already connected" in result.stdout.lower()

def activate_tcpip(ip):
    """Aktifkan mode TCP/IP pada perangkat yang terhubung."""
    try:
        subprocess.run(["adb", "-s", ip, "tcpip", "5555"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False

def main():
    print("=== PEMULIHAN OTOMATIS ADB WIFI ===\n")
    
    # Baca config.yaml
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    devices = config.get("devices", [])
    
    # Pindai perangkat yang sudah online
    result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')[1:]
    
    online_serials = set()
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            identifier = parts[0]
            if ":" in identifier and "." in identifier:
                try:
                    serial_result = subprocess.run(
                        ["adb", "-s", identifier, "shell", "getprop", "ro.serialno"],
                        capture_output=True, text=True, timeout=5
                    )
                    serial = serial_result.stdout.strip()
                    if serial:
                        online_serials.add(serial)
                except Exception:
                    pass
    
    print(f"Perangkat online: {len(online_serials)}")
    
    # Cari perangkat yang tidak online dan coba pulihkan
    recovered = 0
    for dev in devices:
        name = dev.get("name", "Tanpa Nama")
        serial = dev.get("serial", "").strip()
        old_ip = dev.get("ip", "")
        
        if serial in online_serials:
            continue  # Sudah online, lewati
        
        print(f"\n[{name}] Serial {serial} tidak online. Mencoba pemulihan...")
        
        # Coba connect ke IP lama
        if not old_ip:
            print(f"  Tidak ada IP lama, lewati.")
            continue
        
        print(f"  Menghubungi {old_ip}...")
        if try_reconnect(old_ip):
            print(f"  Terhubung! Mengaktifkan mode TCP/IP...")
            if activate_tcpip(old_ip):
                print(f"  ✅ TCP/IP diaktifkan. Tunggu 3 detik...")
                time.sleep(3)
                # Putuskan dan sambungkan ulang agar IP baru terdeteksi
                subprocess.run(["adb", "disconnect", old_ip], capture_output=True)
                time.sleep(1)
                try_reconnect(old_ip)
                recovered += 1
            else:
                print(f"  ❌ Gagal mengaktifkan TCP/IP.")
        else:
            print(f"  ❌ Tidak bisa menghubungi IP lama. Mungkin HP mati atau WiFi berubah.")
    
    print(f"\n=== SELESAI ===")
    print(f"Berhasil memulihkan {recovered} perangkat.")
    print(f"Jalankan 'python renew_ip.py' untuk memperbarui IP.")

if __name__ == "__main__":
    main()
