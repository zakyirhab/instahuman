import random
import time

# Konstanta kecepatan swipe (detik)
SWIPE_SPEED = {
    "fast": (0.15, 0.3),
    "normal": (0.3, 0.6),
    "slow": (0.7, 1.2)
}

def random_sleep(min_seconds=0.5, max_seconds=3.0):
    """Jeda acak agar tidak terlalu robotik."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_swipe(d, direction='up', distance=None, speed='fast'):
    """
    Scroll alami dengan kecepatan yang bisa diatur.
    speed: 'fast' (default), 'normal', atau 'slow'.
    """
    w, h = d.window_size()
    start_x = random.randint(w//4, 3*w//4)
    if distance is None:
        # Jarak scroll: untuk fast lebih jauh, biar terasa tegas
        if speed == 'fast':
            distance = random.randint(h//3, h//2)
        else:
            distance = random.randint(h//5, h//3)
    
    if direction == 'up':
        start_y = random.randint(h//2, 3*h//4)  # mulai dari agak bawah
        end_y = start_y - distance
    else:
        start_y = random.randint(h//4, h//2)
        end_y = start_y + distance

    min_dur, max_dur = SWIPE_SPEED.get(speed, (0.3, 0.9))
    duration = random.uniform(min_dur, max_dur)
    d.swipe(start_x, start_y, start_x, end_y, duration)

def human_typing(d, text):
    """Mengetik huruf per huruf dengan jeda acak."""
    for char in text:
        d.send_keys(char)
        time.sleep(random.uniform(0.05, 0.25))

# Daftar RESOURCE_ID Instagram yang sudah diverifikasi
IG_PACKAGE = "com.instagram.android"
RESOURCE_IDS = {
    # Navigasi Utama
    "TAB_HOME": "com.instagram.android:id/feed_tab",
    "TAB_SEARCH": "com.instagram.android:id/search_tab",
    "TAB_REELS": "com.instagram.android:id/clips_tab",
    "DM_BUTTON": "com.instagram.android:id/direct_tab",

    # Story (pakai resourceId avatar_image_view, tanpa description)
    "STORY_RING": "com.instagram.android:id/avatar_image_view",
    "STORY_NEXT": None,  # Fallback tap kanan

    # Feed
    "FEED_LIKE": "com.instagram.android:id/row_feed_button_like",
    "FEED_COMMENT": "com.instagram.android:id/row_feed_button_comment",
    "FEED_REPOST": "com.instagram.android:id/reposts_ufi_icon",
    "FEED_AD_LABEL": "com.instagram.android:id/secondary_label",

    # Reels
    "REEL_LIKE": "com.instagram.android:id/like_button",
    "REEL_COMMENT": "com.instagram.android:id/comment_button",
    "REEL_REPOST_DESC": "Repost",
    "REEL_AD_LABEL_TEXT": "Ad",

    # Notifikasi
    "NOTIFICATION_BUTTON": "com.instagram.android:id/notification",
    "NOTIFICATION_FOLLOW_BACK": None,

        # Komentar
    "COMMENT_FIELD": "com.instagram.android:id/edittext_container",
    "COMMENT_POST_ICON": "com.instagram.android:id/layout_comment_thread_post_button_icon",   # untuk feed & reel
    "COMMENT_POST": None,  # tidak terpakai
}
