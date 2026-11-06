"""Tests for MetaFlora News push alerts. Run: python -m unittest discover -s tests

Pure logic (topics, matching, payloads, digest, bundling) plus the dispatcher end to end against an
in-memory fake of Firestore and FCM: de-duplication, dry run vs live, dead-token cleanup, admin-only
tests, manual-send confirmation, drafts/scheduled/old stories, and that errors never raise.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "newsroom"))
import notify_logic as L  # noqa: E402

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)


def art(id_, cat="Policy", breaking=False, hours_ago=1, **kw):
    pub = (NOW - timedelta(hours=hours_ago)).isoformat()
    return {"id": id_, "cat": cat, "breaking": breaking, "published": pub, "edition": "2026-11-06-am",
            "headline": f"Headline {id_}", "dek": f"Dek for {id_}", "rank": kw.pop("rank", 1), **kw}


def dev(i, topics=("policy",), freq="all", enabled=True, token=None):
    return {"_id": f"u{i}", "uid": f"u{i}", "token": token or f"tok-{i}-" + "x" * 30, "topics": list(topics), "freq": freq, "enabled": enabled}


class Logic(unittest.TestCase):
    def test_every_section_maps_to_one_topic(self):
        cats = ["Policy", "Federal", "Hemp", "Markets", "Europe", "States", "Science", "Tech"]
        for c in cats:
            self.assertIn(c, L.CAT_TO_TOPIC, c)
        self.assertEqual(len(L.CAT_TO_TOPIC), len(cats))

    def test_topics_match_firestore_rules(self):
        rules = (ROOT / "firebase" / "firestore.rules").read_text()
        for t in L.TOPIC_IDS:
            self.assertIn(f"'{t}'", rules)
        for f in L.FREQ_IDS:
            self.assertIn(f"'{f}'", rules)

    def test_matching(self):
        a = art("a", "Hemp")
        self.assertTrue(L.wants(dev(1, ["hemp"]), a))
        self.assertFalse(L.wants(dev(1, ["policy"]), a))
        self.assertFalse(L.wants(dev(1, ["hemp"], freq="breaking"), a))   # breaking-only ignores normal stories
        self.assertFalse(L.wants(dev(1, ["hemp"], freq="digest"), a))     # digest waits for the digest
        self.assertFalse(L.wants(dev(1, ["hemp"], enabled=False), a))
        b = art("b", "Science", breaking=True)
        self.assertTrue(L.wants(dev(1, ["breaking"], freq="breaking"), b))
        self.assertTrue(L.wants(dev(1, ["science"], freq="all"), b))     # still a new story in their topic
        self.assertFalse(L.wants(dev(1, ["policy"], freq="digest"), b))

    def test_audience_dedupes_tokens(self):
        a = art("a")
        same = "tok-same-" + "x" * 30
        self.assertEqual(len(L.audience([dev(1, token=same), dev(2, token=same), dev(3)], a)), 2)

    def test_eligibility(self):
        self.assertTrue(L.eligible(art("a"), NOW)[0])
        self.assertFalse(L.eligible(art("a", draft=True), NOW)[0])
        self.assertFalse(L.eligible(art("a", push=False), NOW)[0])
        self.assertFalse(L.eligible(art("a", hours_ago=-3), NOW)[0])    # scheduled for later
        self.assertFalse(L.eligible(art("a", hours_ago=72), NOW)[0])    # old story re-committed

    def test_payload_uses_real_copy_and_stable_key(self):
        a = art("aurora-deal", breaking=True)
        p = L.payload(a)
        self.assertEqual(p["title"], "Breaking: Headline aurora-deal")
        self.assertEqual(p["body"], "Dek for aurora-deal")
        self.assertEqual(p["key"], "2026-11-06-aurora-deal")
        self.assertTrue(p["link"].startswith("https://news.metaflora.xyz/2026/11/06/aurora-deal/?utm_source=push"))
        self.assertEqual(L.send_key(dict(a, headline="Edited headline")), p["key"])  # edits keep the key
        self.assertTrue(L.payload(a, test=True)["title"].startswith("[TEST] "))
        self.assertEqual(p["image"], "https://news.metaflora.xyz/og/aurora-deal.jpg")
        long = L.payload(art("x", dek="word " * 80))
        self.assertLessEqual(len(long["body"]), 160)

    def test_bundling(self):
        items = [art(f"s{i}") for i in range(4)]
        self.assertEqual(len(L.edition_payloads(items[:2])), 2)
        b = L.edition_payloads(items)
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0]["title"], "4 new stories in your topics")
        self.assertEqual(len(b[0]["keys"]), 4)

    def test_digest(self):
        arts = [art("p1", "Policy"), art("h1", "Hemp"), art("old", "Policy", hours_ago=30)]
        today = L.digest_articles(arts, NOW)
        self.assertEqual({a["id"] for a in today}, {"p1", "h1"})
        d = L.digest_for(dev(1, ["policy"], freq="digest"), today, "2026-11-06")
        self.assertIn("1 story", d["title"])
        self.assertIsNone(L.digest_for(dev(1, ["policy"], freq="all"), today, "2026-11-06"))
        self.assertIsNone(L.digest_for(dev(1, ["tech"], freq="digest"), today, "2026-11-06"))

    def test_dead_token_rule_is_conservative(self):
        self.assertTrue(L.is_dead_token("UnregisteredError"))
        self.assertFalse(L.is_dead_token("InvalidArgumentError"))
        self.assertFalse(L.is_dead_token("QuotaExceededError"))


# ---------- fakes for the dispatcher ----------

class AlreadyExists(Exception):
    pass


class Doc:
    def __init__(self, store, col, id_):
        self.store, self.col, self.id = store, col, id_

    def create(self, data):
        if self.id in self.store[self.col]:
            raise AlreadyExists()
        self.store[self.col][self.id] = dict(data)

    def update(self, data):
        self.store[self.col][self.id].update(data)

    def delete(self):
        self.store[self.col].pop(self.id, None)

    def get(self):
        d = self.store[self.col].get(self.id)
        return type("Snap", (), {"exists": d is not None, "id": self.id, "to_dict": lambda s: dict(d)})()


class Col:
    def __init__(self, store, name, flt=None):
        self.store, self.name, self.flt = store, name, flt

    def document(self, id_):
        return Doc(self.store, self.name, id_)

    def where(self, field, op, value):
        return Col(self.store, self.name, (field, value))

    def stream(self):
        for k, v in list(self.store[self.name].items()):
            if not self.flt or v.get(self.flt[0]) == self.flt[1]:
                yield type("Snap", (), {"exists": True, "id": k, "to_dict": lambda s, v=v: dict(v)})()

    def add(self, data):
        self.store[self.name][f"auto{len(self.store[self.name])}"] = data

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self


class DB:
    def __init__(self):
        self.store = {c: {} for c in ("devices", "sends", "admins", "tests", "clicks")}

    def collection(self, name):
        return Col(self.store, name)


class UnregisteredError(Exception):
    pass


class FakeMessaging:
    def __init__(self, dead=()):
        self.calls, self.dead = [], set(dead)

    MulticastMessage = staticmethod(lambda **k: k)
    WebpushConfig = staticmethod(lambda **k: k)
    WebpushNotification = staticmethod(lambda **k: k)
    WebpushFCMOptions = staticmethod(lambda **k: k)
    WebpushNotificationAction = staticmethod(lambda *a, **k: a)

    def send_each_for_multicast(self, msg, dry_run=False):
        self.calls.append({"tokens": list(msg["tokens"]), "dry": dry_run, "title": msg["webpush"]["notification"]["title"],
                           "link": msg["webpush"]["fcm_options"]["link"]})
        rs = []
        for t in msg["tokens"]:
            ok = t not in self.dead
            rs.append(type("R", (), {"success": ok, "exception": None if ok else UnregisteredError()})())
        return type("BR", (), {"responses": rs})()


class Dispatcher(unittest.TestCase):
    def setUp(self):
        import push
        self.push = push
        self.tmp = tempfile.TemporaryDirectory()
        self.push.ARTICLES = Path(self.tmp.name)
        self.push.wait_live = lambda url, timeout=600: True
        self.db = DB()
        self.msg = FakeMessaging()
        self.fb = {"db": self.db, "fs": type("FS", (), {"SERVER_TIMESTAMP": "ts"}), "msg": self.msg, "AlreadyExists": AlreadyExists}
        self.real_now = L.datetime

    def tearDown(self):
        self.tmp.cleanup()
        self.push.LIVE = False

    def write(self, a):
        p = Path(self.tmp.name) / f"{L.send_key(a)}.json"
        p.write_text(json.dumps(a))
        return str(p)

    def add_dev(self, d):
        self.db.store["devices"][d["_id"]] = {k: v for k, v in d.items() if k != "_id"}

    def run_cmd(self, *argv, live=False):
        self.push.LIVE = live
        self.push.connect = lambda: self.fb
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.push.main(list(argv))
        return buf.getvalue()

    def fresh(self, id_, **kw):
        a = art(id_, **kw)
        a["published"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        return a

    def test_dry_run_by_default_and_no_duplicates(self):
        self.add_dev(dev(1, ["policy"]))
        f = self.write(self.fresh("a1"))
        out = self.run_cmd("articles", f)
        self.assertIn("DRY RUN", out)
        self.assertTrue(all(c["dry"] for c in self.msg.calls))
        self.assertEqual(len(self.msg.calls), 1)
        out2 = self.run_cmd("articles", f, live=True)              # retried or republished
        self.assertIn("already sent", out2)
        self.assertEqual(len(self.msg.calls), 1)

    def test_live_send_matches_preferences_and_removes_dead_tokens(self):
        self.add_dev(dev(1, ["policy"]))
        self.add_dev(dev(2, ["hemp"]))
        self.add_dev(dev(3, ["policy"], token="dead-token-" + "x" * 30))
        self.add_dev(dev(4, ["policy"], enabled=False))
        self.msg.dead = {"dead-token-" + "x" * 30}
        self.run_cmd("articles", self.write(self.fresh("p1", cat="Policy")), live=True)
        sent_to = self.msg.calls[0]["tokens"]
        self.assertEqual(len(sent_to), 2)                            # u1 and the dead u3; not hemp-only u2, not disabled u4
        self.assertNotIn("u3", self.db.store["devices"])             # dead subscription cleaned up
        self.assertIn("u1", self.db.store["devices"])
        log = self.db.store["sends"]["2026-11-06-p1".replace("2026-11-06", self.fresh("p1")["published"][:10])]
        self.assertEqual((log["sent"], log["failed"], log["removed"], log["status"]), (1, 1, 1, "sent"))

    def test_bundles_three_or_more_and_breaking_alone(self):
        self.add_dev(dev(1, ["breaking", "policy"]))
        files = [self.write(self.fresh(f"n{i}", rank=i + 2)) for i in range(3)]
        files.append(self.write(self.fresh("brk", breaking=True, cat="Science")))
        self.run_cmd("articles", *files, live=True)
        titles = [c["title"] for c in self.msg.calls]
        self.assertEqual(titles[0], "Breaking: Headline brk")
        self.assertIn("3 new stories in your topics", titles)
        self.assertEqual(len(titles), 2)

    def test_skips_drafts_scheduled_and_opted_out(self):
        self.add_dev(dev(1, ["policy"]))
        a = self.fresh("d1", draft=True)
        b = self.fresh("s1")
        b["published"] = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        c = self.fresh("o1", push=False)
        out = self.run_cmd("articles", self.write(a), self.write(b), self.write(c), live=True)
        self.assertEqual(self.msg.calls, [])
        self.assertIn("draft", out)
        self.assertIn("scheduled", out)
        self.assertIn("push disabled", out)

    def test_test_mode_only_reaches_admins(self):
        self.add_dev(dev(1, ["policy"]))
        self.add_dev(dev(2, ["policy"]))
        self.db.store["admins"]["google-admin"] = {"devices": ["u2"]}
        self.write(self.fresh("t1"))
        self.run_cmd("test", "latest")
        self.assertEqual(len(self.msg.calls), 1)
        self.assertEqual(len(self.msg.calls[0]["tokens"]), 1)
        self.assertTrue(self.msg.calls[0]["title"].startswith("[TEST] "))
        self.assertFalse(self.msg.calls[0]["dry"])
        self.assertEqual(self.db.store["sends"], {})                # tests never consume the real send

    def test_manual_send_needs_exact_confirmation(self):
        self.add_dev(dev(1, ["policy"]))
        a = self.fresh("m1", push=False)
        self.write(a)
        key = L.send_key(a)
        out = self.run_cmd("send", key, "--confirm", "yes", live=True)
        self.assertIn("Refused", out)
        self.assertEqual(self.msg.calls, [])
        self.run_cmd("send", key, "--confirm", key, live=True)
        self.assertEqual(len(self.msg.calls), 1)

    def test_errors_never_raise(self):
        def boom():
            raise RuntimeError("firestore down")
        self.push.connect = boom
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.push.main(["articles", "x.json"])
        self.assertIn("ERROR (ignored", buf.getvalue())

    def test_digest_once_per_day(self):
        self.add_dev(dev(1, ["policy"], freq="digest"))
        self.write(self.fresh("g1"))
        self.run_cmd("digest", live=True)
        self.run_cmd("digest", live=True)
        self.assertEqual(len(self.msg.calls), 1)
        self.assertIn("Today in cannabis news", self.msg.calls[0]["title"])


if __name__ == "__main__":
    unittest.main()
