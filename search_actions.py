"""
search_actions.py
Fitur Search Instagram:
  1. search_and_interact()    — cari keyword → like/komen/repost hasil search
  2. explore_and_interact()   — jelajah search page tanpa keyword
  3. mine_keywords()          — scan search page → ekstrak keyword → review → simpan
"""

import random
import time
import re
import yaml
import logging
import os

from human_behavior import random_sleep, human_swipe, human_typing, RESOURCE_IDS
from instagram_actions import (
    dismiss_popups,
    navigate_to_feed,
    post_comment,
    back_to_feed,
    get_current_page,
)

logger = logging.getLogger(__name__)

KEYWORDS_FILE = "keywords.yaml"

# ── Resource ID khusus search ────────────────────────────────────────────────
SEARCH_TAB_XPATH   = '//*[@resource-id="com.instagram.android:id/search_tab"]/android.widget.ImageView[1]'
SEARCH_BAR_ID      = "com.instagram.android:id/explore_action_bar_container"
SEARCH_INPUT_ID    = "com.instagram.android:id/action_bar_search_edit_text"
REEL_PLAY_COUNT_ID = "com.instagram.android:id/preview_clip_play_count"
FIRST_COMMENT_XPATH = '//android.widget.ScrollView/android.view.ViewGroup[1]'

# ── Helpers keyword bank ─────────────────────────────────────────────────────

def load_keywords() -> list[str]:
    """Baca keywords.yaml, return list string."""
    if not os.path.exists(KEYWORDS_FILE):
        logger.warning(f"{KEYWORDS_FILE} tidak ditemukan, return list kosong.")
        return []
    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return [str(k).strip() for k in (data or {}).get("keywords", []) if str(k).strip()]
    except Exception:
        logger.exception("Gagal baca keywords.yaml")
        return []


def save_keywords(keywords: list[str]) -> None:
    """Tulis ulang keywords.yaml dengan list yang diberikan."""
    try:
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            yaml.dump({"keywords": sorted(set(keywords))},
                      f, allow_unicode=True, default_flow_style=False)
        logger.info(f"keywords.yaml disimpan ({len(keywords)} keyword).")
    except Exception:
        logger.exception("Gagal simpan keywords.yaml")


# ── Navigasi ke Search ───────────────────────────────────────────────────────

def navigate_to_search(d, max_retry: int = 3) -> bool:
    """
    Navigasi ke tab Search/Explore.
    Return True jika berhasil.
    """
    for attempt in range(max_retry):
        # Verifikasi: search bar sudah terlihat?
        if d(resourceId=SEARCH_BAR_ID).exists:
            logger.info("Sudah di halaman Search.")
            return True

        logger.info(f"Navigasi ke Search (percobaan {attempt + 1})...")

        # Coba via xpath tab icon dulu
        tab = d.xpath(SEARCH_TAB_XPATH)
        if tab.exists:
            tab.click()
        else:
            # Fallback: cari via resourceId tab search
            tab2 = d(resourceId=RESOURCE_IDS["TAB_SEARCH"])
            if tab2.exists:
                tab2.click()
            else:
                # Tidak ada tab sama sekali — back dulu supaya navbar muncul
                d.press("back")
                random_sleep(0.5, 0.8)
                tab = d.xpath(SEARCH_TAB_XPATH)
                if tab.exists:
                    tab.click()

        random_sleep(1.5, 2.5)
        dismiss_popups(d)

        if d(resourceId=SEARCH_BAR_ID).exists:
            logger.info("Berhasil masuk halaman Search.")
            return True

    logger.warning("Gagal masuk halaman Search setelah semua percobaan.")
    return False


def _open_search_input(d) -> bool:
    """Klik search bar sehingga input field muncul. Return True jika berhasil."""
    bar = d(resourceId=SEARCH_BAR_ID)
    if bar.exists:
        bar.click()
        random_sleep(0.8, 1.2)
    # Tunggu input field muncul
    for _ in range(5):
        if d(resourceId=SEARCH_INPUT_ID).exists:
            return True
        time.sleep(0.4)
    return False


def _type_keyword_and_search(d, keyword: str) -> bool:
    """Ketik keyword di search bar dan tekan enter. Return True jika hasil muncul."""
    if not _open_search_input(d):
        logger.warning("Input search tidak muncul.")
        return False

    field = d(resourceId=SEARCH_INPUT_ID)
    field.clear_text()
    random_sleep(0.3, 0.6)
    human_typing(d, keyword)
    random_sleep(0.8, 1.2)
    d.press("enter")
    random_sleep(1.5, 2.5)
    dismiss_popups(d)
    return True


def _close_search_and_back(d) -> None:
    """Tutup search / kembali ke explore page."""
    # Tekan back 1-2x sampai explore page muncul kembali
    for _ in range(3):
        if d(resourceId=SEARCH_BAR_ID).exists:
            return
        d.press("back")
        random_sleep(0.5, 0.8)


# ── Deteksi & scoring konten di grid ─────────────────────────────────────────

def _parse_count(text: str) -> int:
    """'21.8M' → 21800000, '3,766' → 3766."""
    if not text:
        return 0
    text = text.strip().replace(',', '')
    mult = 1
    if text[-1].lower() == 'k':
        mult = 1_000; text = text[:-1]
    elif text[-1].lower() == 'm':
        mult = 1_000_000; text = text[:-1]
    try:
        return int(float(text) * mult)
    except ValueError:
        return 0


def _is_reel_tile(elem_info: dict) -> bool:
    """Cek apakah tile adalah reel berdasarkan content-desc."""
    desc = (elem_info.get("contentDescription") or "").lower()
    return "reel" in desc


def _get_tile_play_count(d, tile) -> int:
    """Ambil play count dari tile reel. Return 0 kalau bukan reel / tidak ada."""
    try:
        # Coba baca teks preview_clip_play_count di dalam area tile
        bounds = tile.info.get("bounds", {})
        # Cari semua play count di layar dan ambil yang posisinya di dalam bounds tile
        all_counts = d(resourceId=REEL_PLAY_COUNT_ID)
        for cnt in all_counts:
            cb = cnt.info.get("bounds", {})
            if (cb.get("left", 0) >= bounds.get("left", 0) and
                    cb.get("right", 0) <= bounds.get("right", 9999)):
                return _parse_count(cnt.info.get("text", "0"))
    except Exception:
        pass
    return 0


# ── Core: interaksi satu konten dari search ──────────────────────────────────

def _interact_content(d, is_reel: bool,
                      like_prob: float, comment_prob: float, repost_prob: float,
                      comment_promosi_ratio: float, max_likes: int,
                      like_count: list) -> None:
    """
    Sudah berada di dalam konten (post/reel).
    Lakukan like/comment/repost sesuai probabilitas.
    like_count adalah list[int] dengan 1 elemen agar bisa dimodifikasi by reference.
    """
    random_sleep(1.5, 3.0)   # "nonton" sebentar

    if is_reel:
        # Tonton dulu sebentar layaknya manusia
        watch = random.uniform(3, 10)
        time.sleep(watch)

        # Like
        if random.random() < like_prob and (max_likes == 0 or like_count[0] < max_likes):
            like_btn = d(resourceId=RESOURCE_IDS["REEL_LIKE"])
            if like_btn.exists:
                like_btn.click()
                logger.info("Like reel (search).")
            else:
                # double-tap fallback
                w, h = d.window_size()
                cx, cy = w // 2, h // 2
                d.click(cx, cy); time.sleep(0.08); d.click(cx, cy)
                logger.info("Like reel double-tap (search).")
            like_count[0] += 1
            random_sleep(0.3, 0.7)

        # Buka komentar & baca sebentar sebelum komen
        if random.random() < comment_prob:
            # Cari tombol komentar
            comment_btn = d(resourceId=RESOURCE_IDS["REEL_COMMENT"])
            if not comment_btn.exists:
                # Cari via xpath fallback
                cb = d.xpath(FIRST_COMMENT_XPATH)
                if cb.exists:
                    cb.click()
                    random_sleep(1.0, 2.0)
                    # Scroll komentar sebentar
                    for _ in range(random.randint(1, 3)):
                        human_swipe(d, 'up', distance=random.randint(200, 400))
                        random_sleep(0.5, 1.5)
            if comment_btn.exists or d(resourceId=RESOURCE_IDS["REEL_COMMENT"]).exists:
                post_comment(d, is_reel=True,
                             comment_promosi_ratio=comment_promosi_ratio)

        # Repost
        if random.random() < repost_prob:
            rp = d(description="Repost")
            if rp.exists:
                rp.click()
                random_sleep(0.5, 1.0)
                logger.info("Repost reel (search).")

    else:
        # Feed post
        random_sleep(1.5, 3.0)

        # Like
        if random.random() < like_prob and (max_likes == 0 or like_count[0] < max_likes):
            like_btn = d(resourceId=RESOURCE_IDS["FEED_LIKE"])
            if like_btn.exists:
                like_btn.click()
                like_count[0] += 1
                logger.info("Like post (search).")
                random_sleep(0.3, 0.7)

        # Comment
        if random.random() < comment_prob:
            post_comment(d, is_reel=False,
                         comment_promosi_ratio=comment_promosi_ratio)
            back_to_feed(d)

        # Repost
        if random.random() < repost_prob:
            rp = d.xpath('//*[@resource-id="com.instagram.android:id/reposts_ufi_icon"]')
            if rp.exists:
                rp.click()
                random_sleep(0.5, 1.0)
                logger.info("Repost post (search).")


def _pick_and_open_tile(d, prefer_reel: bool = True,
                        min_play_count: int = 100_000) -> tuple[bool, bool]:
    """
    Pilih tile terbaik dari grid yang terlihat sekarang dan buka.
    Return (berhasil_dibuka, is_reel).

    Strategi:
    - Kumpulkan semua tile yang terlihat
    - Kalau prefer_reel: cari reel dengan play count tertinggi >= min_play_count
    - Fallback: ambil tile acak
    """
    # Kumpulkan tile: elemen dengan content-desc yang mengandung "row" dan "column"
    tiles = []
    try:
        all_elems = d.xpath('//*[contains(@content-desc, "row") and contains(@content-desc, "column")]').all()
        for elem in all_elems:
            info = elem.info
            desc = (info.get("contentDescription") or "").lower()
            if not desc:
                continue
            is_reel = "reel" in desc
            play_count = _get_tile_play_count(d, elem) if is_reel else 0
            tiles.append({
                "elem": elem,
                "is_reel": is_reel,
                "play_count": play_count,
                "desc": desc,
            })
    except Exception:
        logger.exception("Gagal kumpulkan tiles")
        return False, False

    if not tiles:
        logger.info("Tidak ada tile terdeteksi di layar.")
        return False, False

    chosen = None

    if prefer_reel:
        # Urutkan reel by play count desc
        reels = [t for t in tiles if t["is_reel"] and t["play_count"] >= min_play_count]
        reels.sort(key=lambda x: x["play_count"], reverse=True)
        if reels:
            chosen = reels[0]
            logger.info(f"Pilih reel: {chosen['desc'][:60]} — {chosen['play_count']:,} plays")

    if chosen is None:
        # Fallback: acak dari semua tile
        chosen = random.choice(tiles)
        logger.info(f"Pilih tile acak: {chosen['desc'][:60]}")

    try:
        chosen["elem"].click()
        random_sleep(2.0, 3.5)
        dismiss_popups(d)
        return True, chosen["is_reel"]
    except Exception:
        logger.exception("Gagal klik tile")
        return False, False


# ── Fitur 1: Search by keyword → interact ────────────────────────────────────

def search_and_interact(d, duration: int = 300,
                        like_prob: float = 0.3,
                        comment_prob: float = 0.05,
                        repost_prob: float = 0.05,
                        comment_promosi_ratio: float = 0.2,
                        max_likes: int = 0,
                        keyword: str = None) -> None:
    """
    Masuk search, ketik keyword, buka konten rame, like/komen/repost,
    lalu balik ke search page dan pilih konten lain.
    """
    logger.info(f"=== Search & Interact | keyword: {keyword or 'acak'} ===")

    if not navigate_to_search(d):
        logger.error("Tidak bisa masuk Search, skip.")
        return

    # Pilih keyword
    if not keyword:
        bank = load_keywords()
        if not bank:
            logger.warning("Bank keyword kosong, pakai explore tanpa keyword.")
            explore_and_interact(d, duration, like_prob, comment_prob,
                                 repost_prob, comment_promosi_ratio, max_likes)
            return
        keyword = random.choice(bank)
        logger.info(f"Keyword terpilih: '{keyword}'")

    if not _type_keyword_and_search(d, keyword):
        logger.error("Gagal ketik keyword.")
        return

    start_time = time.time()
    like_count = [0]
    content_count = 0

    while time.time() - start_time < duration:
        dismiss_popups(d)

        # Scroll grid sedikit untuk variasi konten
        if content_count > 0:
            for _ in range(random.randint(1, 3)):
                human_swipe(d, 'up', speed='fast',
                            distance=random.randint(400, 700))
                random_sleep(0.5, 1.0)

        opened, is_reel = _pick_and_open_tile(d, prefer_reel=True)
        if not opened:
            # Tidak ada tile — scroll lebih jauh
            human_swipe(d, 'up', speed='fast', distance=random.randint(600, 900))
            random_sleep(1.0, 2.0)
            continue

        _interact_content(d, is_reel, like_prob, comment_prob, repost_prob,
                          comment_promosi_ratio, max_likes, like_count)
        content_count += 1
        logger.info(f"Konten ke-{content_count} selesai diinteraksi.")

        # Balik ke search page (pilih konten lain)
        _close_search_and_back(d)
        random_sleep(1.0, 2.0)

        if max_likes > 0 and like_count[0] >= max_likes:
            logger.info("Batas like tercapai, stop search_and_interact.")
            break

    logger.info(f"search_and_interact selesai. Total konten: {content_count}, like: {like_count[0]}")
    _close_search_and_back(d)


# ── Fitur 2: Explore tanpa keyword ───────────────────────────────────────────

def explore_and_interact(d, duration: int = 300,
                         like_prob: float = 0.3,
                         comment_prob: float = 0.05,
                         repost_prob: float = 0.05,
                         comment_promosi_ratio: float = 0.2,
                         max_likes: int = 0) -> None:
    """
    Jelajah search/explore page tanpa keyword.
    Pilih konten rame (reel prioritas), interaksi, balik, pilih lain.
    """
    logger.info("=== Explore & Interact (tanpa keyword) ===")

    if not navigate_to_search(d):
        logger.error("Tidak bisa masuk Search, skip.")
        return

    start_time = time.time()
    like_count = [0]
    content_count = 0

    while time.time() - start_time < duration:
        dismiss_popups(d)

        if content_count > 0:
            for _ in range(random.randint(1, 2)):
                human_swipe(d, 'up', speed='fast',
                            distance=random.randint(400, 700))
                random_sleep(0.5, 1.0)

        opened, is_reel = _pick_and_open_tile(d, prefer_reel=True)
        if not opened:
            human_swipe(d, 'up', speed='fast', distance=random.randint(600, 900))
            random_sleep(1.0, 2.0)
            continue

        _interact_content(d, is_reel, like_prob, comment_prob, repost_prob,
                          comment_promosi_ratio, max_likes, like_count)
        content_count += 1
        logger.info(f"Konten ke-{content_count} selesai diinteraksi (explore).")

        _close_search_and_back(d)
        random_sleep(1.0, 2.0)

        if max_likes > 0 and like_count[0] >= max_likes:
            logger.info("Batas like tercapai, stop explore_and_interact.")
            break

    logger.info(f"explore_and_interact selesai. Total: {content_count}, like: {like_count[0]}")
    navigate_to_feed(d)


# ── Fitur 3: Mine keywords dari search page ───────────────────────────────────

def _extract_keywords_from_screen(d) -> list[str]:
    """
    Baca semua teks di layar dan ekstrak kandidat keyword:
    - Hashtag (#kata)
    - Teks pendek yang meaningful (2–4 kata, bukan angka/simbol)
    Return list string unik.
    """
    candidates = set()
    pattern_hashtag = re.compile(r'#(\w+)')
    pattern_word = re.compile(r'^[a-zA-Z\u00C0-\u024F\u0080-\u024F ]{3,40}$')  # huruf + spasi

    try:
        all_elems = d.xpath('//*[not(@text="")]').all()
        for elem in all_elems:
            try:
                txt = (elem.text or "").strip()
            except Exception:
                continue
            if not txt:
                continue

            # Hashtag
            for m in pattern_hashtag.findall(txt):
                kw = m.lower().strip()
                if 3 <= len(kw) <= 40:
                    candidates.add(kw)

            # Frase pendek (judul konten, caption pendek)
            if 3 <= len(txt) <= 50 and pattern_word.match(txt):
                # Buang yang terlalu generik
                generic = {"like", "follow", "share", "more", "view", "all",
                           "see", "post", "reel", "video", "photo", "story",
                           "and", "the", "for", "you", "this", "that"}
                words = txt.lower().split()
                if len(words) <= 5 and not set(words).issubset(generic):
                    candidates.add(txt.lower().strip())

    except Exception:
        logger.exception("Error ekstrak keyword dari layar")

    return sorted(candidates)


def mine_keywords(d, scroll_rounds: int = 5) -> None:
    """
    Scan halaman search/explore → ekstrak kandidat keyword →
    tampilkan semua ke user → user ketik nomor yang mau DIBUANG →
    sisanya disimpan ke keywords.yaml (digabung dengan yang sudah ada).
    """
    logger.info("=== Mine Keywords ===")

    if not navigate_to_search(d):
        logger.error("Tidak bisa masuk Search, skip mine_keywords.")
        return

    all_candidates: set[str] = set()

    # Scroll beberapa kali sambil scan teks di layar
    for i in range(scroll_rounds):
        logger.info(f"Scan layar round {i+1}/{scroll_rounds}...")
        found = _extract_keywords_from_screen(d)
        all_candidates.update(found)
        logger.info(f"  +{len(found)} kandidat (total: {len(all_candidates)})")

        human_swipe(d, 'up', speed='normal',
                    distance=random.randint(500, 800))
        random_sleep(1.0, 2.0)

    if not all_candidates:
        print("\n[Mine Keywords] Tidak ada kandidat keyword ditemukan.")
        return

    # Filter: buang yang sudah ada di bank
    existing = set(load_keywords())
    new_candidates = sorted(all_candidates - existing)

    if not new_candidates:
        print("\n[Mine Keywords] Semua keyword sudah ada di bank, tidak ada yang baru.")
        return

    # ── Tampilkan ke user untuk review ──────────────────────────────────────
    print("\n" + "="*55)
    print("  KANDIDAT KEYWORD BARU DITEMUKAN")
    print("="*55)
    for idx, kw in enumerate(new_candidates, 1):
        print(f"  {idx:>3}. {kw}")
    print("="*55)
    print("\nKetik nomor yang mau DIBUANG (pisah koma, contoh: 2,5,8)")
    print("Atau tekan Enter langsung untuk SIMPAN SEMUA.")
    raw = input("> ").strip()

    # Parsing nomor yang dibuang
    buang = set()
    if raw:
        for part in raw.split(','):
            part = part.strip()
            try:
                n = int(part)
                if 1 <= n <= len(new_candidates):
                    buang.add(n)
            except ValueError:
                pass

    approved = [kw for idx, kw in enumerate(new_candidates, 1) if idx not in buang]

    if not approved:
        print("\n[Mine Keywords] Semua dibuang, tidak ada yang disimpan.")
        return

    # Gabung dengan yang sudah ada lalu simpan
    final = sorted(existing | set(approved))
    save_keywords(final)

    print(f"\n[Mine Keywords] {len(approved)} keyword baru disimpan:")
    for kw in approved:
        print(f"  ✓ {kw}")
    print(f"Total keyword di bank sekarang: {len(final)}")