import uiautomator2 as u2
import random
import time
import yaml
import logging
import os
from instagram_actions import (
    check_notifications,
    check_dm,
    watch_stories,
    interact_feed,
    scroll_reels,
)

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/session.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def load_config(config_file: str = "config.yaml") -> dict:
    try:
        with open(config_file, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        logger.exception("Gagal baca config")
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
    print("5. Semua")
    tasks = input("Masukkan angka: ").strip()
    if '5' in tasks:
        return [1, 2, 3, 4]
    selected = []
    for t in tasks.split(','):
        t = t.strip()
        if t and t in '1234':
            selected.append(int(t))
    return selected


def jalankan_session(d, mode: str, tasks: list[int],
                     durasi_total_menit: int = 10,
                     like_prob: float = 0.3,
                     comment_prob: float = 0.03,
                     repost_prob: float = 0.05,
                     promosi_ratio: float = 0.2):
    if mode == "1":
        logger.info("=== MODE TESTING ===")
        d.app_start("com.instagram.android")
        time.sleep(random.uniform(5, 8))
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

    # Loop Task
    logger.info(f"=== LOOP TASK SELAMA {durasi_total_menit} MENIT ===")
    durasi_task = {
        1: 120,   # notif+DM
        3: 300,   # feed
        4: 300,   # reels
    }
    # Hitung durasi siklus hanya untuk task yang punya durasi (bukan story)
    cycle_duration = sum(durasi_task[t] for t in tasks if t in durasi_task)
    if cycle_duration == 0:
        # Semua task tidak punya durasi (misal hanya story), pakai fallback 10 menit
        cycle_duration = 600

    total_durasi_detik = durasi_total_menit * 60
    start_total = time.time()
    iteration = 0

    while time.time() - start_total < total_durasi_detik:
        iteration += 1
        logger.info(f"Siklus ke-{iteration}")
        d.app_start("com.instagram.android")
        time.sleep(random.uniform(5, 8))

        if 1 in tasks:
            check_notifications(d)
            check_dm(d)
            time.sleep(1)
        if 2 in tasks:
            watch_stories(d)
            time.sleep(1)
        if 3 in tasks:
            dur = durasi_task[3]
            interact_feed(d, duration=dur, like_prob=like_prob,
                         comment_prob=comment_prob,
                         repost_prob=repost_prob,
                         comment_promosi_ratio=promosi_ratio)
        if 4 in tasks:
            dur = durasi_task[4]
            scroll_reels(d, duration=dur, like_prob=like_prob,
                        comment_prob=comment_prob,
                        repost_prob=repost_prob,
                        comment_promosi_ratio=promosi_ratio)

        d.app_stop("com.instagram.android")
        time.sleep(random.uniform(3, 6))
        if time.time() - start_total >= total_durasi_detik:
            break

    logger.info("Durasi total tercapai, loop selesai.")


def main() -> None:
    config = load_config()
    devices = config.get("devices", [])
    if not devices:
        logger.warning("Tidak ada perangkat di config.yaml.")
        return

    mode = pilih_mode()
    tasks = pilih_task()
    if not tasks:
        print("Tidak ada task yang dipilih.")
        return

    if mode == "2":
        menit = int(input("Durasi total (menit): "))
        like = float(input("Probabilitas Like (0-1, default 0.3): ") or 0.3)
        comment = float(input("Probabilitas Comment (default 0.03): ") or 0.03)
        repost = float(input("Probabilitas Repost (default 0.05): ") or 0.05)
        prom = float(input("Rasio komentar promosi (0-1, default 0.2): ") or 0.2)
    else:
        menit = 0
        like = comment = repost = 0.0
        prom = 0.2

    for dev in devices:
        ip = dev["ip"]
        nama = dev.get("name", ip)
        logger.info(f"Koneksi ke {nama} ({ip})")
        try:
            d = u2.connect(ip)
            if not d.info:
                logger.error(f"Gagal koneksi {ip}")
                continue
            if mode == "1":
                jalankan_session(d, mode, tasks)
            else:
                jalankan_session(d, mode, tasks, menit, like, comment, repost, prom)
        except Exception:
            logger.exception(f"Error di {nama}")
        finally:
            time.sleep(random.uniform(10, 30))


if __name__ == "__main__":
    main()
