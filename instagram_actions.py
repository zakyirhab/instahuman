import random
import time
import os
import datetime
import logging
from human_behavior import random_sleep, human_swipe, human_typing, RESOURCE_IDS
from comment_bank import COMMENTS_NATURAL, COMMENTS_PROMOSI
import re

logger = logging.getLogger(__name__)

def _parse_number(text: str) -> int:
    """Ubah teks seperti '199K', '8,604', '16' menjadi integer."""
    if not text:
        return 0
    text = text.strip().replace(',', '')
    multiplier = 1
    if text[-1].lower() == 'k':
        multiplier = 1000
        text = text[:-1]
    elif text[-1].lower() == 'm':
        multiplier = 1000000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0

def _get_like_count(d) -> int:
    """Perkirakan jumlah like dari elemen teks di layar. Ambil angka terbesar yang valid."""
    pattern = re.compile(r'^[\d,.]+[KkMm]?$')
    best = 0
    for elem in d.xpath('//*[not(@text="")]').all():
        try:
            txt = elem.text
        except Exception:
            continue
        if not txt or not txt.strip():
            continue
        if pattern.match(txt.strip()):
            val = _parse_number(txt)
            if val > best:
                best = val
    return best

# ---------- popup dismiss ----------

def _is_suggested_content(d) -> bool:
    """True jika layar menampilkan Suggested Follows atau Suggested Reels."""
    if d(resourceId="com.instagram.android:id/netego_carousel_title").exists:
        logger.info("Suggested follows terdeteksi, skip...")
        return True
    if d(resourceId="com.instagram.android:id/clips_header_title").exists:
        logger.info("Suggested reels terdeteksi, skip...")
        return True
    return False

def _is_on_post(d) -> bool:
    """True jika salah satu penanda postingan terlihat di layar."""
    if d(resourceId="com.instagram.android:id/carousel_index_indicator_text_view").exists:
        return True
    if d(resourceId="com.instagram.android:id/layout_container_main").exists:
        return True
    if d.xpath('//*[@resource-id="android:id/list"]/android.view.ViewGroup[2]').exists:
        return True
    return False

def _center_post(d):
    """Scroll kecil ke atas berulang sampai penanda postingan muncul, maks 3 kali."""
    for _ in range(3):
        if _is_on_post(d):
            return True
        human_swipe(d, 'up', distance=random.randint(150, 250), speed='fast')
        random_sleep(0.3, 0.5)
    return _is_on_post(d)

def dismiss_popups(d):
    """Tutup pop-up umum yang mengganggu."""
    popup_texts = ["Not Now", "Cancel", "Close", "Later", "Skip", "Dismiss"]
    for text in popup_texts:
        btn = d(text=text)
        if btn.exists:
            btn.click()
            logger.info(f"Popup '{text}' ditutup.")
            time.sleep(0.5)
            return True
    return False

# ---------- navigasi ----------

def go_home(d):
    for _ in range(3):
        d.press("back")
        time.sleep(0.5)
        if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
            dismiss_popups(d)
            return
    home = d(resourceId=RESOURCE_IDS["TAB_HOME"])
    if home.exists:
        home.click()
        time.sleep(1)
        dismiss_popups(d)

def back_to_feed(d):
    """Kembali ke feed tanpa refresh."""
    for _ in range(3):
        if d(resourceId=RESOURCE_IDS["FEED_LIKE"]).exists:
            return
        if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
            return
        d.press("back")
        time.sleep(0.5)

# ---------- [BARU] deteksi halaman & navigasi aman ----------

def get_current_page(d) -> str:
    """
    Deteksi halaman Instagram yang sedang aktif.
    Return: 'feed' | 'reels' | 'story' | 'dm' | 'notification' | 'unknown'
    """
    if d(resourceId=RESOURCE_IDS["FEED_LIKE"]).exists:
        return 'feed'
    if d(resourceId=RESOURCE_IDS["FEED_COMMENT"]).exists:
        return 'feed'
    if d(resourceId=RESOURCE_IDS["REEL_LIKE"]).exists:
        if not d(resourceId=RESOURCE_IDS["FEED_LIKE"]).exists:
            return 'reels'
    if d(resourceId="com.instagram.android:id/reel_viewer_root").exists:
        return 'story'
    if d(resourceId="com.instagram.android:id/direct_inbox_item_layout").exists:
        return 'dm'
    if d(resourceId="com.instagram.android:id/notification_list").exists:
        return 'notification'
    return 'unknown'

def navigate_to_feed(d, max_retry: int = 3) -> bool:
    """Navigasi ke tab Feed dan verifikasi berhasil."""
    for attempt in range(max_retry):
        if get_current_page(d) == 'feed':
            logger.info("Sudah di Feed.")
            return True

        logger.info(f"Navigasi ke Feed (percobaan {attempt + 1})...")
        current = get_current_page(d)
        if current in ('story', 'reels', 'unknown'):
            d.press("back")
            random_sleep(0.5, 0.8)

        home_tab = d(resourceId=RESOURCE_IDS["TAB_HOME"])
        if home_tab.exists:
            home_tab.click()
        else:
            d.press("back")
            random_sleep(0.5, 1.0)
            home_tab = d(resourceId=RESOURCE_IDS["TAB_HOME"])
            if home_tab.exists:
                home_tab.click()

        random_sleep(1.5, 2.5)
        dismiss_popups(d)

        if get_current_page(d) == 'feed':
            logger.info("Berhasil navigasi ke Feed.")
            return True

    logger.warning("Gagal navigasi ke Feed setelah semua percobaan.")
    return False

def navigate_to_reels(d, max_retry: int = 3) -> bool:
    """Navigasi ke tab Reels dan verifikasi berhasil."""
    for attempt in range(max_retry):
        current = get_current_page(d)
        if current == 'reels':
            logger.info("Sudah di Reels.")
            return True

        logger.info(f"Navigasi ke Reels (percobaan {attempt + 1})...")
        if current in ('story', 'unknown'):
            d.press("back")
            random_sleep(0.5, 0.8)

        reels_tab = d(resourceId=RESOURCE_IDS["TAB_REELS"])
        if reels_tab.exists:
            reels_tab.click()
        else:
            home_tab = d(resourceId=RESOURCE_IDS["TAB_HOME"])
            if home_tab.exists:
                home_tab.click()
                random_sleep(1.0, 1.5)
            reels_tab = d(resourceId=RESOURCE_IDS["TAB_REELS"])
            if reels_tab.exists:
                reels_tab.click()

        random_sleep(2.0, 3.0)
        dismiss_popups(d)

        if get_current_page(d) == 'reels':
            logger.info("Berhasil navigasi ke Reels.")
            return True

    logger.warning("Gagal navigasi ke Reels setelah semua percobaan.")
    return False

# ---------- [BARU] baca username & caption postingan (untuk boost) ----------

def get_post_username(d) -> str:
    """
    Baca username dari postingan yang sedang di layar feed.
    Return string username (tanpa @) atau '' jika tidak ditemukan.
    """
    candidates = [
        "com.instagram.android:id/row_header_textview",
        "com.instagram.android:id/username",
        "com.instagram.android:id/media_owner_username_text_view",
    ]
    for res_id in candidates:
        el = d(resourceId=res_id)
        if el.exists:
            try:
                txt = el.get_text(timeout=1).strip().lstrip("@")
                if txt:
                    return txt
            except Exception:
                pass

    # Fallback regex username
    pattern = re.compile(r'^[a-zA-Z0-9._]{3,30}$')
    generic = {"follow", "following", "message", "share", "like", "comment",
               "save", "more", "sponsored", "reel", "video", "photo", "story"}
    try:
        for elem in d.xpath('//*[@resource-id]').all():
            try:
                txt = (elem.text or "").strip().lstrip("@")
                if txt and pattern.match(txt) and not txt.isdigit() \
                        and txt.lower() not in generic:
                    return txt
            except Exception:
                pass
    except Exception:
        pass
    return ""

def get_post_caption(d) -> str:
    """
    Baca caption postingan yang sedang di layar.
    Return string caption atau '' jika tidak ditemukan.
    """
    candidates = [
        "com.instagram.android:id/caption_text_view",
        "com.instagram.android:id/row_feed_comment_textview_layout",
    ]
    for res_id in candidates:
        el = d(resourceId=res_id)
        if el.exists:
            try:
                txt = el.get_text(timeout=1).strip()
                if txt:
                    return txt
            except Exception:
                pass
    try:
        el = d.xpath('//*[@resource-id="com.instagram.android:id/caption_text_view"]')
        if el.exists:
            return (el.get_text() or "").strip()
    except Exception:
        pass
    return ""

# ---------- notifikasi & DM ----------

def check_notifications(d) -> None:
    logger.info("Mengecek notifikasi...")
    try:
        notif_btn = d(resourceId=RESOURCE_IDS["NOTIFICATION_BUTTON"])
        if notif_btn.exists:
            notif_btn.click()
            random_sleep(2, 5)
            for _ in range(random.randint(1, 3)):
                human_swipe(d, 'up')
                random_sleep(1, 3)
            if RESOURCE_IDS.get("NOTIFICATION_FOLLOW_BACK"):
                follow_btn = d(resourceId=RESOURCE_IDS["NOTIFICATION_FOLLOW_BACK"])
                if follow_btn.exists:
                    follow_btn.click()
                    logger.info("Follow Back diberikan.")
        else:
            logger.info("Tidak ada notifikasi.")
    except Exception:
        logger.exception("Error notifikasi")
    finally:
        go_home(d)

def check_dm(d) -> None:
    logger.info("Mengecek DM...")
    try:
        dm_btn = d(resourceId=RESOURCE_IDS["DM_BUTTON"])
        if dm_btn.exists:
            dm_btn.click()
            random_sleep(2, 4)
            for _ in range(random.randint(1, 2)):
                human_swipe(d, 'up')
                random_sleep(1, 2)
        else:
            logger.info("Tidak ada DM baru.")
    except Exception:
        logger.exception("Error DM")
    finally:
        go_home(d)

# ---------- story ----------

def watch_stories(d) -> None:
    logger.info("Menonton story...")
    try:
        all_rings = d(resourceId=RESOURCE_IDS["STORY_RING"])
        if not all_rings.exists:
            logger.info("Tidak ada story ring sama sekali.")
            return

        target = None
        for elem in all_rings:
            desc = (elem.info.get('contentDescription') or '').lower()
            if not desc or 'add' in desc or 'your' in desc or 'camera' in desc:
                continue
            if 'story' in desc and '0 of' not in desc:
                target = elem
                break

        if target is None:
            logger.info("Tidak ada story dengan unseen baru.")
            return

        logger.info(f"Buka story: {target.info.get('contentDescription')}")
        target.click()
        random_sleep(2, 4)

        max_safety = 100
        count = 0
        while count < max_safety:
            count += 1
            if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
                logger.info("Semua story sudah ditonton (kembali ke feed).")
                break

            ad_story = d(resourceId="com.instagram.android:id/reel_item_sponsored_label_footer_pill")
            if ad_story.exists:
                logger.info("Story iklan, skip...")
                _skip_ad_story(d)
                continue

            random_sleep(1, 3)
            _next_story(d)

    except Exception:
        logger.exception("Story error")
    finally:
        try:
            if not d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
                d.press("back")
                random_sleep(1, 2)
        except:
            pass

def _next_story(d):
    """Lanjut ke story berikutnya dengan swipe kiri (aman dari widget)."""
    if RESOURCE_IDS.get("STORY_NEXT"):
        next_btn = d(resourceId=RESOURCE_IDS["STORY_NEXT"])
        if next_btn.exists:
            next_btn.click()
            return
    _skip_ad_story(d)

def _skip_ad_story(d):
    """Swipe kiri untuk skip story iklan."""
    w, h = d.window_size()
    start_x = int(w * 0.9)
    end_x = int(w * 0.1)
    y = h // 2
    d.swipe(start_x, y, end_x, y, duration=random.uniform(0.3, 0.6))
    random_sleep(0.5, 1)

# ---------- feed ----------
def interact_feed(d, duration=60, like_prob=0.3, comment_prob=0.03, repost_prob=0.05,
                  comment_promosi_ratio=0.2, max_likes=0):
    logger.info("Memulai interaksi feed...")
    start_time = time.time()
    like_count = 0

    while time.time() - start_time < duration:
        dismiss_popups(d)

        for _ in range(random.randint(1, 2)):
            human_swipe(d, 'up', speed='normal')
            random_sleep(0.5, 1.5)

        if _is_suggested_content(d):
            human_swipe(d, 'up', speed='fast')
            random_sleep(0.3, 0.7)
            continue

        if d(resourceId="com.instagram.android:id/cta_container").exists:
            logger.info("Iklan feed terdeteksi, skip...")
            human_swipe(d, 'up', speed='fast')
            random_sleep(0.3, 0.7)
            continue

        if not _center_post(d):
            human_swipe(d, 'up', speed='normal')
            random_sleep(0.3, 0.5)
            continue

        follow_btn = d(resourceId="com.instagram.android:id/inline_follow_button")
        is_followed = not follow_btn.exists

        if is_followed:
            if random.random() < like_prob and (max_likes == 0 or like_count < max_likes):
                like_btn = d(resourceId=RESOURCE_IDS["FEED_LIKE"])
                if like_btn.exists:
                    like_btn.click()
                    like_count += 1
                    logger.info(f"Like diberikan. ({like_count}/{max_likes if max_likes>0 else 'unlimited'})")
                    random_sleep(0.3, 0.7)
            logger.info("Akun sudah di-follow, hanya like yang diberikan.")
        else:
            like_count_post = _get_like_count(d)
            is_popular = like_count_post >= 100

            if random.random() < like_prob and (max_likes == 0 or like_count < max_likes):
                like_btn = d(resourceId=RESOURCE_IDS["FEED_LIKE"])
                if like_btn.exists:
                    like_btn.click()
                    like_count += 1
                    logger.info(f"Like diberikan. ({like_count}/{max_likes if max_likes>0 else 'unlimited'})")
                    random_sleep(0.3, 0.7)

            if is_popular and random.random() < repost_prob:
                repost_btn = d.xpath('//*[@resource-id="com.instagram.android:id/reposts_ufi_icon"]')
                if repost_btn.exists:
                    repost_btn.click()
                    random_sleep(0.5, 1)
                    logger.info("Repost.")
                    random_sleep(0.5, 1)

            if is_popular and random.random() < comment_prob:
                post_comment(d, is_reel=False, comment_promosi_ratio=comment_promosi_ratio)
                back_to_feed(d)

        human_swipe(d, 'up', speed='normal')
        random_sleep(0.3, 0.5)
        human_swipe(d, 'up', speed='normal')
        random_sleep(0.3, 0.5)

# ---------- reels ----------

def _reel_like_fallback(d):
    """Double-tap di tengah layar untuk like reel (fallback)."""
    w, h = d.window_size()
    cx, cy = w // 2, h // 2
    d.click(cx, cy)
    time.sleep(0.08)
    d.click(cx, cy)
    logger.info("Like reel (double-tap fallback).")

# ---------- [BARU] cari tombol komentar reel dengan fallback container ----------

def _find_comment_button_reel(d):
    """
    Cari tombol komentar reel dengan 3 fallback:
    1. resourceId comment_button (standard)
    2. clips_linear_layout_container > FrameLayout[2] (ketutupan action bar)
    3. Swipe kecil lalu coba ulang
    """
    btn = d(resourceId=RESOURCE_IDS["REEL_COMMENT"])
    if btn.exists:
        return btn

    btn_alt = d.xpath(
        '//*[@resource-id="com.instagram.android:id/clips_linear_layout_container"]'
        '/android.widget.FrameLayout[2]/android.widget.LinearLayout[1]'
    )
    if btn_alt.exists:
        logger.info("Tombol komentar ditemukan via clips_linear_layout_container.")
        return btn_alt

    for _ in range(2):
        human_swipe(d, 'up', distance=random.randint(80, 150), speed='fast')
        random_sleep(0.4, 0.7)
        btn = d(resourceId=RESOURCE_IDS["REEL_COMMENT"])
        if btn.exists:
            return btn
        btn_alt = d.xpath(
            '//*[@resource-id="com.instagram.android:id/clips_linear_layout_container"]'
            '/android.widget.FrameLayout[2]/android.widget.LinearLayout[1]'
        )
        if btn_alt.exists:
            logger.info("Tombol komentar ditemukan setelah swipe via container.")
            return btn_alt

    return None

def scroll_reels(d, duration: int = 60, like_prob: float = 0.3,
                 comment_prob: float = 0.05, repost_prob: float = 0.0,
                 comment_promosi_ratio: float = 0.2, max_likes: int = 0) -> None:
    logger.info("Mulai nonton Reels...")
    try:
        d(resourceId=RESOURCE_IDS["TAB_REELS"]).click()
        random_sleep(2, 4)
    except:
        logger.info("Gagal masuk tab Reels, lanjutkan saja")

    for _ in range(3):
        time.sleep(random.uniform(1.0, 2.5))
        dismiss_popups(d)
        human_swipe(d, 'up', speed='fast', distance=random.randint(800, 1100))
        random_sleep(0.3, 0.7)

    start_time = time.time()
    like_count = 0

    while time.time() - start_time < duration:
        try:
            dismiss_popups(d)

            ad_reel = d(text=RESOURCE_IDS["REEL_AD_LABEL_TEXT"])
            if not ad_reel.exists:
                ad_reel = d.xpath(RESOURCE_IDS["REEL_AD_XPATH"])
            if ad_reel.exists:
                logger.info("Iklan Reel, skip...")
                human_swipe(d, 'up', speed='fast', distance=random.randint(800, 1100))
                random_sleep(0.3, 0.7)
                continue

            follow_btn = d(resourceId="com.instagram.android:id/inline_follow_button")
            if not follow_btn.exists:
                follow_btn = d(text="Follow")
            can_interact = follow_btn.exists

            watch_time = random.uniform(2, 12)
            time.sleep(watch_time)

            if can_interact:
                if random.random() < like_prob and (max_likes == 0 or like_count < max_likes):
                    like_btn = d(resourceId=RESOURCE_IDS["REEL_LIKE"])
                    if like_btn.exists:
                        like_btn.click()
                        logger.info("Like reel (tombol).")
                    else:
                        _reel_like_fallback(d)
                    like_count += 1
                    logger.info(f"Like reel. ({like_count}/{max_likes if max_likes>0 else 'unlimited'})")
                    random_sleep(0.3, 0.7)

                if random.random() < repost_prob:
                    repost_btn = _find_reel_action_button(d, RESOURCE_IDS["REEL_REPOST_DESC"], "Repost")
                    if repost_btn:
                        repost_btn.click()
                        random_sleep(0.5, 1)
                        logger.info("Repost reel.")
                    else:
                        logger.info("Tombol repost tidak terlihat, lewati.")

                # [DIUPDATE] pakai _find_comment_button_reel yang baru
                if random.random() < comment_prob:
                    comment_btn = _find_comment_button_reel(d)
                    if comment_btn:
                        comment_btn.click()
                        random_sleep(1.0, 2.0)
                        post_comment(d, is_reel=True,
                                     comment_promosi_ratio=comment_promosi_ratio)
                    else:
                        logger.info("Tombol komentar tidak muncul, lewati.")
            else:
                logger.info("Reel dari akun di-follow, lewati interaksi.")

            human_swipe(d, 'up', speed='fast', distance=random.randint(900, 1300))
            random_sleep(0.5, 1.5)

        except Exception:
            logger.exception("Error di reel loop")
            try:
                human_swipe(d, 'up', speed='fast', distance=random.randint(900, 1300))
                random_sleep(0.5, 1.5)
            except:
                pass

def _find_reel_action_button(d, target_id_or_desc, log_label: str):
    """Cari tombol (resourceId atau description) dengan swipe kecil berulang."""
    if target_id_or_desc != "Comment":
        btn = d(resourceId=target_id_or_desc)
        if btn.exists:
            return btn

    btn = d(description=target_id_or_desc)
    if btn.exists:
        return btn

    for _ in range(3):
        human_swipe(d, 'up', distance=random.randint(100, 200), speed='fast')
        random_sleep(0.5)
        if target_id_or_desc != "Comment":
            btn = d(resourceId=target_id_or_desc)
            if btn.exists:
                return btn
        btn = d(description=target_id_or_desc)
        if btn.exists:
            return btn

    return None

# ---------- komentar ----------

def post_comment(d, is_reel: bool = False, comment_promosi_ratio: float = 0.2,
                 forced_comment: str = None):
    """
    Tulis dan kirim komentar.
    forced_comment: isi teks langsung (untuk boost mode), abaikan bank komentar.
    """
    try:
        comment_btn = None
        for attempt in range(3):
            if not is_reel:
                comment_btn = d(resourceId=RESOURCE_IDS["FEED_COMMENT"])
                if comment_btn.exists:
                    break
            else:
                comment_btn = _find_comment_button_reel(d)
                if comment_btn:
                    break
                comment_btn = None
            logger.info("Tombol komentar belum terlihat, scroll kecil...")
            human_swipe(d, 'up', distance=random.randint(180, 250), speed='fast')
            random_sleep(0.5, 1.0)

        if comment_btn is None or not comment_btn.exists:
            logger.warning("Tombol komentar tidak ditemukan.")
            if not d(resourceId=RESOURCE_IDS["FEED_LIKE"]).exists:
                d.press("back")
            return

        os.makedirs("screenshots", exist_ok=True)
        timestamp1 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipe = "reel" if is_reel else "feed"
        filename1 = f"screenshots/{timestamp1}_{tipe}_post.png"
        d.screenshot(filename1)
        logger.info(f"Bukti postingan: {filename1}")

        comment_btn.click()
        random_sleep(1.5, 2.5)

        field = None
        for _ in range(10):
            field = d(resourceId=RESOURCE_IDS["COMMENT_FIELD"])
            if field.exists:
                break
            time.sleep(0.5)
        if field is None or not field.exists:
            logger.warning("Kolom komentar tidak muncul.")
            d.press("back")
            return

        # Pilih komentar — forced_comment untuk boost, normal untuk patroli biasa
        if forced_comment:
            comment = forced_comment
        elif random.random() < comment_promosi_ratio:
            comment = random.choice(COMMENTS_PROMOSI)
        else:
            comment = random.choice(COMMENTS_NATURAL)

        field.click()
        random_sleep(0.5)
        human_typing(d, comment)
        random_sleep(0.5, 1.5)

        timestamp2 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = comment[:30]
        for c in r'<>:"/\|?* ':
            safe = safe.replace(c, "_")
        filename2 = f"screenshots/{timestamp2}_{tipe}_presend_{safe}.png"
        d.screenshot(filename2)
        logger.info(f"Bukti sebelum kirim: {filename2}")

        send_btn = d(resourceId=RESOURCE_IDS["COMMENT_POST_ICON"])
        if send_btn.exists:
            send_btn.click()
            logger.info(f"Komentar terkirim: {comment}")
        else:
            d.press("enter")
            logger.info(f"Komentar terkirim (Enter): {comment}")

        handle = d(resourceId="com.instagram.android:id/bottom_sheet_drag_handle_prism")
        if handle.exists:
            bounds = handle.info['bounds']
            start_x = (bounds['left'] + bounds['right']) // 2
            start_y = (bounds['top'] + bounds['bottom']) // 2
            end_y = d.window_size()[1] - 10
            d.swipe(start_x, start_y, start_x, end_y, duration=0.4)
            logger.info("Sheet komentar ditutup dengan drag handle.")
            random_sleep(1, 2)
        else:
            if is_reel:
                d.press("back")
                random_sleep(0.5, 1.0)
                d.press("back")
                random_sleep(0.5, 1.0)
            else:
                d.press("back")
                random_sleep(1, 2)

    except Exception:
        logger.exception("Gagal komen")
        try:
            handle = d(resourceId="com.instagram.android:id/bottom_sheet_drag_handle_prism")
            if handle.exists:
                bounds = handle.info['bounds']
                start_x = (bounds['left'] + bounds['right']) // 2
                start_y = (bounds['top'] + bounds['bottom']) // 2
                end_y = d.window_size()[1] - 10
                d.swipe(start_x, start_y, start_x, end_y, duration=0.4)
            else:
                d.press("back")
        except:
            pass
