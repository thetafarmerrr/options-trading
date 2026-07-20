#!/usr/bin/env python3
"""
多平台碎片分发 — Twitter + Reddit 一键发送

用法：
  python3 tools/post_fragment.py                  # 发送所有待发碎片
  python3 tools/post_fragment.py --dry-run        # 仅预览，不发送
  python3 tools/post_fragment.py --platform twitter  # 仅发 Twitter
  python3 tools/post_fragment.py --platform reddit   # 仅发 Reddit

凭证：tools/fragment_credentials.json（不入 git）
碎片：data/fragments.json
"""

import json, sys, os, argparse, time, hmac, hashlib, base64, urllib.parse
from pathlib import Path
from datetime import datetime
from random import getrandbits

import requests

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
FRAGMENTS_FILE = DATA_DIR / "fragments.json"
CRED_FILE = SCRIPT_DIR / "fragment_credentials.json"


# ── OAuth 1.0a（Twitter）────────────────────────────────────────

def _oauth1_sign(method, url, params, consumer_secret, token_secret=""):
    """OAuth 1.0a 签名"""
    param_string = "&".join(
        f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items())
    )
    base = "&".join([
        method.upper(),
        _pct(url),
        _pct(param_string),
    ])
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    sig = base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    ).decode()
    return sig


def _pct(s):
    return urllib.parse.quote(str(s), safe="")


def _oauth1_header(method, url, params, cred):
    """生成 OAuth 1.0a Authorization header"""
    oauth = {
        "oauth_consumer_key": cred["api_key"],
        "oauth_nonce": hex(getrandbits(64))[2:],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": cred["access_token"],
        "oauth_version": "1.0",
    }
    all_params = {**oauth, **params}
    oauth["oauth_signature"] = _oauth1_sign(
        method, url, all_params,
        cred["api_secret"], cred["access_secret"]
    )
    header = "OAuth " + ", ".join(
        f'{_pct(k)}="{_pct(v)}"' for k, v in oauth.items()
    )
    return header


# ── Twitter API v2 ──────────────────────────────────────────────

def post_twitter(content, cred, dry_run=False):
    """发送推文"""
    if dry_run:
        print(f"  🐦 [DRY-RUN] Twitter: {content[:60]}…")
        return True

    url = "https://api.twitter.com/2/tweets"
    body = {"text": content}
    headers = {
        "Authorization": _oauth1_header("POST", url, {}, cred),
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(url, json=body, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            data = r.json()
            tid = data.get("data", {}).get("id", "?")
            print(f"  🐦 Twitter ✅  id={tid}")
            return True
        else:
            print(f"  🐦 Twitter ❌ {r.status_code}: {r.text[:120]}")
            return False
    except Exception as e:
        print(f"  🐦 Twitter ❌ {e}")
        return False


# ── Reddit API ──────────────────────────────────────────────────

def _reddit_auth(cred):
    """Reddit OAuth2 script app → access token"""
    try:
        r = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "password", "username": cred["username"],
                  "password": cred["password"]},
            auth=requests.auth.HTTPBasicAuth(cred["client_id"], cred["client_secret"]),
            headers={"User-Agent": cred["user_agent"]},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["access_token"]
    except Exception:
        pass
    return None


def post_reddit(subreddit, title, content, cred, dry_run=False):
    """发帖到 Reddit"""
    if dry_run:
        print(f"  👽 [DRY-RUN] r/{subreddit}: {title[:50]}…")
        return True

    token = _reddit_auth(cred)
    if not token:
        print(f"  👽 Reddit ❌ 认证失败")
        return False

    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent": cred["user_agent"],
    }
    body = {
        "sr": subreddit,
        "kind": "self",
        "title": title,
        "text": content,
    }
    try:
        r = requests.post(
            "https://oauth.reddit.com/api/submit",
            headers=headers, data=body, timeout=15,
        )
        if r.status_code == 200:
            j = r.json()
            if j.get("success"):
                pid = j.get("json", {}).get("data", {}).get("id", "?")
                print(f"  👽 Reddit ✅  r/{subreddit}  id={pid}")
                return True
        print(f"  👽 Reddit ❌ {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        print(f"  👽 Reddit ❌ {e}")
        return False


# ── 碎片文件管理 ────────────────────────────────────────────────

def load_fragments():
    """加载碎片文件"""
    if FRAGMENTS_FILE.exists():
        return json.loads(FRAGMENTS_FILE.read_text())
    return {"pending": [], "posted": []}


def save_fragments(data):
    """保存碎片文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRAGMENTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_credentials():
    """加载凭证"""
    if not CRED_FILE.exists():
        print("❌ 未找到凭证文件 tools/fragment_credentials.json")
        print("   请从模板填入 API 密钥。")
        return None
    return json.loads(CRED_FILE.read_text())


# ── 主入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="多平台碎片分发 — Twitter + Reddit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅预览，不实际发送"
    )
    parser.add_argument(
        "--platform", type=str, default="both",
        choices=["twitter", "reddit", "both"],
        help="目标平台（默认 both）"
    )
    args = parser.parse_args()

    creds = load_credentials()
    if not creds:
        sys.exit(1)

    data = load_fragments()
    pending = data.get("pending", [])

    if not pending:
        print("📭 无待发碎片。")
        return

    print(f"\n{'═'*50}")
    print(f"  🚀 碎片分发  {'[DRY-RUN]' if args.dry_run else ''}")
    print(f"  {'═'*50}")

    success = []
    remaining = []

    for frag in pending:
        pid = frag.get("id", "?")
        platform = frag.get("platform", "")

        print(f"\n  [{pid}] ", end="")

        if args.platform != "both" and platform != args.platform:
            print(f"⏭ 跳过（platform={platform}）")
            remaining.append(frag)
            continue

        if platform == "twitter":
            ok = post_twitter(frag["content"], creds["twitter"], args.dry_run)
        elif platform == "reddit":
            ok = post_reddit(
                frag.get("subreddit", "thetagang"),
                frag["title"],
                frag["content"],
                creds["reddit"],
                args.dry_run,
            )
        else:
            print(f"⚠️ 未知平台 {platform}")
            remaining.append(frag)
            continue

        if ok:
            frag["posted_at"] = datetime.now().isoformat()
            success.append(frag)
        else:
            remaining.append(frag)

    posted = data.get("posted", [])
    if not args.dry_run:
        posted.extend(success)
        data["pending"] = remaining
        data["posted"] = posted[-200:]
        save_fragments(data)
    else:
        # dry-run 不写回——不发、不动
        pass

    print(f"\n  {'─'*40}")
    print(f"  ✅ {len(success)} 发送  ⏳ {len(remaining)} 待发")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    main()
