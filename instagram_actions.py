import random
import time
import os
import datetime
from human_behavior import *
from comment_bank import COMMENTS_NATURAL, COMMENTS_PROMOSI

def back_to_home(d, max_backs=5):
    """Tekan Back berkali-kali hingga kembali ke beranda (feed)."""
    for _ in range(max_backs):
        # Cek apakah kita sudah di Home dengan melihat tab Home
        home_tab = d(resourceId=RESOURCE_IDS["TAB_HOME"])
        if home_tab.exists:
            # Sudah di Home, tidak perlu back lagi
            return
        # Jika belum, tekan back
        d.press("back")
        time.sleep(0.5)
    # Fallback: klik tab Home jika setelah max_backs masih belum
    home_tab = d(resourceId=RESOURCE_IDS["TAB_HOME"])
    if home_tab.exists:
        home_tab.click()

def natural_session(d):
    """Sesi yang bisa diatur untuk testing modul satu per satu."""
    print("=== Memulai sesi natural ===")
    d.app_start("com.instagram.android")
    random_sleep(5, 8)

    # ========== PENGATURAN TEST MODE ==========
    # Pilih salah satu angka:
    # 1 = hanya notifikasi + DM + story
    # 2 = hanya story
    # 3 = hanya feed (like/komen bisa dimatikan manual)
    # 4 = hanya reels
    # 5 = full flow seperti biasa (sesuai pengacakan)
    TEST_MODE = 4   # <-- GANTI ANGKA INI SESUAI YANG INGIN DITEST

    if TEST_MODE == 1:
        check_notifications(d)
        check_dm(d)
        watch_stories(d)

    elif TEST_MODE == 2:
        watch_stories(d)

    elif TEST_MODE == 3:
        # Untuk matikan like/komen, ubah probabilitas di interact_feed jadi 0
        interact_feed(d, duration=60)

    elif TEST_MODE == 4:
        scroll_reels(d, duration=60)

    elif TEST_MODE == 5:
        # Full flow biasa
        roll = random.random()
        if roll < 0.3:
            check_notifications(d)
            check_dm(d)
            watch_stories(d)
        elif roll < 0.6:
            watch_stories(d)
        else:
            print("Langsung ke konten...")
        interact_feed(d, duration=60)
        if random.random() < 0.7:
            scroll_reels(d, duration=60)

    # Idle lalu tutup
    random_sleep(10, 20)
    d.app_stop("com.instagram.android")
    print("=== Sesi selesai ===")
def check_notifications(d):
    """Cek notifikasi, folback jika ada."""
    print("Mengecek notifikasi...")
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
                    print("Follow Back diberikan.")
        else:
            print("Tidak ada notifikasi.")
    except Exception as e:
        print(f"Error notifikasi: {e}")
    finally:
        go_home(d)

def check_dm(d):
    """Cek DM, hanya lihat, tidak balas. Pastikan kembali ke home."""
    print("Mengecek DM...")
    try:
        dm_btn = d(resourceId=RESOURCE_IDS["DM_BUTTON"])
        if dm_btn.exists:
            dm_btn.click()
            random_sleep(2, 4)
            for _ in range(random.randint(1, 2)):
                human_swipe(d, 'up')
                random_sleep(1, 2)
            # Tidak perlu buka pesan
        else:
            print("Tidak ada DM baru.")
    except Exception as e:
        print(f"Error DM: {e}")
    finally:
        go_home(d)  # ⬅️ Pastikan pulang

def watch_stories(d):
    """Nonton story orang lain yang punya unseen (1 of ...), bukan yang sudah habis (0 of ...)."""
    print("Menonton story...")
    try:
        all_rings = d(resourceId=RESOURCE_IDS["STORY_RING"])
        if not all_rings.exists:
            print("Tidak ada story ring sama sekali.")
            return

        target = None
        for elem in all_rings:
            desc = (elem.info.get('contentDescription') or '').lower()
            # Abaikan milik sendiri / add story / kamera / tanpa deskripsi
            if not desc or 'add' in desc or 'your' in desc or 'camera' in desc:
                continue
            # Hanya story orang lain yang mengandung kata "story" 
            # DAN TIDAK ada "0 of" (artinya ada unseen, minimal 1)
            if 'story' in desc and '0 of' not in desc:
                target = elem
                break  # ambil story pertama yang lolos (paling kiri setelah punya sendiri)

        if target is None:
            print("Tidak ada story dengan unseen baru.")
            return

        print(f"Buka story: {target.info.get('contentDescription')}")
        target.click()
        random_sleep(2, 4)

        # Tonton story satu per satu
        for _ in range(random.randint(5, 15)):
            ad_story = d(resourceId="com.instagram.android:id/reel_item_sponsored_label_footer_pill")
            if ad_story.exists:
                print("Story iklan, skip...")
                _next_story(d)
                continue
            random_sleep(1, 3)   # tonton
            _next_story(d)

        # Setelah habis, tekan back sekali untuk kembali ke feed
        d.press("back")
        random_sleep(1, 2)

    except Exception as e:
        print(f"Story error: {e}")
        try:
            d.press("back")
        except:
            pass

def _next_story(d):
    """Lanjut ke story berikutnya."""
    if RESOURCE_IDS.get("STORY_NEXT"):
        next_btn = d(resourceId=RESOURCE_IDS["STORY_NEXT"])
        if next_btn.exists:
            next_btn.click()
            return
    # Fallback tap kanan
    w, h = d.window_size()
    d.click(w - 200, h // 2)
    random_sleep(0.5, 1)

def interact_feed(d, duration=60, like_prob=0.3, comment_prob=0.03, repost_prob=0.05, comment_promosi_ratio=0.2):
    """Scroll feed, interaksi dengan probabilitas yang bisa diatur."""
    print("Memulai interaksi feed...")
    start_time = time.time()
    while time.time() - start_time < duration:
        sponsored = d(text="Sponsored")
        if sponsored.exists:
            print("Iklan sponsored, skip...")
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
                    print("Like diberikan.")
                    random_sleep(0.3, 0.7)

            if random.random() < repost_prob:
                repost_btn = d.xpath('//*[@resource-id="com.instagram.android:id/reposts_ufi_icon"]')
                if repost_btn.exists:
                    repost_btn.click()
                    random_sleep(0.5, 1)
                    d.click(540, 1200)
                    print("Repost.")
                    random_sleep(0.5, 1)

            if random.random() < comment_prob:
                post_comment(d, is_reel=False, comment_promosi_ratio=comment_promosi_ratio)
                go_home(d)
        else:
            print("Akun sudah di-follow, lewati interaksi.")

def scroll_reels(d, duration=60, like_prob=0.3, comment_prob=0.05, repost_prob=0.0, comment_promosi_ratio=0.2):
    """Scroll Reels dengan probabilitas yang bisa diatur."""
    print("Mulai nonton Reels...")
    try:
        d(resourceId=RESOURCE_IDS["TAB_REELS"]).click()
        random_sleep(2, 4)
    except:
        print("Gagal masuk tab Reels, lanjutkan saja")

    start_time = time.time()
    while time.time() - start_time < duration:
        try:
            ad_reel = d(text=RESOURCE_IDS["REEL_AD_LABEL_TEXT"])
            if ad_reel.exists:
                print("Iklan Reel, skip...")
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
                        print("Like reel.")
                        random_sleep(0.3, 0.7)

                if random.random() < comment_prob:
                    post_comment(d, is_reel=True, comment_promosi_ratio=comment_promosi_ratio)

                if random.random() < repost_prob:
                    repost_btn = d(description=RESOURCE_IDS["REEL_REPOST_DESC"])
                    if repost_btn.exists:
                        repost_btn.click()
                        random_sleep(0.5, 1)
                        d.press("back")
                        print("Repost reel.")
            else:
                print("Reel dari akun di-follow, lewati interaksi.")

            human_swipe(d, 'up', speed='fast', distance=random.randint(900, 1300))
            random_sleep(0.5, 1.5)

        except Exception as e:
            print(f"Error di reel loop: {e}")
            try:
                human_swipe(d, 'up', speed='fast', distance=random.randint(900, 1300))
                random_sleep(0.5, 1.5)
            except:
                pass

def post_comment(d, is_reel=False, comment_promosi_ratio=0.2):
    """Komen dengan 2 screenshot, kirim via tombol. Rasio promosi bisa diatur."""
    try:
        # Screenshot 1: postingan/reel
        os.makedirs("screenshots", exist_ok=True)
        timestamp1 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tipe = "reel" if is_reel else "feed"
        filename1 = f"screenshots/{timestamp1}_{tipe}_post.png"
        d.screenshot(filename1)
        print(f"Bukti postingan: {filename1}")

        comment_btn = d(resourceId=RESOURCE_IDS["FEED_COMMENT"]) if not is_reel else d(resourceId=RESOURCE_IDS["REEL_COMMENT"])
        if not comment_btn.exists:
            print("Tombol komentar tidak ditemukan.")
            return
        comment_btn.click()
        random_sleep(1.5, 2.5)

        # Tunggu kolom komentar
        field = None
        for _ in range(10):
            field = d(resourceId=RESOURCE_IDS["COMMENT_FIELD"])
            if field.exists:
                break
            time.sleep(0.5)
        if not field or not field.exists:
            print("Kolom komentar tidak muncul.")
            d.press("back")
            return

        # Pilih komentar
        if random.random() < comment_promosi_ratio:
            comment = random.choice(COMMENTS_PROMOSI)
        else:
            comment = random.choice(COMMENTS_NATURAL)

        field.click()
        random_sleep(0.5)
        human_typing(d, comment)
        random_sleep(0.5, 1.5)

        # Screenshot 2: sebelum kirim
        timestamp2 = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = comment[:30]
        for c in r'<>:"/\|?* ':
            safe = safe.replace(c, "_")
        filename2 = f"screenshots/{timestamp2}_{tipe}_presend_{safe}.png"
        d.screenshot(filename2)
        print(f"Bukti sebelum kirim: {filename2}")

        send_btn = d(resourceId=RESOURCE_IDS["COMMENT_POST_ICON"])
        if send_btn.exists:
            send_btn.click()
            print(f"Komentar terkirim: {comment}")
        else:
            d.press("enter")
            print(f"Komentar terkirim (Enter): {comment}")

        d.press("back")
        random_sleep(1, 2)

    except Exception as e:
        print(f"Gagal komen: {e}")
        try:
            d.press("back")
        except:
            pass

def go_home(d):
    """Kembali ke feed dengan aman: back sampai tab Home muncul, atau klik paksa."""
    for _ in range(3):
        d.press("back")
        time.sleep(0.5)
        if d(resourceId=RESOURCE_IDS["TAB_HOME"]).exists:
            return
    # Fallback: klik tab Home langsung
    home = d(resourceId=RESOURCE_IDS["TAB_HOME"])
    if home.exists:
        home.click()
        time.sleep(1)
