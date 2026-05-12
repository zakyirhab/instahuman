import random
import time
import os
import datetime
import logging
from human_behavior import *
from comment_bank import COMMENTS_NATURAL, COMMENTS_PROMOSI

logger = logging.getLogger(__name__)

# ---------- navigasi ----------
def go_home(d):
    """Kembali ke feed dengan aman: back sampai tab Home muncul, atau klik paksa."""
    for _ in range(3):
        d.press("back")
        time.sleep(0.5)
        if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
            return
    home = d(resourceId=RESOURCE_IDS["TAB_HOME"])
    if home.exists:
        home.click()
        time.sleep(1)

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
    """Menonton semua story orang lain sampai benar-benar habis (tak terbatas)."""
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
            # Hanya story yang punya unseen (ada angka >0 sebelum "of")
            if 'story' in desc and '0 of' not in desc:
                target = elem
                break

        if target is None:
            logger.info("Tidak ada story dengan unseen baru.")
            return

        logger.info(f"Buka story: {target.info.get('contentDescription')}")
        target.click()
        random_sleep(2, 4)

        # Loop tanpa batas sampai story habis & Instagram kembali ke feed
        max_safety = 100  # pengaman anti infinite loop
        count = 0
        while count < max_safety:
            count += 1
            # Cek apakah story viewer sudah menutup (sudah di feed)
            if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
                logger.info("Semua story sudah ditonton (kembali ke feed).")
                break

            # Cek story iklan
            ad_story = d(resourceId="com.instagram.android:id/reel_item_sponsored_label_footer_pill")
            if ad_story.exists:
                logger.info("Story iklan, skip...")
                _next_story(d)
                continue

            random_sleep(1, 3)   # tonton story ini
            _next_story(d)

    except Exception:
        logger.exception("Story error")
    finally:
        # Pastikan kembali ke home jika masih di story viewer
        try:
            if not d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
                d.press("back")
                random_sleep(1, 2)
        except:
            pass
            
def _next_story(d):
    if RESOURCE_IDS.get("STORY_NEXT"):
        next_btn = d(resourceId=RESOURCE_IDS["STORY_NEXT"])
        if next_btn.exists:
            next_btn.click()
            return
    w, h = d.window_size()
    d.click(w - 200, h // 2)
    random_sleep(0.5, 1)

# ---------- feed ----------
def interact_feed(d, duration: int = 60, like_prob: float = 0.3,
                  comment_prob: float = 0.03, repost_prob: float = 0.05,
                  comment_promosi_ratio: float = 0.2) -> None:
    logger.info("Memulai interaksi feed...")
    start_time = time.time()
    while time.time() - start_time < duration:
        sponsored = d(text="Sponsored")
        if sponsored.exists:
            logger.info("Iklan sponsored, skip...")
            human_swipe(d, 'up', speed='fast')
            random_sleep(0.3, 0.7)
            continue

        for _ in range(random.randint(1, 2)):
            human_swipe(d, 'up', speed='fast')
            random_sleep(0.5, 1.5)

        follow_btn = d(resourceId="com.instagram.android:id/inline_follow_button")
        can_interact = follow_btn.exists

        if can_interact:
            if random.random() < like_prob:
                like_btn = d(resourceId=RESOURCE_IDS["FEED_LIKE"])
                if like_btn.exists:
                    like_btn.click()
                    logger.info("Like diberikan.")
                    random_sleep(0.3, 0.7)

            if random.random() < repost_prob:
                repost_btn = d.xpath('//*[@resource-id="com.instagram.android:id/reposts_ufi_icon"]')
                if repost_btn.exists:
                    repost_btn.click()
                    random_sleep(0.5, 1)
                    # Cari tombol "Feed" pada share sheet
                    feed_share = d(text="Feed")
                    if not feed_share.exists:
                        feed_share = d(description="Feed")
                    if feed_share.exists:
                        feed_share.click()
                        logger.info("Repost.")
                        random_sleep(0.5, 1)
                    else:
                        d.press("back")   # tidak ada tombol, tutup saja

            if random.random() < comment_prob:
                post_comment(d, is_reel=False, comment_promosi_ratio=comment_promosi_ratio)
                go_home(d)
        else:
            logger.info("Akun sudah di-follow, lewati interaksi.")

# ---------- reels ----------
def scroll_reels(d, duration: int = 60, like_prob: float = 0.3,
                 comment_prob: float = 0.05, repost_prob: float = 0.0,
                 comment_promosi_ratio: float = 0.2) -> None:
    logger.info("Mulai nonton Reels...")
    try:
        d(resourceId=RESOURCE_IDS["TAB_REELS"]).click()
        random_sleep(2, 4)
    except:
        logger.info("Gagal masuk tab Reels, lanjutkan saja")

    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            ad_reel = d(text=RESOURCE_IDS["REEL_AD_LABEL_TEXT"])
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
                if random.random() < like_prob:
                    like_btn = d(resourceId=RESOURCE_IDS["REEL_LIKE"])
                    if like_btn.exists:
                        like_btn.click()
                        logger.info("Like reel.")
                        random_sleep(0.3, 0.7)

                if random.random() < comment_prob:
                    post_comment(d, is_reel=True, comment_promosi_ratio=comment_promosi_ratio)

                if random.random() < repost_prob:
                    repost_btn = d(description=RESOURCE_IDS["REEL_REPOST_DESC"])
                    if repost_btn.exists:
                        repost_btn.click()
                        random_sleep(0.5, 1)
                        d.press("back")
                        logger.info("Repost reel.")
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

# ---------- komentar ----------
def post_comment(d, is_reel: bool = False, comment_promosi_ratio: float = 0.2):
    try:
        os.makedirs("screenshots", exist_ok=True)
        timestamp1 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipe = "reel" if is_reel else "feed"
        filename1 = f"screenshots/{timestamp1}_{tipe}_post.png"
        d.screenshot(filename1)
        logger.info(f"Bukti postingan: {filename1}")

        comment_btn = d(resourceId=RESOURCE_IDS["FEED_COMMENT"]) if not is_reel else d(resourceId=RESOURCE_IDS["REEL_COMMENT"])
        if not comment_btn.exists:
            logger.warning("Tombol komentar tidak ditemukan.")
            return
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

        if random.random() < comment_promosi_ratio:
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

        d.press("back")
        random_sleep(1, 2)

    except Exception:
        logger.exception("Gagal komen")
        try:
            d.press("back")
        except:
            pass
