import random
import time
import threading
import queue
import logging
import os
import datetime
from contextlib import contextmanager
 
from human_behavior import random_sleep, human_swipe, RESOURCE_IDS
from instagram_actions import (
    dismiss_popups,
    go_home,
    back_to_feed,
    post_comment,
    get_post_username,
    get_post_caption,
)
from comment_bank import COMMENTS_NATURAL, COMMENTS_PROMOSI
 
# ── Setup logger boost_queue ─────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
 
boost_logger = logging.getLogger("boost_queue")
boost_logger.setLevel(logging.INFO)
_bq_handler = logging.FileHandler("logs/boost_queue.log", encoding="utf-8")
_bq_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
boost_logger.addHandler(_bq_handler)
# Juga ke terminal tapi dengan prefix khusus
_bq_stream = logging.StreamHandler()
_bq_stream.setFormatter(logging.Formatter("%(asctime)s [BOOST] %(message)s"))
boost_logger.addHandler(_bq_stream)
boost_logger.propagate = False
 
 
# ── Dataclass sederhana ──────────────────────────────────────────────────────
class QueueItem:
    """Satu item antrian: satu HP yang menemukan target."""
    def __init__(self, worker, caption: str, screenshot_path: str):
        self.worker = worker          # DeviceWorker instance
        self.caption = caption
        self.screenshot_path = screenshot_path
        self.resume_event = threading.Event()   # set() oleh thread pelayan
        self.chosen_bank = None                 # diisi oleh thread pelayan
        self.action = None                      # "comment" | "skip"
        self.found_at = time.time()
 
 
class ScheduledBoost:
    """Satu jadwal komentar untuk satu HP."""
    def __init__(self, execute_at: float, bank_name: str,
                 bank_comments: list, caption_key: str):
        self.execute_at = execute_at
        self.bank_name = bank_name
        self.bank_comments = bank_comments
        self.caption_key = caption_key
 
 
# ── DeviceWorker ─────────────────────────────────────────────────────────────
class DeviceWorker:
    """
    Satu instance per HP.
    Mengelola state patroli, processed_posts, busy flag, dan jadwal boost.
    """
    def __init__(self, d, device_name: str, target_username: str,
                 pending_queue: queue.Queue, session_end_time: float,
                 max_comment_per_post: int = 5):
        self.d = d
        self.name = device_name
        self.target_username = target_username.lower().lstrip("@")
        self.pending_queue = pending_queue
        self.session_end_time = session_end_time
        self.max_comment_per_post = max_comment_per_post
 
        # processed_posts: key → "pending"|"skip"|"timeout"|"done"
        self.processed_posts: dict[str, str] = {}
 
        # Busy flag
        self._lock = threading.RLock()
        self._busy = False
 
        # Jadwal boost yang menunggu eksekusi
        self.scheduled_boost: ScheduledBoost | None = None
        self._sched_lock = threading.Lock()
 
        # Logger per device (akan di-set dari luar)
        self.logger = logging.getLogger(device_name)
 
        # Stop signal
        self.stop_event = threading.Event()
 
    @property
    def is_busy(self) -> bool:
        with self._lock:
            return self._busy
 
    @contextmanager
    def busy_context(self):
        with self._lock:
            self._busy = True
        try:
            yield
        finally:
            with self._lock:
                self._busy = False
 
    def caption_key(self, caption: str) -> str:
        return f"{self.target_username}:{caption.strip()[:60].lower()}"
 
    def run(self):
        """Main loop patroli. Dipanggil oleh thread worker."""
        self.logger.info(f"[{self.name}] Mulai patroli boost @{self.target_username}")
        while not self.stop_event.is_set():
            if time.time() >= self.session_end_time:
                self.logger.info(f"[{self.name}] Durasi habis, stop patroli.")
                break
            try:
                self._check_scheduled_boost()
                self._patrol_once()
            except Exception:
                self.logger.exception(f"[{self.name}] Error di patrol loop")
                random_sleep(1, 2)
 
    def _check_scheduled_boost(self):
        """Cek apakah ada jadwal boost yang sudah tiba waktunya."""
        with self._sched_lock:
            sched = self.scheduled_boost
            if sched is None:
                return
            if time.time() < sched.execute_at:
                return
            # Durasi sesi sudah habis — batalkan
            if time.time() >= self.session_end_time:
                boost_logger.info(f"[{self.name}] Jadwal dibatalkan (sesi habis): {sched.caption_key}")
                self.scheduled_boost = None
                return
            # HP sedang busy — tunda 30-60 detik
            if self.is_busy:
                delay = random.uniform(30, 60)
                sched.execute_at += delay
                self.logger.info(f"[{self.name}] HP busy, tunda boost {delay:.0f}s")
                return
            # Eksekusi!
            boost = sched
            self.scheduled_boost = None
 
        self._execute_boost(boost)
 
    def _execute_boost(self, boost: ScheduledBoost):
        """Buka feed, temukan postingan target, tulis komentar."""
        self.logger.info(f"[{self.name}] Eksekusi boost: bank={boost.bank_name}")
        boost_logger.info(f"[{self.name}] EKSEKUSI bank={boost.bank_name} caption={boost.caption_key[:40]}")
 
        with self.busy_context():
            try:
                # Pastikan di feed
                go_home(self.d)
                random_sleep(1, 2)
 
                # Cari postingan target di feed (scroll max 20x)
                found = False
                for _ in range(20):
                    uname = get_post_username(self.d)
                    caption = get_post_caption(self.d)
                    if (uname and uname.lower() == self.target_username and
                            self.caption_key(caption) == boost.caption_key):
                        found = True
                        break
                    human_swipe(self.d, 'up', speed='fast')
                    random_sleep(0.5, 1.2)
 
                if not found:
                    self.logger.warning(f"[{self.name}] Postingan target tidak ditemukan saat eksekusi.")
                    boost_logger.info(f"[{self.name}] GAGAL (tidak ditemukan): {boost.caption_key[:40]}")
                    # Tandai done supaya tidak coba lagi
                    self.processed_posts[boost.caption_key] = "done"
                    return
 
                # Eksekusi komentar
                comment = random.choice(boost.bank_comments)
                post_comment(self.d, is_reel=False,
                             comment_promosi_ratio=0.0,
                             forced_comment=comment)
 
                self.processed_posts[boost.caption_key] = "done"
                boost_logger.info(f"[{self.name}] SELESAI komentar: {comment[:50]}")
                self.logger.info(f"[{self.name}] Boost komentar terkirim.")
 
            except Exception:
                self.logger.exception(f"[{self.name}] Error eksekusi boost")
                boost_logger.info(f"[{self.name}] ERROR saat eksekusi: {boost.caption_key[:40]}")
 
    def _patrol_once(self):
        """Satu iterasi patroli feed."""
        dismiss_popups(self.d)
 
        # Scroll
        for _ in range(random.randint(1, 3)):
            human_swipe(self.d, 'up', speed='fast')
            random_sleep(0.5, 1.5)
 
        # Skip iklan
        if self.d(resourceId="com.instagram.android:id/cta_container").exists:
            human_swipe(self.d, 'up', speed='fast')
            random_sleep(0.3, 0.7)
            return
 
        # Baca username di postingan ini
        uname = get_post_username(self.d)
        if not uname:
            return
 
        if uname.lower() != self.target_username:
            return
 
        # Target ditemukan!
        caption = get_post_caption(self.d)
        key = self.caption_key(caption)
 
        # Sudah pernah diproses?
        if key in self.processed_posts:
            status = self.processed_posts[key]
            self.logger.info(f"[{self.name}] Target sudah diproses ({status}), skip.")
            human_swipe(self.d, 'up', speed='fast')
            return
 
        self.logger.info(f"[{self.name}] TARGET DITEMUKAN: @{uname}")
        boost_logger.info(f"[{self.name}] DITEMUKAN @{uname} | caption: {caption[:50]}")
 
        # Like otomatis
        with self.busy_context():
            like_btn = self.d(resourceId=RESOURCE_IDS["FEED_LIKE"])
            if like_btn.exists:
                like_btn.click()
                self.logger.info(f"[{self.name}] Like otomatis.")
                random_sleep(0.3, 0.7)
 
            # Screenshot
            os.makedirs("screenshots", exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_path = f"screenshots/boost_{self.name}_{ts}.png"
            self.d.screenshot(ss_path)
            self.logger.info(f"[{self.name}] Screenshot: {ss_path}")
 
        # Tandai pending & masuk antrian
        self.processed_posts[key] = "pending"
        item = QueueItem(worker=self, caption=caption, screenshot_path=ss_path)
        self.pending_queue.put(item)
        boost_logger.info(f"[{self.name}] MASUK ANTRIAN | key={key[:40]}")
 
        # Pause tunggu keputusan dari thread pelayan (max 5 menit)
        resolved = item.resume_event.wait(timeout=300)
        if not resolved:
            # Timeout
            self.processed_posts[key] = "timeout"
            boost_logger.info(f"[{self.name}] TIMEOUT antrian, lanjut patroli.")
            self.logger.warning(f"[{self.name}] Antrian timeout, lanjut patroli.")
 
 
# ── Thread pelayan (interactive) ─────────────────────────────────────────────
 
def caption_key_str(target_username: str, caption: str) -> str:
    return f"{target_username.lower()}:{caption.strip()[:60].lower()}"
 
 
def _grouping_window(pending_queue: queue.Queue,
                     first_item: QueueItem,
                     target_username: str,
                     base_window: float = 35.0,
                     max_window: float = 60.0) -> list[QueueItem]:
    """
    Tunggu base_window detik setelah item pertama masuk.
    Setiap HP baru yang masuk dengan caption sama → perpanjang 10 detik (maks max_window total).
    Item caption berbeda dikembalikan ke antrian.
    """
    key = caption_key_str(target_username, first_item.caption)
    group = [first_item]
    deadline = time.time() + base_window
    max_deadline = time.time() + max_window
 
    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            item = pending_queue.get(timeout=min(remaining, 1.0))
            item_key = caption_key_str(target_username, item.caption)
            if item_key == key:
                group.append(item)
                # Perpanjang window 10 detik, tapi tidak melebihi max_deadline
                deadline = min(deadline + 10, max_deadline)
                boost_logger.info(f"[{item.worker.name}] Masuk kelompok (total: {len(group)} HP)")
            else:
                # Caption berbeda — kembalikan ke antrian
                pending_queue.put(item)
        except queue.Empty:
            pass
 
    return group
 
 
def _build_bank_menu(available_banks: dict) -> str:
    """Render menu pilihan bank komentar."""
    lines = []
    for idx, (name, comments) in enumerate(available_banks.items(), 1):
        sample = comments[0][:50] if comments else "-"
        lines.append(f"  {idx}. {name:<20} → \"{sample}...\"")
    return "\n".join(lines)
 
 
def serve_queue(pending_queue: queue.Queue,
                available_banks: dict,
                target_username: str,
                session_end_time: float,
                comment_delay_range: tuple = (300, 420),
                max_comment_per_post: int = 5):
    """
    Thread utama yang melayani antrian secara interaktif.
    Dipanggil dari main thread (bukan di thread terpisah) agar bisa input().
    """
    boost_logger.info("Thread pelayan mulai.")
    stats = {"found": 0, "commented": 0, "skipped": 0, "timeout": 0, "cancelled": 0}
 
    # Track berapa HP sudah komentar per caption_key
    comment_count_per_post: dict[str, int] = {}
 
    while time.time() < session_end_time:
        try:
            first_item = pending_queue.get(timeout=2.0)
        except queue.Empty:
            continue
 
        stats["found"] += 1
        key = caption_key_str(target_username, first_item.caption)
 
        # Cek apakah post ini sudah dapat terlalu banyak komentar
        if comment_count_per_post.get(key, 0) >= max_comment_per_post:
            boost_logger.info(f"[{first_item.worker.name}] Post sudah max komentar ({max_comment_per_post}), skip.")
            first_item.worker.processed_posts[key] = "skip"
            first_item.resume_event.set()
            continue
 
        # Grouping window
        group = _grouping_window(pending_queue, first_item, target_username)
 
        # Filter: hanya ambil sebanyak sisa slot komentar
        current_count = comment_count_per_post.get(key, 0)
        slot_remaining = max_comment_per_post - current_count
        group = group[:slot_remaining]
 
        # ── Tampilkan prompt ─────────────────────────────────────────────
        hp_names = ", ".join(item.worker.name for item in group)
        caption_preview = first_item.caption[:80].replace("\n", " ")
 
        print("\n" + "█" * 62)
        print(f"  ⚠  ANTRIAN BOOST — {len(group)} HP menunggu")
        print("█" * 62)
        print(f"  Akun    : @{target_username}")
        print(f"  Caption : \"{caption_preview}\"")
        print(f"  HP      : {hp_names}")
        print(f"  Screenshot: {first_item.screenshot_path}")
        print(f"\n  Bank komentar tersedia:")
        print(_build_bank_menu(available_banks))
        print("█" * 62)
 
        # Input pilih bank
        bank_keys = list(available_banks.keys())
        chosen_bank_name = None
        chosen_comments = None
        while True:
            try:
                raw = input(f"  Pilih bank (1-{len(bank_keys)}): ").strip()
                idx = int(raw) - 1
                if 0 <= idx < len(bank_keys):
                    chosen_bank_name = bank_keys[idx]
                    chosen_comments = available_banks[chosen_bank_name]
                    break
                print(f"  Masukkan angka 1-{len(bank_keys)}.")
            except (ValueError, EOFError):
                print("  Input tidak valid.")
 
        # Konfirmasi
        confirm = input("  Konfirmasi (y/skip): ").strip().lower()
        print("█" * 62 + "\n")
 
        if confirm != "y":
            # Skip semua HP di kelompok
            boost_logger.info(f"SKIP oleh user: {key[:40]} ({len(group)} HP)")
            stats["skipped"] += len(group)
            for item in group:
                item.worker.processed_posts[caption_key_str(target_username, item.caption)] = "skip"
                item.resume_event.set()
            continue
 
        # Jadwalkan eksekusi dengan delay antar HP
        shuffled = group.copy()
        random.shuffle(shuffled)
        delay_acc = 0.0
 
        for item in shuffled:
            execute_at = time.time() + delay_acc
            # Cek apakah masih dalam durasi sesi
            if execute_at >= session_end_time:
                boost_logger.info(f"[{item.worker.name}] Jadwal di luar sesi, dibatalkan.")
                stats["cancelled"] += 1
                item.worker.processed_posts[caption_key_str(target_username, item.caption)] = "done"
                item.resume_event.set()
                continue
 
            sched = ScheduledBoost(
                execute_at=execute_at,
                bank_name=chosen_bank_name,
                bank_comments=chosen_comments,
                caption_key=key,
            )
            with item.worker._sched_lock:
                item.worker.scheduled_boost = sched
 
            boost_logger.info(
                f"[{item.worker.name}] DIJADWAL T+{delay_acc/60:.1f}m "
                f"bank={chosen_bank_name}"
            )
            stats["commented"] += 1
            comment_count_per_post[key] = comment_count_per_post.get(key, 0) + 1
 
            # Resume HP — biarkan patroli lagi, eksekusi di-check tiap iterasi
            item.resume_event.set()
 
            # Tambah delay untuk HP berikutnya
            delay_acc += random.uniform(*comment_delay_range)
 
        print(f"[BOOST] {len(shuffled)} HP dijadwal. Delay antar HP: {comment_delay_range[0]//60}-{comment_delay_range[1]//60} menit.\n")
 
    boost_logger.info("Thread pelayan selesai.")
    return stats
 
 
# ── Entry point ───────────────────────────────────────────────────────────────
 
def setup_boost_session() -> dict:
    """
    Interaktif di terminal: minta semua input yang diperlukan.
    Return dict konfigurasi.
    """
    from comment_bank import COMMENTS_NATURAL, COMMENTS_PROMOSI
 
    # Impor semua bank yang tersedia dari comment_bank
    # Format: {nama_bank: list_komentar}
    all_banks = _discover_banks()
 
    print("\n" + "=" * 55)
    print("  BOOST COMMENT BY USERNAME")
    print("=" * 55)
 
    username = input("  Username target (tanpa @): ").strip().lstrip("@")
    if not username:
        print("  Username tidak boleh kosong.")
        return {}
 
    print(f"\n  Bank komentar tersedia:")
    bank_keys = list(all_banks.keys())
    for idx, name in enumerate(bank_keys, 1):
        sample = all_banks[name][0][:50] if all_banks[name] else "-"
        print(f"    {idx}. {name:<20} → \"{sample}...\"")
 
    raw_banks = input("\n  Pilih bank (pisah koma, contoh: 1,3): ").strip()
    selected_banks = {}
    for part in raw_banks.split(","):
        part = part.strip()
        try:
            i = int(part) - 1
            if 0 <= i < len(bank_keys):
                name = bank_keys[i]
                selected_banks[name] = all_banks[name]
        except ValueError:
            pass
 
    if not selected_banks:
        print("  Tidak ada bank yang valid dipilih.")
        return {}
 
    durasi = int(input("\n  Durasi patroli total (menit): ").strip() or "30")
    max_hp_comment = int(input("  Max komentar per postingan (default 5): ").strip() or "5")
    delay_min = int(input("  Delay min antar HP komentar (menit, default 5): ").strip() or "5")
    delay_max = int(input("  Delay max antar HP komentar (menit, default 7): ").strip() or "7")
 
    print(f"\n  Konfigurasi:")
    print(f"    Target     : @{username}")
    print(f"    Bank       : {', '.join(selected_banks.keys())}")
    print(f"    Durasi     : {durasi} menit")
    print(f"    Max komentar/post: {max_hp_comment}")
    print(f"    Delay      : {delay_min}-{delay_max} menit")
    print("=" * 55)
 
    return {
        "username": username,
        "banks": selected_banks,
        "durasi_menit": durasi,
        "max_comment_per_post": max_hp_comment,
        "delay_range": (delay_min * 60, delay_max * 60),
    }
 
 
def _discover_banks() -> dict:
    """
    Baca semua bank komentar dari comment_bank.py.
    Return dict {nama: list_komentar}.
    """
    import comment_bank as cb
    import inspect
 
    banks = {}
    for name, obj in inspect.getmembers(cb):
        if name.startswith("COMMENTS_") and isinstance(obj, list) and obj:
            # COMMENTS_NATURAL → Natural, COMMENTS_PROMOSI → Promosi, dst
            display = name.replace("COMMENTS_", "").replace("_", " ").title()
            banks[display] = obj
    return banks
 
 
def run_boost_session(devices: list, cfg: dict):
    """
    Jalankan boost session untuk semua device.
    devices: list of (d, device_name) sudah terkoneksi UIAutomator2.
    cfg: output dari setup_boost_session().
    """
    if not cfg:
        return
 
    pending_queue = queue.Queue()
    session_end_time = time.time() + cfg["durasi_menit"] * 60
 
    # Buat worker per device
    workers = []
    for d, name in devices:
        worker = DeviceWorker(
            d=d,
            device_name=name,
            target_username=cfg["username"],
            pending_queue=pending_queue,
            session_end_time=session_end_time,
            max_comment_per_post=cfg["max_comment_per_post"],
        )
        workers.append(worker)
 
    # Jalankan worker di thread masing-masing
    threads = []
    for worker in workers:
        t = threading.Thread(target=worker.run, name=f"patrol-{worker.name}", daemon=True)
        t.start()
        threads.append(t)
 
    boost_logger.info(f"Boost session dimulai. {len(workers)} HP, target @{cfg['username']}, durasi {cfg['durasi_menit']}m")
    print(f"\n[BOOST] {len(workers)} HP mulai patroli @{cfg['username']} selama {cfg['durasi_menit']} menit...\n")
 
    # Main thread melayani antrian (blocking, tapi input() bisa berjalan)
    stats = serve_queue(
        pending_queue=pending_queue,
        available_banks=cfg["banks"],
        target_username=cfg["username"],
        session_end_time=session_end_time,
        comment_delay_range=cfg["delay_range"],
        max_comment_per_post=cfg["max_comment_per_post"],
    )
 
    # Tunggu semua thread patroli selesai
    for worker in workers:
        worker.stop_event.set()
    for t in threads:
        t.join(timeout=15)
 
    # Summary
    print("\n" + "=" * 55)
    print("  BOOST SESSION SELESAI — Ringkasan")
    print("=" * 55)
    print(f"  Durasi       : {cfg['durasi_menit']} menit")
    print(f"  Target       : @{cfg['username']}")
    print(f"  Ditemukan    : {stats['found']} kali masuk antrian")
    print(f"  Dijadwal     : {stats['commented']} komentar")
    print(f"  Skip (user)  : {stats['skipped']} HP")
    print(f"  Dibatalkan   : {stats['cancelled']} (durasi habis)")
    print(f"  Log detail   : logs/boost_queue.log")
    print("=" * 55 + "\n")
 
    boost_logger.info(
        f"SESSION SELESAI | found={stats['found']} commented={stats['commented']} "
        f"skipped={stats['skipped']} cancelled={stats['cancelled']}"
    )
