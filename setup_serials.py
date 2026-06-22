import yaml
import subprocess
import time

def get_serial(ip):
    """Dapatkan serial number dari perangkat dengan IP tertentu."""
    try:
        # Pastikan perangkat terhubung
        subprocess.run(["adb", "connect", ip], capture_output=True, text=True)
        time.sleep(1)
        result = subprocess.run(
            ["adb", "-s", ip, "shell", "getprop", "ro.serialno"],
            capture_output=True,
            text=True,
            timeout=10
        )
        serial = result.stdout.strip()
        if serial:
            return serial
        else:
            return "TIDAK_DITEMUKAN"
    except Exception as e:
        return f"ERROR: {e}"

def main():
    # Baca config.yaml
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    devices = config.get("devices", [])
    updated_devices = []
    
    print("=== SETUP SERIAL NUMBER ===")
    for dev in devices:
        name = dev.get("name", "Tanpa Nama")
        ip = dev.get("ip", "")
        print(f"\nMemproses {name} ({ip})...")
        
        serial = get_serial(ip)
        print(f"  Serial: {serial}")
        
        dev["serial"] = serial
        updated_devices.append(dev)
    
    # Simpan kembali ke config.yaml
    config["devices"] = updated_devices
    with open("config.yaml", "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print("\n=== SELESAI ===")
    print("config.yaml telah diperbarui dengan serial number.")

if __name__ == "__main__":
    main()
