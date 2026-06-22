import yaml
import subprocess
import time

def send_verification(ip, device_name):
    """Kirim verifikasi ke HP: notifikasi + toast fallback."""
    title = f"Verifikasi HP"
    message = f"Ini adalah {device_name}"
    
    print(f"  🔔 Mengirim verifikasi ke {device_name} ({ip})...")
    
    # 1. Bangunkan layar
    subprocess.run(["adb", "-s", ip, "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
                   capture_output=True, timeout=3)
    time.sleep(0.5)
    
    # 2. Notifikasi dengan format yang benar
    try:
        result = subprocess.run([
            "adb", "-s", ip, "shell",
            "cmd", "notification", "post",
            "-S", "bigtext",
            "-t", f'"{title}"',
            "tag_verify",
            f'"{message}"'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode != 0:
            raise Exception("cmd notification gagal")
        print(f"  ✅ Notifikasi muncul di {device_name}")
    except Exception:
        # 3. Fallback: Toast via keyboard input
        print(f"  ⚠️ Notifikasi gagal, coba toast...")
        try:
            # Simulasikan toast dengan mengetikkan teks di aplikasi yang terbuka
            subprocess.run(["adb", "-s", ip, "shell", "input", "keyevent", "KEYCODE_HOME"],
                          capture_output=True, timeout=2)
            time.sleep(0.3)
            # Buka aplikasi yang bisa menampilkan toast (kalkulator misalnya)
            subprocess.run(["adb", "-s", ip, "shell", "am", "start", 
                          "-a", "android.intent.action.VIEW",
                          "-d", f"data:text/plain,{message}"],
                          capture_output=True, timeout=3)
            print(f"  ℹ️ Teks ditampilkan di browser {device_name}")
        except Exception as e2:
            print(f"  ❌ Semua metode gagal. Cek manual serial {ip}")

def renew_ip_interactive():
    print("=== RENEW IP INTERAKTIF ===\n")
    
    # Baca config.yaml
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("ERROR: config.yaml tidak ditemukan.")
        return
    
    devices = config.get("devices", [])
    print(f"Membaca {len(devices)} perangkat dari config.yaml\n")

    # Pindai perangkat ADB
    print("Memindai jaringan ADB...")
    result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')[1:]
    
    serial_to_ip = {}
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
                        serial_to_ip[serial] = identifier
                except Exception:
                    pass
    
    print(f"Ditemukan {len(serial_to_ip)} perangkat aktif di jaringan\n")
    print("="*60)

    updated_count = 0
    for dev in devices:
        name = dev.get("name", "Tanpa Nama")
        serial = dev.get("serial", "").strip()
        old_ip = dev.get("ip", "")

        if serial in serial_to_ip:
            new_ip = serial_to_ip[serial]
            if new_ip != old_ip:
                print(f"\n[{name}] IP berubah: {old_ip} -> {new_ip}")
                print(f"  Serial: {serial}")
                
                # Kirim verifikasi ke HP target
                send_verification(new_ip, name)
                
                confirm = input("  Benar HP ini? (y/n): ").strip().lower()
                if confirm == 'y':
                    dev["ip"] = new_ip
                    print(f"  ✅ IP {name} diperbarui.")
                    updated_count += 1
                else:
                    print(f"  ⏩ IP {name} dilewati.")
            else:
                print(f"[{name}] IP tidak berubah.")
        else:
            print(f"[{name}] ⚠️ Serial {serial} tidak ditemukan di jaringan.")

    print("\n" + "="*60)
    
    # Simpan perubahan
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"Selesai. {updated_count} IP berhasil diperbarui.")
    print("config.yaml telah disimpan.")

if __name__ == "__main__":
    renew_ip_interactive()
