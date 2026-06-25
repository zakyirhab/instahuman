import subprocess

def get_usb_serials():
    """Ambil daftar serial number HP yang terhubung via USB."""
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')[1:]
    serials = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            # Hanya ambil yang serial number (bukan IP:port)
            if ":" not in serial:
                serials.append(serial)
    return serials

def check_wifi_status(serial):
    """Cek status WiFi dan alamat IP perangkat."""
    try:
        # Cek apakah WiFi menyala
        wifi_status = subprocess.run(
            ["adb", "-s", serial, "shell", "dumpsys", "wifi"],
            capture_output=True, text=True, timeout=5
        )
        # Cek IP address di wlan0
        ip_result = subprocess.run(
            ["adb", "-s", serial, "shell", "ip", "addr", "show", "wlan0"],
            capture_output=True, text=True, timeout=5
        )
        ip_output = ip_result.stdout
        
        # Ekstrak IP dari output
        import re
        ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_output)
        ip = ip_match.group(1) if ip_match else "Tidak ada IP"
        
        return ip
    except Exception as e:
        return f"Error: {e}"

def check_port_5555(serial):
    """Cek apakah port 5555 sudah listening."""
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "netstat", "-tln"],
            capture_output=True, text=True, timeout=5
        )
        return ":5555" in result.stdout
    except Exception:
        return False

def ping_device(ip):
    """Coba ping perangkat dari komputer."""
    try:
        result = subprocess.run(
            ["ping", "-n", "2", "-w", "1000", ip],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    print("=== NETWORK CHECK 40 HP ===\n")
    
    serials = get_usb_serials()
    if not serials:
        print("Tidak ada perangkat USB terdeteksi. Pastikan kabel USB terpasang.")
        return
    
    print(f"Ditemukan {len(serials)} perangkat via USB.\n")
    print(f"{'No':<4} {'Serial':<25} {'IP Address':<18} {'Port 5555':<12} {'Ping':<8}")
    print("-" * 70)
    
    # Dapatkan subnet komputer (asumsi semua di jaringan yang sama)
    import socket
    hostname = socket.gethostname()
    computer_ip = socket.gethostbyname(hostname)
    subnet = ".".join(computer_ip.split('.')[:3])
    print(f"Komputer IP: {computer_ip} (subnet {subnet}.x)")
    print("-" * 70)
    
    masalah = []
    berhasil = []
    
    for i, serial in enumerate(serials, 1):
        ip = check_wifi_status(serial)
        port_ok = check_port_5555(serial)
        
        # Cek apakah IP di subnet yang sama dengan komputer
        subnet_ok = ip.startswith(subnet) if ip != "Tidak ada IP" else False
        
        ping_ok = ping_device(ip) if subnet_ok else False
        
        print(f"{i:<4} {serial:<25} {ip:<18} {'✓' if port_ok else '✗':<12} {'✓' if ping_ok else '✗':<8}")
        
        if not subnet_ok:
            masalah.append((serial, ip, "IP berbeda subnet"))
        elif not port_ok:
            masalah.append((serial, ip, "Port 5555 tidak aktif"))
        elif not ping_ok:
            masalah.append((serial, ip, "Ping gagal (mungkin AP Isolation)"))
        else:
            berhasil.append((serial, ip))
    
    print("\n" + "=" * 70)
    print(f"RINGKASAN:")
    print(f"  Berhasil   : {len(berhasil)} perangkat")
    print(f"  Bermasalah : {len(masalah)} perangkat")
    
    if masalah:
        print("\nPerangkat bermasalah:")
        for serial, ip, reason in masalah:
            print(f"  {serial}: {ip} - {reason}")
        
        print("\nKEMUNGKINAN PENYEBAB & SOLUSI:")
        print("1. IP berbeda subnet → HP terhubung ke WiFi yang berbeda.")
        print("   Solusi: Pastikan semua HP & komputer di WiFi yang sama.")
        print("2. Port 5555 tidak aktif → Mode TCP/IP belum berhasil diaktifkan.")
        print("   Solusi: Jalankan ulang 'adb tcpip 5555' via USB untuk HP tersebut.")
        print("3. Ping gagal → AP Isolation di router memblokir komunikasi antar perangkat.")
        print("   Solusi: Buka pengaturan router (192.168.1.1), cari 'AP Isolation' atau")
        print("   'Wireless Isolation' dan MATIKAN fitur tersebut.")

if __name__ == "__main__":
    main()
