import uiautomator2 as u2
import random
import time
import yaml
import logging
import os
import re
import concurrent.futures
from human_behavior import random_sleep
from instagram_actions import (
    check_notifications,
    check_dm,
    dismiss_popups,
    go_home,
    watch_stories,
    interact_feed,
    scroll_reels,
)
from search_actions import (
    search_and_interact,
    explore_and_interact,
    mine_keywords,
    load_keywords,
)
from utils.adb_helper import (
    check_adb_connection,
    restart_adb_server,
    connect_device,
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
    print("5. Search & Interact")
    print("6. Semua (1-5)")
    tasks = input("Masukkan angka: ").strip()
    if '6' in tasks:
        return [1, 2, 3, 4, 5]
    selected = []
    for t in tasks.split(','):
        t = t.strip()
        if t and t in '12345':
            selected.append(int(t))
    return selected


def pilih_search_mode() -> dict:
    """
    Tanya user sub-mode untuk task Search.
    Return dict konfigurasi search.
    """
    print("\n  === KONFIGURASI SEARCH ===")
    print("  Sub-mode:")
    print("  1. Search by keyword (dari bank keyword)")
    print("  2. Explore tanpa keyword")
    print("  3. Mine keyword baru (scan + review)")
    sub = input("  Pilih sub-mode (1/2/3, default 1): ").strip() or "1"

    keyword = None
    if sub == "1":
        bank = load_keywords()
        if bank:
            print(f"  Keyword tersedia: {', '.join(bank)}")
            kw_input = input("  Ketik keyword spesifik (kosongkan = acak dari bank): ").strip()
            keyword = kw_input if kw_input else None
        else:
            print("  Bank keyword kosong, akan pakai explore.")
            sub = "2"

    return {"sub_mode": sub, "keyword": keyword}


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

        search_cfg = {}
        if 5 in tasks:
            search_cfg = pilih_search_mode()

        menit, like, comment, repost, prom, max_likes = 0, 0.0, 0.0, 0.0, 0.2, 0
        if mode == "2":
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
            'search_cfg': search_cfg,
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
    random_sleep(1, 2)
    logger.info("App terbuka dan posisi direset ke Home.")


def jalankan_session(d, device_name, mode: str, tasks: list[int],
                     durasi_total_menit: int = 10,
                     like_prob: float = 0.3,
                     comment_prob: float = 0.03,
                     repost_prob: float = 0.05,
                     promosi_ratio: float = 0.2,
                     max_likes: int = 0,
                     search_cfg: dict = None):
    """Satu sesi untuk satu perangkat (testing/loop)."""
    logger = logging.getLogger(device_name)
    logger.info(f"=== Sesi {device_name} dimulai ===")
    search_cfg = search_cfg or {}

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
        if 5 in tasks:
            _run_search_task(d, search_cfg, duration=60,
                             like_prob=1.0, comment_prob=1.0,
                             repost_prob=1.0, promosi_ratio=promosi_ratio,
                             max_likes=max_likes)

        d.app_stop("com.instagram.android")
        logger.info("Testing selesai.")
        return

    # ---------- MODE LOOP ----------
    logger.info(f"=== LOOP TASK SELAMA {durasi_total_menit} MENIT ===")
    durasi_task = {1: 120, 3: 300, 4: 300, 5: 300}
    cycle_duration = sum(durasi_task[t] for t in tasks if t in durasi_task)
    if cycle_duration == 0:
        cycle_duration = 600

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
        if 5 in tasks:
            _run_search_task(d, search_cfg, duration=durasi_task[5],
                             like_prob=like_prob, comment_prob=comment_prob,
                             repost_prob=repost_prob, promosi_ratio=promosi_ratio,
                             max_likes=max_likes)

        time.sleep(random.uniform(2, 4))
        if time.time() - start_total < total_durasi_detik:
            go_home(d)

    d.app_stop("com.instagram.android")
    logger.info("Durasi total tercapai, loop selesai.")


def _run_search_task(d, search_cfg: dict, duration: int,
                     like_prob: float, comment_prob: float, repost_prob: float,
                     promosi_ratio: float, max_likes: int) -> None:
    """
    Dispatch ke sub-mode search yang sesuai.
    Mine keywords hanya berjalan sekali (bukan loop), lalu lanjut explore.
    """
    sub = search_cfg.get("sub_mode", "1")
    keyword = search_cfg.get("keyword")

    if sub == "3":
        # Mine mode: jalankan 1x, tidak perlu durasi
        mine_keywords(d)
        # Setelah mine, lanjut explore sisa waktu (opsional)
        explore_and_interact(d, duration=max(60, duration // 2),
                             like_prob=like_prob, comment_prob=comment_prob,
                             repost_prob=repost_prob,
                             comment_promosi_ratio=promosi_ratio,
                             max_likes=max_likes)
    elif sub == "2":
        explore_and_interact(d, duration=duration,
                             like_prob=like_prob, comment_prob=comment_prob,
                             repost_prob=repost_prob,
                             comment_promosi_ratio=promosi_ratio,
                             max_likes=max_likes)
    else:
        # sub == "1" — search by keyword (acak dari bank jika keyword=None)
        search_and_interact(d, duration=duration,
                            like_prob=like_prob, comment_prob=comment_prob,
                            repost_prob=repost_prob,
                            comment_promosi_ratio=promosi_ratio,
                            max_likes=max_likes,
                            keyword=keyword)


def run_single_device(device_info, mode, tasks, menit, like, comment,
                      repost, prom, max_likes, search_cfg=None):
    """Thread worker untuk satu perangkat."""
    ip = device_info["ip"]
    nama = device_info.get("name", ip)

    logger_local = logging.getLogger(nama)
    logger_local.setLevel(logging.INFO)
    formatter = logging.Formatter(f"%(asctime)s [%(levelname)s] [{nama}] %(message)s")
    file_handler = logging.FileHandler(f"logs/session_{nama}.log")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger_local.handlers.clear()
    logger_local.addHandler(file_handler)
    logger_local.addHandler(stream_handler)

    logger_local.info(f"Mulai sesi untuk {nama} ({ip})")

    if not check_adb_connection(ip):
        logger_local.warning("ADB tidak terhubung, mencoba connect...")
        connect_device(ip)
        time.sleep(3)
        if not check_adb_connection(ip):
            logger_local.warning("Connect gagal, restart ADB & connect ulang...")
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
        import search_actions as sa
        original_ia = ia.logger
        original_sa = sa.logger
        ia.logger = logger_local
        sa.logger = logger_local
        try:
            jalankan_session(d, nama, mode, tasks, menit, like, comment,
                             repost, prom, max_likes, search_cfg or {})
        finally:
            ia.logger = original_ia
            sa.logger = original_sa

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

    print("\nGunakan pembagian grup khusus? (y/n)")
    if input("> ").strip().lower() == 'y':
        groups = pilih_custom_groups(devices)
        if not groups:
            print("Tidak ada grup dibuat, keluar.")
            return
    else:
        mode = pilih_mode()
        tasks = pilih_task()
        if not tasks:
            print("Tidak ada task yang dipilih.")
            return

        search_cfg = {}
        if 5 in tasks:
            search_cfg = pilih_search_mode()

        menit, like, comment, repost, prom, max_likes = 0, 0.0, 0.0, 0.0, 0.2, 0
        if mode == "2":
            menit, like, comment, repost, prom, max_likes = pilih_params_loop()

        groups = [{
            'devices': devices,
            'mode': mode,
            'tasks': tasks,
            'menit': menit,
            'like_prob': like,
            'comment_prob': comment,
            'repost_prob': repost,
            'promosi_ratio': prom,
            'max_likes': max_likes,
            'search_cfg': search_cfg,
        }]

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
                    group.get('search_cfg', {}),
                )
                all_futures.append(future)

        for future in concurrent.futures.as_completed(all_futures):
            try:
                future.result()
            except Exception as exc:
                logging.error(f"Thread error: {exc}")

    print("\nSemua perangkat selesai.")


if __name__ == "__main__":
    main()
