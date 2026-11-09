"""/admin/notifications/: the alerts dashboard (noindex, disallowed in robots.txt, not in the sitemap).

Static page; the numbers come from Firestore in the browser, readable only by accounts listed in
admins/ (Firestore rules). Sending stays in GitHub Actions, where the server credentials live.
"""
import json
from html import escape

import notify_logic as L
import notify_site
import stocks
import templates as T

REPO_ACTIONS = "https://github.com/Tryptolemus/news/actions/workflows/notify.yml"


def build(arts, write):
    c = notify_site.config()
    if not c:
        body = ('<div class="page-h"><h1>News alerts</h1><p class="dek">Push alerts are not switched on yet. '
                'See NOTIFICATIONS.md in the repository to connect Firebase.</p></div>')
        write("admin/notifications/index.html", T.page("News alerts admin", body, path="/admin/notifications/", robots="noindex, nofollow"))
        return
    recent = [dict(L.payload(a), cat=a["cat"], breaking=bool(a.get("breaking")), push=a.get("push", True),
                   topic=L.topic_for(a), published=a["published"]) for a in arts[:24]]
    cfg = {"sdk": c["sdk"], "firebase": c["firebase"], "topics": [[t, lbl] for t, lbl, _ in L.TOPICS],
           "freqs": [list(f) for f in L.FREQUENCIES], "recent": recent, "actions": REPO_ACTIONS, "xready": L.x_ready(arts) + stocks.x_posts(T.ctx.get("market")),
           "built": __import__("time").strftime("%Y%m%d%H%M")}
    body = f"""<div class="page-h adm-h"><h1>News alerts</h1><p class="dek">Subscribers, deliveries and clicks. Sending happens in GitHub Actions; this page only reads.</p></div>
<section class="block adm-x" id="x" aria-labelledby="x-h"><h2 class="sec-label" id="x-h">Ready for X</h2>
  <p class="mfn-note">The latest edition's top stories, written for @MetaFloraLabs. Tap <b>Post on X</b>: X opens with the text and link filled in; press Post. For a story X hasn't seen yet, the card can take 10–20 seconds to appear in the compose window (or type a space after the link); either way X attaches it when the post is published. Free, from your own account. The image under each post is the card X will show with it.</p>
  <ol class="adm-xlist" id="adm-xlist"></ol></section>
<div id="adm" class="adm">
  <section class="adm-auth"><button type="button" class="mfn-primary" id="adm-signin">Sign in with Google</button>
    <p class="mfn-note" id="adm-who"></p></section>
  <div id="adm-body" hidden>
    <section class="adm-kpis" id="adm-kpis" aria-label="Totals"></section>
    <section class="block"><h2 class="sec-label">Subscribers by choice</h2><div class="adm-two"><div id="adm-freq"></div><div id="adm-topics"></div></div></section>
    <section class="block"><h2 class="sec-label">New subscriptions, last 30 days</h2><div id="adm-growth" class="adm-growth"></div></section>
    <section class="block"><h2 class="sec-label">Notifications sent</h2><div class="stk-table-wrap"><table class="stk-table adm-table" id="adm-sends"></table></div></section>
    <section class="block"><h2 class="sec-label">Your test devices</h2><div id="adm-devices"></div></section>
    <section class="block"><h2 class="sec-label">Preview and send</h2>
      <p class="mfn-note">Pick a story to see the alert readers would get. To send a test to your own devices, preview the audience, or send manually,
      open <a href="{REPO_ACTIONS}" target="_blank" rel="noopener">Notifications in GitHub Actions</a>, click <b>Run workflow</b> and choose the action.
      A manual send asks you to type the article key again to confirm, and every article is sent at most once.</p>
      <label class="adm-pick">Story <select id="adm-article"></select></label>
      <div class="adm-preview" id="adm-preview" aria-live="polite"></div></section>
  </div>
</div>
<script type="application/json" id="adm-config">{json.dumps(cfg)}</script>
<script type="module" src="/assets/admin.js?v={T.CSS_VERSION}"></script>"""
    write("admin/notifications/index.html", T.page("News alerts admin", body, path="/admin/notifications/", robots="noindex, nofollow",
                                                   desc="MetaFlora News alerts dashboard."))
