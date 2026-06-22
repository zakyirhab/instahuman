import uiautomator2 as u2
import random
import time
import yaml
import logging
import os
import concurrent.futures
from instagram_actions import (
    check_notifications,
    check_dm,
    watch_stories,
    interact_feed,
    scroll_reels,
    dismiss_popups,
    go_home,
)
from utils.adb_helper import (
    check_adb_connection,
    restart_adb_server,
    connect_device,
    get_device_ip,
)

os.makedirs("logs", exist_ok=True)


def load_config(config_file: str = "config.yaml") -> dict:
    try:
        with open(config_file, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        logging.exception("Gagal baca config")
        return {"devices": []}


def pilih_mode() -> str:
    print("\n=== BOT INSTAGRAM ===")
    print("1. Testing Module")
    print("2. Loop Task")
    pilihan = input("Pilih mode (1/2): ").strip()
    return pilihan


def pilih_task() -> list[int]:
    print("\nPilih task (pisahkan dengan koma):")
    print("1. Notifikasi & DM")
    print("2. Story")
    print("3. Feed")
    print("4. Reels")
    print("5. Boost Comment by Username")
    print("6. Semua (1-4)")
    tasks = input("Masukkan angka: ").strip()
    if '6' in tasks:
        return [1, 2, 3, 4]
    selected = []
    for t in tasks.split(','):
        t = t.strip()
        if t and t in '12345':
            selected.append(int(t))
    return selected


def pilih_params_loop() -> tuple:
    menit = int(input("Durasi total (menit): "))
    like = float(input("Probabilitas Like (0-1, default 0.3): ") or 0.3)
    comment = float(input("Probabilitas Comment (default 0.03): ") or 0.03)
    repost = float(input("Probabilitas Repost (default 0.05): ") or 0.05)
    prom = float(input("Rasio komentar promosi (0-1, default 0.2): ") or 0.2)
    max_likes = int(input("Batas maksimal Like per sesi (0=tidak terbatas): ") or 0)
    return menit, like, comment, repost, prom, max_likes


def parse_indices(raw: str, total_devices: int) -> list[int]:
    indices = set()
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    for part in parts:
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                a, b = int(a), int(b)
                for i in range(a, b + 1):
                    if 1 <= i <= total_devices:
                        indices.add(i)
            except:
                continue
        else:
            try:
                i = int(part)
                if 1 <= i <= total_devices:
                    indices.add(i)
            except:
                continue
    return sorted(indices)


def pilih_custom_groups(devices):
    groups = []
    assigned = set()

    print("\n=== PEMBAGIAN GRUP ===")
    print(f"Total perangkat tersedia: {len(devices)}")
    for idx, dev in enumerate(devices, 1):
        print(f"  {idx}. {dev.get('name', dev['ip'])} ({dev['ip']})")

    while True:
        print("\nMasukkan pilihan HP (contoh: 1-5, 2,4, 'sisa', 'selesai'):")
        raw = input("> ").strip().lower()
        if raw == 'selesai':
            break

        if raw == 'sisa':
            idx_sisa = [i for i in range(1, len(devices) + 1) if i not in assigned]
            if not idx_sisa:
                print("Semua perangkat sudah dibagi.")
                continue
            selected_indices = idx_sisa
        else:
            selected_indices = parse_indices(raw, len(devices))
            if not selected_indices:
                print("Indeks tidak valid.")
                continue

        fresh = [i for i in selected_indices if i not in assigned]
        if not fresh:
            print("Semua perangkat yang dipilih sudah ada di grup lain.")
            continue

        print(f"Perangkat yang akan diatur: {fresh}")
        assigned.update(fresh)

        print("\nPengaturan untuk grup ini:")
        mode = pilih_mode()
        tasks = pilih_task()
        if not tasks:
            print("Task tidak valid, lewati grup ini.")
            assigned.difference_update(fresh)
            continue

        menit, like, comment, repost, prom, max_likes = 0, 0.0, 0.0, 0.0, 0.2, 0
        if mode == "2" and any(t in tasks for t in [1, 2, 3, 4]):
            menit, like, comment, repost, prom, max_likes = pilih_params_loop()

        group = {
            'devices': [devices[i - 1] for i in fresh],
            'mode': mode,
            'tasks': tasks,
            'menit': menit,
            'like_prob': like,
            'comment_prob': comment,
            'repost_prob': repost,
            'promosi_ratio': prom,
            'max_likes': max_likes,
        }
        groups.append(group)
        print(f"Grup berhasil ditambahkan ({len(fresh)} perangkat).")

    return groups


def _app_start_and_reset(d, logger):
    """Buka Instagram dan pastikan posisi awal di Feed (home)."""
    d.app_start("com.instagram.android")
    time.sleep(random.uniform(5, 8))
    dismiss_popups(d)
    go_home(d)
    time.sleep(random.uniform(1, 2))
    logger.info("App terbuka dan posisi direset ke Home.")


def jalankan_session(d, device_name, mode: str, tasks: list[int],
                     durasi_total_menit: int = 10,
                     like_prob: float = 0.3,
                     comment_prob: float = 0.03,
                     repost_prob: float = 0.05,
                     promosi_ratio: float = 0.2,
                     max_likes: int = 0):
    """Satu sesi untuk satu perangkat (testing/loop). Tidak mencakup task 5 (boost)."""
    logger = logging.getLogger(device_name)
    logger.info(f"=== Sesi {device_name} dimulai ===")

    if mode == "1":
        logger.info("=== MODE TESTING ===")
        _app_start_and_reset(d, logger)

        if 1 in tasks:
            check_notifications(d)
            check_dm(d)
        if 2 in tasks:
            watch_stories(d)
        if 3 in tasks:
            interact_feed(d, duration=60, like_prob=1.0, comment_prob=1.0,
                          repost_prob=1.0, comment_promosi_ratio=promosi_ratio)
        if 4 in tasks:
            scroll_reels(d, duration=60, like_prob=1.0, comment_prob=1.0,
                         repost_prob=1.0, comment_promosi_ratio=promosi_ratio)

        d.app_stop("com.instagram.android")
        logger.info("Testing selesai.")
        return

    # ---------- MODE LOOP ----------
    logger.info(f"=== LOOP TASK SELAMA {durasi_total_menit} MENIT ===")
    durasi_task = {1: 120, 3: 300, 4: 300}
    total_durasi_detik = durasi_total_menit * 60
    start_total = time.time()
    iteration = 0

    _app_start_and_reset(d, logger)

    while time.time() - start_total < total_durasi_detik:
        iteration += 1
        logger.info(f"Siklus ke-{iteration}")

        if 1 in tasks:
            check_notifications(d)
            check_dm(d)
            time.sleep(1)
        if 2 in tasks:
            watch_stories(d)
            time.sleep(1)
        if 3 in tasks:
            interact_feed(d, duration=durasi_task[3], like_prob=like_prob,
                          comment_prob=comment_prob, repost_prob=repost_prob,
                          comment_promosi_ratio=promosi_ratio, max_likes=max_likes)
        if 4 in tasks:
            scroll_reels(d, duration=durasi_task[4], like_prob=like_prob,
                         comment_prob=comment_prob, repost_prob=repost_prob,
                         comment_promosi_ratio=promosi_ratio, max_likes=max_likes)

        time.sleep(random.uniform(2, 4))
        if time.time() - start_total < total_durasi_detik:
            go_home(d)

    d.app_stop("com.instagram.android")
    logger.info("Durasi total tercapai, loop selesai.")


def _connect_all_devices(devices: list) -> list:
    """
    Koneksi ADB + UIAutomator2 untuk semua device.
    Return list of (d, name) yang berhasil terkoneksi.
    """
    connected = []
    for device_info in devices:
        ip = device_info["ip"]
        nama = device_info.get("name", ip)
        logger_local = logging.getLogger(nama)

        # ─── Auto-deteksi IP berdasarkan serial ───
        serial = device_info.get("serial", "").strip()
        if serial:
            detected_ip = get_device_ip(serial)
            if detected_ip:
                if detected_ip != ip:
                    logger_local.info(f"IP diperbarui: {ip} → {detected_ip} (via serial)")
                    ip = detected_ip
            else:
                logger_local.warning(f"Serial {serial} tidak ditemukan di jaringan, pakai IP lama.")
        # ───────────────────────────────────────────

        if not check_adb_connection(ip):
            logger_local.warning(f"[{nama}] ADB tidak terhubung, mencoba connect...")
            connect_device(ip)
            time.sleep(3)
            if not check_adb_connection(ip):
                restart_adb_server()
                time.sleep(2)
                connect_device(ip)
                time.sleep(5)
                if not check_adb_connection(ip):
                    logger_local.error(f"[{nama}] Gagal koneksi, lewati.")
                    continue

        try:
            d = u2.connect(ip)
            if not d.info:
                logger_local.error(f"[{nama}] Gagal koneksi UIAutomator2.")
                continue
            connected.append((d, nama))
            logger_local.info(f"[{nama}] Terkoneksi.")
        except Exception:
            logger_local.exception(f"[{nama}] Error koneksi")

    return connected


def run_single_device(device_info, mode, tasks, menit, like, comment, repost, prom, max_likes):
    """Thread worker untuk satu perangkat (task 1-4)."""
    ip = device_info["ip"]
    nama = device_info.get("name", ip)

    logger_local = logging.getLogger(nama)
    logger_local.setLevel(logging.INFO)
    formatter = logging.Formatter(f"%(asctime)s [%(levelname)s] [{nama}] %(message)s")
    fh = logging.FileHandler(f"logs/session_{nama}.log")
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger_local.handlers.clear()
    logger_local.addHandler(fh)
    logger_local.addHandler(sh)

    logger_local.info(f"Mulai sesi untuk {nama} ({ip})")

    # ─── Auto-deteksi IP berdasarkan serial ───
    serial = device_info.get("serial", "").strip()
    if serial:
        detected_ip = get_device_ip(serial)
        if detected_ip:
            if detected_ip != ip:
                logger_local.info(f"IP diperbarui: {ip} → {detected_ip} (via serial)")
                ip = detected_ip
        else:
            logger_local.warning(f"Serial {serial} tidak ditemukan di jaringan, pakai IP lama.")
    # ───────────────────────────────────────────

    if not check_adb_connection(ip):
        logger_local.warning("ADB tidak terhubung, mencoba connect...")
        connect_device(ip)
        time.sleep(3)
        if not check_adb_connection(ip):
            restart_adb_server()
            time.sleep(2)
            connect_device(ip)
            time.sleep(5)
            if not check_adb_connection(ip):
                logger_local.error("Gagal koneksi setelah restart, lewati.")
                return

    try:
        d = u2.connect(ip)
        if not d.info:
            logger_local.error("Gagal koneksi UIAutomator2.")
            return

        import instagram_actions as ia
        original_logger = ia.logger
        ia.logger = logger_local
        try:
            jalankan_session(d, nama, mode, tasks, menit, like,
                             comment, repost, prom, max_likes)
        finally:
            ia.logger = original_logger

    except Exception:
        logger_local.exception(f"Error di {nama}")
    finally:
        logger_local.info("Sesi selesai.")
        

def main() -> None:
    config = load_config()
    devices = config.get("devices", [])
    if not devices:
        logging.warning("Tidak ada perangkat di config.yaml.")
        return

    # Cek apakah task 5 (boost) dipilih di level global
    print("\nGunakan pembagian grup khusus? (y/n)")
    use_groups = input("> ").strip().lower() == 'y'

    if use_groups:
        groups = pilih_custom_groups(devices)
        if not groups:
            print("Tidak ada grup dibuat, keluar.")
            return

        # Cek apakah ada grup dengan task boost
        boost_groups = [g for g in groups if 5 in g['tasks']]
        normal_groups = [g for g in groups if 5 not in g['tasks']]

        # Jalankan normal groups paralel
        if normal_groups:
            _run_normal_groups(normal_groups)

        # Jalankan boost groups (ambil semua device-nya)
        if boost_groups:
            boost_devices = []
            for g in boost_groups:
                boost_devices.extend(g['devices'])
            _run_boost_mode(boost_devices)

    else:
        tasks = pilih_task()
        if not tasks:
            print("Tidak ada task yang dipilih.")
            return

        if tasks == [5]:
            # Pure boost mode
            _run_boost_mode(devices)
            return

        if 5 in tasks:
            # Mixed: boost + task lain tidak didukung di mode global
            # Pisahkan: jalankan task normal dulu, lalu boost
            print("\n[INFO] Task Boost dijalankan terpisah setelah task lain selesai.")
            normal_tasks = [t for t in tasks if t != 5]
            if normal_tasks:
                mode = pilih_mode()
                menit, like, comment, repost, prom, max_likes = 0, 0.0, 0.0, 0.0, 0.2, 0
                if mode == "2":
                    menit, like, comment, repost, prom, max_likes = pilih_params_loop()
                groups = [{'devices': devices, 'mode': mode, 'tasks': normal_tasks,
                           'menit': menit, 'like_prob': like, 'comment_prob': comment,
                           'repost_prob': repost, 'promosi_ratio': prom, 'max_likes': max_likes}]
                _run_normal_groups(groups)
            _run_boost_mode(devices)
            return

        # Task normal saja
        mode = pilih_mode()
        menit, like, comment, repost, prom, max_likes = 0, 0.0, 0.0, 0.0, 0.2, 0
        if mode == "2":
            menit, like, comment, repost, prom, max_likes = pilih_params_loop()
        groups = [{'devices': devices, 'mode': mode, 'tasks': tasks,
                   'menit': menit, 'like_prob': like, 'comment_prob': comment,
                   'repost_prob': repost, 'promosi_ratio': prom, 'max_likes': max_likes}]
        _run_normal_groups(groups)

    print("\nSemua perangkat selesai.")


def _run_normal_groups(groups: list):
    """Jalankan semua grup task normal (1-4) secara paralel."""
    all_futures = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=sum(len(g['devices']) for g in groups)
    ) as executor:
        for group in groups:
            for dev in group['devices']:
                future = executor.submit(
                    run_single_device,
                    dev,
                    group['mode'],
                    group['tasks'],
                    group['menit'],
                    group['like_prob'],
                    group['comment_prob'],
                    group['repost_prob'],
                    group['promosi_ratio'],
                    group['max_likes'],
                )
                all_futures.append(future)

        for future in concurrent.futures.as_completed(all_futures):
            try:
                future.result()
            except Exception as exc:
                logging.error(f"Thread error: {exc}")


def _run_boost_mode(devices: list):
    """Setup logger per device lalu jalankan boost session."""
    from boost_comment import setup_boost_session, run_boost_session
    import instagram_actions as ia

    # Setup logger per device sebelum koneksi
    for device_info in devices:
        nama = device_info.get("name", device_info["ip"])
        logger_local = logging.getLogger(nama)
        logger_local.setLevel(logging.INFO)
        formatter = logging.Formatter(f"%(asctime)s [%(levelname)s] [{nama}] %(message)s")
        fh = logging.FileHandler(f"logs/session_{nama}.log")
        fh.setFormatter(formatter)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger_local.handlers.clear()
        logger_local.addHandler(fh)
        logger_local.addHandler(sh)

    # Konfigurasi boost dari user
    cfg = setup_boost_session()
    if not cfg:
        return

    # Koneksi semua device
    print(f"\n[BOOST] Menghubungkan {len(devices)} perangkat...")
    connected = _connect_all_devices(devices)
    if not connected:
        print("[BOOST] Tidak ada perangkat yang terkoneksi.")
        return

    # Override logger instagram_actions per device dihandle di dalam DeviceWorker
    run_boost_session(connected, cfg)


if __name__ == "__main__":
    main()
