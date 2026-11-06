"""Site build pieces for push alerts: bell + panel HTML, service worker, web app manifest, icons.

The bell only renders when newsroom/firebase-web.json is enabled and complete, so the site never
shows a control that can't work. The manifest and icons always ship (they also make "Add to Home
Screen" look right on phones).
"""
import json
from html import escape
from pathlib import Path

from notify_logic import DEFAULT_FREQ, DEFAULT_TOPICS, FREQUENCIES, TOPICS

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "firebase-web.json"

BELL_SVG = ('<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M12 3a6 6 0 0 0-6 6v3.6l-1.6 2.7A1 1 0 0 0 5.3 17h13.4a1 1 0 0 0 .9-1.7L18 12.6V9a6 6 0 0 0-6-6Z" '
            'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M9.5 19.5a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>')
SHARE_SVG = ('<svg viewBox="0 0 24 24" width="15" height="15" aria-label="Share" role="img"><path d="M12 3v12M8 7l4-4 4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
             '<path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>')


def config():
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    fb = c.get("firebase") or {}
    if not c.get("enabled") or not c.get("vapidKey") or not all(fb.get(k) for k in ("apiKey", "authDomain", "projectId", "messagingSenderId", "appId")):
        return None
    return c


def bell():
    """Bell button + panel, placed in the masthead next to Follow. Empty when alerts are off."""
    c = config()
    if not c:
        return ""
    client = {"sdk": c["sdk"], "firebase": c["firebase"], "vapidKey": c["vapidKey"],
              "defaults": {"topics": DEFAULT_TOPICS, "freq": DEFAULT_FREQ}}
    freqs = "".join(f'<label class="mfn-opt"><input type="radio" name="freq" value="{v}"><span>{escape(lbl)}</span></label>' for v, lbl in FREQUENCIES)
    topics = "".join(f'<label class="mfn-opt"><input type="checkbox" name="topic" value="{v}"><span>{escape(lbl)}</span></label>' for v, lbl, _ in TOPICS)
    return f"""<button type="button" class="mfn-bell" id="mfn-bell" aria-label="News alerts: off" aria-haspopup="dialog" aria-expanded="false" aria-controls="mfn-panel">{BELL_SVG}<span class="mfn-dot" aria-hidden="true"></span></button>
<div class="mfn" id="mfn-panel" role="dialog" aria-modal="false" aria-labelledby="mfn-h" hidden>
  <div class="mfn-head"><h2 id="mfn-h" tabindex="-1">News alerts</h2><button type="button" class="mfn-x" aria-label="Close">&times;</button></div>
  <p class="mfn-status" id="mfn-status" role="status" aria-live="polite"></p>
  <div data-v="unsupported" hidden><p>This browser can't receive web alerts. Chrome, Edge, Firefox and Safari can, on desktop and Android.</p></div>
  <div data-v="ios" hidden><p>On iPhone and iPad, alerts work once MetaFlora News is on your Home Screen:</p>
    <ol class="mfn-steps"><li>In Safari, tap Share {SHARE_SVG}</li><li>Choose <b>Add to Home Screen</b>, then <b>Add</b></li><li>Open MetaFlora News from your Home Screen and tap the bell</li></ol>
    <p class="mfn-note">Needs iOS or iPadOS 16.4 or later.</p></div>
  <div data-v="denied" hidden><p>Alerts are blocked for this site. Allow notifications for news.metaflora.xyz in your browser's site settings, then reload this page.</p></div>
  <form data-v="prefs" hidden>
    <fieldset><legend>How often</legend>{freqs}</fieldset>
    <fieldset class="mfn-topics"><legend>Topics</legend>{topics}</fieldset>
    <div class="mfn-actions">
      <button type="submit" class="mfn-primary" data-act="enable">Turn on alerts</button>
      <button type="button" class="mfn-primary" data-act="save" hidden>Save preferences</button>
      <button type="button" class="mfn-ghost" data-act="disable" hidden>Turn off alerts</button>
    </div>
    <p class="mfn-note">Free, no account. We keep an anonymous device ID, this browser's push address and your choices; no name or email. <a href="/how-we-report/#alerts">Privacy</a></p>
  </form>
</div>
<script type="application/json" id="mfn-push-config">{json.dumps(client)}</script>"""


def head_tags(css_version):
    """Manifest + icons in every page head; the alerts module only when alerts are on."""
    tags = ('<link rel="manifest" href="/manifest.webmanifest">'
            '<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">'
            '<meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-title" content="MetaFlora News">'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black">')
    if config():
        tags += f'<script type="module" src="/assets/notify.js?v={css_version}"></script>'
    return tags


def write_static(out, write):
    """manifest.webmanifest, icons, and the service worker (only when alerts are on)."""
    from PIL import Image
    icons = out / "assets" / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    cube = Image.open(HERE / "assets" / "metaflora-cube.png").convert("RGBA")
    for name, size, pad in (("icon-192.png", 192, 0.16), ("icon-512.png", 512, 0.16), ("maskable-512.png", 512, 0.26),
                            ("apple-touch-icon.png", 180, 0.14), ("badge-96.png", 96, 0.1)):
        p = icons / name
        if p.exists():
            continue
        bg = Image.new("RGBA", (size, size), (19, 19, 19, 255) if name != "badge-96.png" else (0, 0, 0, 0))
        h = round(size * (1 - 2 * pad))
        c = cube.resize((round(h * cube.width / cube.height), h), Image.LANCZOS)
        if name == "badge-96.png":  # monochrome silhouette for Android's status bar
            alpha = c.split()[3]
            c = Image.new("RGBA", c.size, (255, 255, 255, 255)); c.putalpha(alpha)
        bg.alpha_composite(c, ((size - c.width) // 2, (size - c.height) // 2))
        bg.save(p, optimize=True)
    manifest = {
        "name": "MetaFlora News", "short_name": "MetaFlora News", "id": "/", "start_url": "/?source=homescreen", "scope": "/",
        "display": "standalone", "background_color": "#131313", "theme_color": "#131313",
        "description": "Cannabis industry news: policy, markets, science and the business of cannabis. Morning and evening editions.",
        "icons": [{"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }
    write("manifest.webmanifest", json.dumps(manifest, indent=1))
    c = config()
    sw = out / "firebase-messaging-sw.js"
    if not c:
        if sw.exists():
            sw.unlink()
        return
    write("firebase-messaging-sw.js", f"""// MetaFlora News push service worker. Shows alerts sent through Firebase Cloud Messaging.
// No caching, no offline mode: it only handles push messages and alert clicks.
importScripts("https://www.gstatic.com/firebasejs/{c['sdk']}/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/{c['sdk']}/firebase-messaging-compat.js");
firebase.initializeApp({json.dumps(c['firebase'])});
const messaging = firebase.messaging();
// Messages carry a webpush.notification block, so the SDK displays them and opens fcm_options.link on click.
messaging.onBackgroundMessage(() => {{}});
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
""")
