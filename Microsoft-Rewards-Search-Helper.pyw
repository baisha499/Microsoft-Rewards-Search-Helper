# -*- coding: utf-8 -*-
import os
import random
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import urllib.request
import json
import zipfile
import shutil
import tempfile
import re
import subprocess

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== 全局配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EDGE_DRIVER_PATH = os.path.join(BASE_DIR, "msedgedriver.exe")
CHROME_DRIVER_PATH = os.path.join(BASE_DIR, "chromedriver.exe")

USER_DATA_DIR_EDGE = os.path.join(BASE_DIR, "user_data_edge")
USER_DATA_DIR_CHROME = os.path.join(BASE_DIR, "user_data_chrome")
os.makedirs(USER_DATA_DIR_EDGE, exist_ok=True)
os.makedirs(USER_DATA_DIR_CHROME, exist_ok=True)

DICT_PATH = os.path.join(BASE_DIR, "dictionary.txt")

CFT_LAST_KNOWN_GOOD_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "last-known-good-versions-with-downloads.json"
)

EDGE_DRIVER_DOWNLOAD_URLS = [
    "https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip",
]


# ========== 版本号比较工具 ==========
def _version_tuple(v):
    if not v:
        return None
    try:
        parts = re.findall(r"\d+", str(v))
        if not parts:
            return None
        return tuple(int(x) for x in parts)
    except Exception:
        return None


def _compare_versions(a, b):
    ta = _version_tuple(a)
    tb = _version_tuple(b)
    if ta is None or tb is None:
        return None
    length = max(len(ta), len(tb))
    ta = ta + (0,) * (length - len(ta))
    tb = tb + (0,) * (length - len(tb))
    if ta > tb:
        return 1
    elif ta < tb:
        return -1
    else:
        return 0


# ========== 驱动版本检测与更新 ==========
def _run_no_window(cmd, timeout=10):
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        startupinfo=startupinfo
    )


def get_chrome_driver_version(driver_path):
    if not os.path.exists(driver_path):
        return None
    try:
        result = _run_no_window([driver_path, "--version"])
        output = (result.stdout or "") + (result.stderr or "")
        match = re.search(r"ChromeDriver\s+([\d.]+)", output)
        return match.group(1) if match else None
    except Exception:
        return None


def get_edge_driver_version(driver_path):
    if not os.path.exists(driver_path):
        return None
    try:
        result = _run_no_window([driver_path, "--version"])
        output = (result.stdout or "") + (result.stderr or "")
        match = re.search(r"WebDriver\s+([\d.]+)", output)
        return match.group(1) if match else None
    except Exception:
        return None


def get_local_browser_version(browser):
    try:
        import winreg
        if browser == "edge":
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Edge\BLBeacon"
                )
                version, _ = winreg.QueryValueEx(key, "version")
                winreg.CloseKey(key)
                return version
            except FileNotFoundError:
                pass
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"Software\WOW6432Node\Microsoft\EdgeUpdate\Clients"
                    r"\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}"
                )
                version, _ = winreg.QueryValueEx(key, "pv")
                winreg.CloseKey(key)
                return version
            except Exception:
                pass
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"Software\Microsoft\Edge\BLBeacon"
                )
                version, _ = winreg.QueryValueEx(key, "version")
                winreg.CloseKey(key)
                return version
            except Exception:
                pass
            return None
        elif browser == "chrome":
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for path in (
                    r"Software\Google\Chrome\BLBeacon",
                    r"Software\WOW6432Node\Google\Chrome\BLBeacon",
                ):
                    try:
                        key = winreg.OpenKey(root, path)
                        version, _ = winreg.QueryValueEx(key, "version")
                        winreg.CloseKey(key)
                        return version
                    except FileNotFoundError:
                        continue
            return None
    except Exception:
        return None


def get_latest_chrome_driver_info(log_func=None):
    try:
        if log_func:
            log_func("🔍 查询 Chrome for Testing 官方 API ...")
        req = urllib.request.Request(
            CFT_LAST_KNOWN_GOOD_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        data = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                data = json.loads(raw.decode(enc))
                break
            except Exception:
                continue
        if data is None:
            if log_func:
                log_func("⚠️ Chrome for Testing API 返回内容无法解析为 JSON")
            return None, None

        stable = data.get("channels", {}).get("Stable", {})
        version = stable.get("version")
        downloads = stable.get("downloads", {}).get("chromedriver", [])

        win64_url = None
        for item in downloads:
            if item.get("platform") == "win64":
                win64_url = item.get("url")
                break

        if log_func and version:
            log_func(f"✅ Chrome for Testing 返回最新版本: {version}")
        return version, win64_url
    except Exception as e:
        if log_func:
            log_func(f"⚠️ Chrome for Testing API 请求失败: {e}")
        return None, None


def get_latest_edge_driver_version(browser_major_version, log_func=None):
    if not browser_major_version:
        if log_func:
            log_func("⚠️ 未获取到本地 Edge 主版本号")
        return None, None

    major = str(browser_major_version).split(".")[0]

    def _parse_version(raw_bytes):
        for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-8", "latin-1"):
            try:
                text = raw_bytes.decode(enc)
                text = text.replace("\ufeff", "").strip()
                m = re.search(r"\d+\.\d+\.\d+\.\d+", text)
                if m:
                    return m.group(0)
            except Exception:
                continue
        return None

    url = f"https://msedgedriver.microsoft.com/LATEST_RELEASE_{major}"
    try:
        if log_func:
            log_func(f"🔍 尝试 msedgedriver.microsoft.com/LATEST_RELEASE_{major} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        version = _parse_version(raw)
        if version:
            if log_func:
                log_func(f"✅ 官方端点返回最新版本: {version}")
            download_url = EDGE_DRIVER_DOWNLOAD_URLS[0].format(version=version)
            return version, download_url
        else:
            if log_func:
                log_func(f"⚠️ 官方端点返回内容无法解析为版本号（前 40 字节: {raw[:40]!r}）")
    except Exception as e:
        if log_func:
            log_func(f"⚠️ 官方端点请求失败: {e}")

    try:
        api_url = "https://edgeupdates.microsoft.com/api/products?view=enterprise"
        if log_func:
            log_func("🔍 尝试 Edge 更新 API: edgeupdates.microsoft.com ...")
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        data = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                data = json.loads(raw.decode(enc))
                break
            except Exception:
                continue
        if data is None:
            if log_func:
                log_func("⚠️ Edge 更新 API 返回内容无法解析为 JSON")
            return None, None

        candidates = []
        for product in data:
            if not isinstance(product, dict):
                continue
            if product.get("Product") != "Stable":
                continue
            for release in product.get("Releases", []):
                arch = str(release.get("Architecture", "")).lower()
                if "x64" in arch:
                    ver = release.get("ProductVersion")
                    if ver:
                        candidates.append(str(ver))

        for ver in candidates:
            if ver.startswith(major + "."):
                if log_func:
                    log_func(f"✅ Edge 更新 API 返回: {ver}")
                download_url = EDGE_DRIVER_DOWNLOAD_URLS[0].format(version=ver)
                return ver, download_url

        if candidates:
            ver = candidates[0]
            if log_func:
                log_func(f"⚠️ 未找到 {major}.x 版本，使用最新 x64 版本: {ver}")
            download_url = EDGE_DRIVER_DOWNLOAD_URLS[0].format(version=ver)
            return ver, download_url
        else:
            if log_func:
                log_func("⚠️ Edge 更新 API 返回中没有找到 x64 稳定版")
    except Exception as e:
        if log_func:
            log_func(f"⚠️ Edge 更新 API 请求失败: {e}")

    if log_func:
        log_func("❌ 所有方式均无法获取 Edge 最新版本号")
    return None, None


def get_local_edge_browser_major():
    ver = get_local_browser_version("edge")
    if not ver:
        return None
    try:
        return str(ver).split(".")[0]
    except Exception:
        return None


def download_and_extract_driver(url, driver_path, driver_exe_name):
    tmp_dir = tempfile.mkdtemp(prefix="driver_update_")
    zip_path = os.path.join(tmp_dir, "driver.zip")
    backup_path = driver_path + ".bak"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(zip_path, "wb") as f:
                shutil.copyfileobj(resp, f)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        found_exe = None
        for root_dir, _, files in os.walk(tmp_dir):
            if driver_exe_name in files:
                found_exe = os.path.join(root_dir, driver_exe_name)
                break

        if not found_exe:
            return False, "解压后未找到驱动可执行文件"

        if os.path.exists(driver_path):
            try:
                shutil.copy2(driver_path, backup_path)
            except Exception:
                pass
            os.remove(driver_path)

        shutil.copy2(found_exe, driver_path)
        return True, "更新成功"

    except Exception as e:
        return False, f"更新失败: {e}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
        pycache_dir = os.path.join(BASE_DIR, "__pycache__")
        if os.path.exists(pycache_dir):
            shutil.rmtree(pycache_dir, ignore_errors=True)
        try:
            for name in os.listdir(BASE_DIR):
                if name.startswith("driver_update_"):
                    shutil.rmtree(os.path.join(BASE_DIR, name), ignore_errors=True)
        except Exception:
            pass


# ========== 驱动初始化 ==========
def init_driver(browser, headless=False, use_mobile_ua=False, page_load_strategy=None):
    if browser == "edge":
        options = EdgeOptions()
        options.add_argument(f"--user-data-dir={USER_DATA_DIR_EDGE}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--disable-gpu")
        if page_load_strategy:
            options.page_load_strategy = page_load_strategy
        if use_mobile_ua:
            mobile_ua = ("Mozilla/5.0 (Linux; Android 11; SM-G991B) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/114.0.5735.196 Mobile Safari/537.36 "
                         "Edg/114.0.1823.58")
            options.add_argument(f"--user-agent={mobile_ua}")
            options.add_argument("--window-size=412,915")
        if headless:
            options.add_argument("--headless")
        service = EdgeService(EDGE_DRIVER_PATH)
        return webdriver.Edge(service=service, options=options)

    elif browser == "chrome":
        options = ChromeOptions()
        options.add_argument(f"--user-data-dir={USER_DATA_DIR_CHROME}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--disable-gpu")
        if page_load_strategy:
            options.page_load_strategy = page_load_strategy
        if use_mobile_ua:
            mobile_ua = ("Mozilla/5.0 (Linux; Android 11; SM-G991B) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/114.0.5735.196 Mobile Safari/537.36 "
                         "Edg/114.0.1823.58")
            options.add_argument(f"--user-agent={mobile_ua}")
            options.add_argument("--window-size=412,915")
        if headless:
            options.add_argument("--headless")
        service = ChromeService(CHROME_DRIVER_PATH)
        return webdriver.Chrome(service=service, options=options)
    else:
        raise ValueError("不支持的浏览器类型")


# ========== 读取词典（只读） ==========
def load_words():
    if not os.path.exists(DICT_PATH):
        return []
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def pick_words(count):
    words = load_words()
    if not words:
        return []
    if len(words) < count:
        random.shuffle(words)
        return (words * (count // len(words) + 1))[:count]
    return random.sample(words, count)


def type_with_delay(element, text, delay=0.5):
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)


def detect_available_browsers():
    available = []
    if os.path.exists(EDGE_DRIVER_PATH):
        available.append("edge")
    if os.path.exists(CHROME_DRIVER_PATH):
        available.append("chrome")
    return available


# ========== 主界面 ==========
class App:
    def __init__(self, root):
        self.root = root
        root.title("必应自动刷积分助手v2.2 (支持Edge/Chrome)")
        root.geometry("540x560")
        root.resizable(False, False)

        self.chrome_update_available = False
        self.edge_update_available = False
        self.chrome_latest_version = None
        self.edge_latest_version = None

        self.status_var = tk.StringVar()
        tk.Label(root, textvariable=self.status_var, fg="blue", relief="sunken",
                 anchor="w", padx=5).pack(fill="x", padx=10, pady=5)

        self.available_browsers = detect_available_browsers()
        if not self.available_browsers:
            self.browser_var = tk.StringVar(value="")
            self.log("❌ 未找到任何浏览器驱动，请将 msedgedriver.exe 或 chromedriver.exe 放入程序目录！")
            messagebox.showerror("驱动缺失", "未找到 Edge 或 Chrome 驱动，请将对应的驱动文件放入程序目录。")
        else:
            default_browser = "edge" if "edge" in self.available_browsers else "chrome"
            self.browser_var = tk.StringVar(value=default_browser)

        top_frame = tk.Frame(root)
        top_frame.pack(pady=10, padx=10, fill="x")

        tk.Label(top_frame, text="选择浏览器:", font=("微软雅黑", 10)).grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        if self.available_browsers:
            self.browser_combo = ttk.Combobox(top_frame, textvariable=self.browser_var,
                                              values=self.available_browsers,
                                              state="readonly", width=12)
            self.browser_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        else:
            self.browser_combo = ttk.Combobox(top_frame, textvariable=self.browser_var,
                                              values=[], state="disabled", width=12)
            self.browser_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        btn_frame = tk.Frame(top_frame)
        btn_frame.grid(row=0, column=2, padx=10, pady=5, sticky="e")

        self.btn_login = tk.Button(btn_frame, text="🔑 登录账号", command=self.login_task,
                                   width=10, bg="#FFD700")
        self.btn_login.grid(row=0, column=0, padx=2, pady=4)

        self.btn_5 = tk.Button(btn_frame, text="▶ 5次",
                               command=lambda: self.start_search(5), width=6)
        self.btn_5.grid(row=0, column=1, padx=2, pady=4)

        self.btn_10 = tk.Button(btn_frame, text="▶ 10次",
                                command=lambda: self.start_search(10), width=6)
        self.btn_10.grid(row=0, column=2, padx=2, pady=4)

        self.btn_20 = tk.Button(btn_frame, text="▶ 20次",
                                command=lambda: self.start_search(20), width=6)
        self.btn_20.grid(row=0, column=3, padx=2, pady=4)

        custom_frame = tk.Frame(top_frame)
        custom_frame.grid(row=1, column=0, columnspan=3, pady=5)

        tk.Label(custom_frame, text="自定义次数:", font=("微软雅黑", 10)).grid(
            row=0, column=0, padx=4, pady=4, sticky="e")
        self.custom_entry = tk.Entry(custom_frame, width=10)
        self.custom_entry.grid(row=0, column=1, padx=4, pady=4)
        self.custom_entry.insert(0, "5")

        self.btn_custom = tk.Button(custom_frame, text="▶ 自定义搜索",
                                    command=self.start_custom_search, width=12)
        self.btn_custom.grid(row=0, column=2, padx=4, pady=4)

        self.btn_dailyset = tk.Button(custom_frame, text="📋 每日打卡",
                                      command=self.start_daily_set,
                                      width=12, bg="white")
        self.btn_dailyset.grid(row=0, column=3, padx=4, pady=4)

        update_frame = tk.LabelFrame(root, text="驱动版本管理", font=("微软雅黑", 9),
                                     padx=8, pady=5)
        update_frame.pack(fill="x", padx=10, pady=(0, 5))

        tk.Label(update_frame, text="Chrome:", font=("微软雅黑", 9)).grid(
            row=0, column=0, padx=4, pady=3, sticky="e")
        self.chrome_version_var = tk.StringVar(value="检测中...")
        tk.Label(update_frame, textvariable=self.chrome_version_var,
                 font=("微软雅黑", 9), fg="gray", anchor="w", width=32).grid(
            row=0, column=1, padx=4, pady=3, sticky="w")
        self.btn_update_chrome = tk.Button(
            update_frame, text="更新Chrome驱动", width=14,
            command=self.update_chrome_driver, state="disabled")
        self.btn_update_chrome.grid(row=0, column=2, padx=6, pady=3)

        tk.Label(update_frame, text="Edge:", font=("微软雅黑", 9)).grid(
            row=1, column=0, padx=4, pady=3, sticky="e")
        self.edge_version_var = tk.StringVar(value="检测中...")
        tk.Label(update_frame, textvariable=self.edge_version_var,
                 font=("微软雅黑", 9), fg="gray", anchor="w", width=32).grid(
            row=1, column=1, padx=4, pady=3, sticky="w")
        self.btn_update_edge = tk.Button(
            update_frame, text="更新Edge驱动", width=14,
            command=self.update_edge_driver, state="disabled")
        self.btn_update_edge.grid(row=1, column=2, padx=6, pady=3)

        self.log_area = scrolledtext.ScrolledText(root, height=12, state='disabled', wrap=tk.WORD)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        if not self.available_browsers:
            self.btn_login.config(state="disabled")
            self.btn_5.config(state="disabled")
            self.btn_10.config(state="disabled")
            self.btn_20.config(state="disabled")
            self.btn_custom.config(state="disabled")
            self.btn_dailyset.config(state="disabled")
            self.update_status("驱动缺失，无法使用")
        else:
            self.btn_login.config(state="normal")
            self.btn_5.config(state="disabled")
            self.btn_10.config(state="disabled")
            self.btn_20.config(state="disabled")
            self.btn_custom.config(state="disabled")
            self.btn_dailyset.config(state="disabled")

            browser = self.browser_var.get()
            user_dir = USER_DATA_DIR_EDGE if browser == "edge" else USER_DATA_DIR_CHROME
            if os.path.exists(user_dir) and os.listdir(user_dir):
                self.update_status(f"检测到 {browser} 用户数据，可搜索")
                self.log(f"ℹ️ {browser} 用户数据目录已存在，若已登录可直接搜索")
                self.btn_5.config(state="normal")
                self.btn_10.config(state="normal")
                self.btn_20.config(state="normal")
                self.btn_custom.config(state="normal")
                self.btn_dailyset.config(state="normal")
            else:
                self.update_status(f"未登录 {browser}，请点击“登录账号”")
                self.log(f"ℹ️ {browser} 用户数据目录为空，需要登录")

        if not os.path.exists(DICT_PATH):
            self.log("⚠️ 警告：找不到 dictionary.txt，请创建并填入搜索词。")

        threading.Thread(target=self.check_driver_versions, daemon=True).start()

    def _log_threadsafe(self, msg):
        self.root.after(0, lambda m=msg: self.log(m))

    def check_driver_versions(self):
        time.sleep(0.5)

        try:
            if os.path.exists(CHROME_DRIVER_PATH):
                local_ver = get_chrome_driver_version(CHROME_DRIVER_PATH)
                latest_ver, _ = get_latest_chrome_driver_info(
                    log_func=self._log_threadsafe
                )

                if local_ver and latest_ver:
                    cmp = _compare_versions(local_ver, latest_ver)
                    if cmp == 0:
                        self.root.after(0, lambda: self.chrome_version_var.set(
                            f"本地: {local_ver}  ✅ 已是最新"))
                        self.root.after(0, lambda: self.btn_update_chrome.config(
                            text="✅ 已是最新", state="disabled", bg="#E0E0E0"))
                    elif cmp == 1:
                        self.root.after(0, lambda: self.log(
                            f"ℹ️ 本地 Chrome 驱动 ({local_ver}) 高于官方端点返回的版本 "
                            f"({latest_ver})，端点可能尚未同步，跳过更新"))
                        self.root.after(0, lambda: self.chrome_version_var.set(
                            f"本地: {local_ver}  ✅ 已是最新（端点延迟）"))
                        self.root.after(0, lambda: self.btn_update_chrome.config(
                            text="✅ 已是最新", state="disabled", bg="#E0E0E0"))
                    else:
                        self.chrome_update_available = True
                        self.chrome_latest_version = latest_ver
                        self.root.after(0, lambda: self.chrome_version_var.set(
                            f"本地: {local_ver}  ⬆ 最新: {latest_ver}"))
                        self.root.after(0, lambda: self.btn_update_chrome.config(
                            text="⬆ 更新Chrome驱动", state="normal",
                            bg="#FFA500"))
                        self.root.after(0, lambda: self.log(
                            f"🔄 ChromeDriver 有新版本: {local_ver} → {latest_ver}"))
                elif not local_ver:
                    self.root.after(0, lambda: self.chrome_version_var.set(
                        "无法读取本地版本"))
                elif not latest_ver:
                    self.root.after(0, lambda v=local_ver: self.chrome_version_var.set(
                        f"本地: {v}  (无法从官方获取最新版，详见日志)"))
                else:
                    self.root.after(0, lambda: self.chrome_version_var.set(
                        f"本地: {local_ver}"))
            else:
                self.root.after(0, lambda: self.chrome_version_var.set(
                    "未找到 chromedriver.exe"))
        except Exception as e:
            self.root.after(0, lambda e=e: self.chrome_version_var.set(
                f"检测失败: {e}"))

        try:
            if os.path.exists(EDGE_DRIVER_PATH):
                local_driver_ver = get_edge_driver_version(EDGE_DRIVER_PATH)
                major = get_local_edge_browser_major()

                if not major:
                    self.root.after(0, lambda: self.log(
                        "⚠️ 无法从注册表获取本地 Edge 浏览器版本号"))
                    self.root.after(0, lambda v=local_driver_ver: self.edge_version_var.set(
                        f"本地驱动: {v or '未知'}  (无法检测 Edge 浏览器版本)"))
                    return

                self.root.after(0, lambda m=major: self.log(
                    f"ℹ️ 本地 Edge 主版本号: {m}"))

                latest_ver, _ = get_latest_edge_driver_version(
                    major, log_func=self._log_threadsafe
                )

                if local_driver_ver and latest_ver:
                    cmp = _compare_versions(local_driver_ver, latest_ver)
                    if cmp == 0:
                        self.root.after(0, lambda: self.edge_version_var.set(
                            f"本地: {local_driver_ver}  ✅ 已是最新"))
                        self.root.after(0, lambda: self.btn_update_edge.config(
                            text="✅ 已是最新", state="disabled", bg="#E0E0E0"))
                    elif cmp == 1:
                        self.root.after(0, lambda: self.log(
                            f"ℹ️ 本地 Edge 驱动 ({local_driver_ver}) 高于官方端点返回的版本 "
                            f"({latest_ver})，端点可能尚未同步，跳过更新"))
                        self.root.after(0, lambda: self.edge_version_var.set(
                            f"本地: {local_driver_ver}  ✅ 已是最新（端点延迟）"))
                        self.root.after(0, lambda: self.btn_update_edge.config(
                            text="✅ 已是最新", state="disabled", bg="#E0E0E0"))
                    else:
                        self.edge_update_available = True
                        self.edge_latest_version = latest_ver
                        self.root.after(0, lambda: self.edge_version_var.set(
                            f"本地: {local_driver_ver}  ⬆ 最新: {latest_ver}"))
                        self.root.after(0, lambda: self.btn_update_edge.config(
                            text="⬆ 更新Edge驱动", state="normal",
                            bg="#FFA500"))
                        self.root.after(0, lambda: self.log(
                            f"🔄 EdgeDriver 有新版本: {local_driver_ver} → {latest_ver}"))
                elif not local_driver_ver:
                    self.root.after(0, lambda: self.edge_version_var.set(
                        "无法读取本地 Edge 驱动版本"))
                elif not latest_ver:
                    self.root.after(0, lambda v=local_driver_ver: self.edge_version_var.set(
                        f"本地: {v}  (无法从官方获取最新版，详见日志)"))
                else:
                    self.root.after(0, lambda: self.edge_version_var.set(
                        f"本地: {local_driver_ver}"))
            else:
                self.root.after(0, lambda: self.edge_version_var.set(
                    "未找到 msedgedriver.exe"))
        except Exception as e:
            self.root.after(0, lambda e=e: self.edge_version_var.set(
                f"检测失败: {e}"))

    def update_chrome_driver(self):
        if not self.chrome_update_available:
            messagebox.showinfo("提示", "Chrome 驱动已是最新，无需更新。")
            return

        if not messagebox.askyesno("确认更新",
                                   f"即将更新 ChromeDriver 到版本 {self.chrome_latest_version}，"
                                   f"更新完成后会自动清理缓存。是否继续？"):
            return

        self.btn_update_chrome.config(state="disabled", text="更新中...")
        self.log("⬇ 开始下载 ChromeDriver...")

        def worker():
            try:
                _, win64_url = get_latest_chrome_driver_info(
                    log_func=self._log_threadsafe
                )
                if not win64_url:
                    self.root.after(0, lambda: self.log("❌ 未找到 ChromeDriver 下载链接"))
                    self.root.after(0, lambda: self.btn_update_chrome.config(
                        state="normal", text="⬆ 更新Chrome驱动"))
                    return

                self.root.after(0, lambda: self.log(f"📦 下载地址: {win64_url[:80]}..."))
                self.root.after(0, lambda: self.update_status("正在更新 ChromeDriver..."))

                success, msg = download_and_extract_driver(
                    win64_url, CHROME_DRIVER_PATH, "chromedriver.exe")

                if success:
                    self.root.after(0, lambda v=self.chrome_latest_version: self.log(
                        f"✅ ChromeDriver 已更新到 {v}，临时文件、备份和 __pycache__ 已清理"))
                    self.root.after(0, lambda v=self.chrome_latest_version: self.chrome_version_var.set(
                        f"本地: {v}  ✅ 已是最新"))
                    self.root.after(0, lambda: self.btn_update_chrome.config(
                        state="disabled", text="✅ 已是最新", bg="#E0E0E0"))
                    self.chrome_update_available = False
                    self.root.after(0, lambda v=self.chrome_latest_version: messagebox.showinfo(
                        "更新完成",
                        f"ChromeDriver 已更新到 {v}\n\n"
                        f"已清理：\n"
                        f"  • 临时下载目录\n"
                        f"  • .bak 旧驱动备份\n"
                        f"  • __pycache__ 缓存"))
                else:
                    self.root.after(0, lambda m=msg: self.log(f"❌ {m}（缓存已清理）"))
                    self.root.after(0, lambda: self.btn_update_chrome.config(
                        state="normal", text="⬆ 重试更新Chrome驱动"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"❌ 更新出错: {e}（缓存已清理）"))
                self.root.after(0, lambda: self.btn_update_chrome.config(
                    state="normal", text="⬆ 重试更新Chrome驱动"))

        threading.Thread(target=worker, daemon=True).start()

    def update_edge_driver(self):
        if not self.edge_update_available:
            messagebox.showinfo("提示", "Edge 驱动已是最新，无需更新。")
            return

        if not messagebox.askyesno("确认更新",
                                   f"即将更新 EdgeDriver 到版本 {self.edge_latest_version}，"
                                   f"更新完成后会自动清理缓存。是否继续？"):
            return

        self.btn_update_edge.config(state="disabled", text="更新中...")
        self.log("⬇ 开始下载 EdgeDriver...")

        def worker():
            try:
                major = get_local_edge_browser_major()
                latest_ver, first_url = get_latest_edge_driver_version(
                    major, log_func=self._log_threadsafe
                )

                urls_to_try = []
                if latest_ver:
                    for tmpl in EDGE_DRIVER_DOWNLOAD_URLS:
                        urls_to_try.append(tmpl.format(version=latest_ver))
                elif first_url:
                    urls_to_try.append(first_url)

                if not urls_to_try:
                    self.root.after(0, lambda: self.log(
                        "❌ 未找到 EdgeDriver 下载链接（详见上方日志）"))
                    self.root.after(0, lambda: self.btn_update_edge.config(
                        state="normal", text="⬆ 更新Edge驱动"))
                    return

                self.root.after(0, lambda: self.update_status("正在更新 EdgeDriver..."))

                success = False
                last_msg = ""
                for url in urls_to_try:
                    self.root.after(0, lambda u=url:
                        self.log(f"📦 尝试下载: {u[:80]}..."))
                    success, last_msg = download_and_extract_driver(
                        url, EDGE_DRIVER_PATH, "msedgedriver.exe")
                    if success:
                        break
                    self.root.after(0, lambda m=last_msg:
                        self.log(f"⚠️ 该源失败: {m}"))

                if success:
                    self.root.after(0, lambda v=latest_ver: self.log(
                        f"✅ EdgeDriver 已更新到 {v}，临时文件、备份和 __pycache__ 已清理"))
                    self.root.after(0, lambda v=latest_ver: self.edge_version_var.set(
                        f"本地: {v}  ✅ 已是最新"))
                    self.root.after(0, lambda: self.btn_update_edge.config(
                        state="disabled", text="✅ 已是最新", bg="#E0E0E0"))
                    self.edge_update_available = False
                    self.root.after(0, lambda v=latest_ver: messagebox.showinfo(
                        "更新完成",
                        f"EdgeDriver 已更新到 {v}\n\n"
                        f"已清理：\n"
                        f"  • 临时下载目录\n"
                        f"  • .bak 旧驱动备份\n"
                        f"  • __pycache__ 缓存"))
                else:
                    self.root.after(0, lambda m=last_msg:
                        self.log(f"❌ {m}（缓存已清理）"))
                    self.root.after(0, lambda: self.btn_update_edge.config(
                        state="normal", text="⬆ 重试更新Edge驱动"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"❌ 更新出错: {e}（缓存已清理）"))
                self.root.after(0, lambda: self.btn_update_edge.config(
                    state="normal", text="⬆ 重试更新Edge驱动"))

        threading.Thread(target=worker, daemon=True).start()

    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self.root.update_idletasks()

    def update_status(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg))

    def start_custom_search(self):
        try:
            count = int(self.custom_entry.get().strip())
            if count <= 0:
                raise ValueError
            self.start_search(count)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数（如 1、10、50）！")

    def login_task(self):
        if not self.available_browsers:
            messagebox.showerror("错误", "没有可用的浏览器驱动！")
            return

        browser = self.browser_var.get()
        if not browser:
            messagebox.showerror("错误", "请先选择浏览器！")
            return

        if browser == "edge" and not os.path.exists(EDGE_DRIVER_PATH):
            messagebox.showerror("错误", "Edge 驱动文件缺失")
            return
        if browser == "chrome" and not os.path.exists(CHROME_DRIVER_PATH):
            messagebox.showerror("错误", "Chrome 驱动文件缺失")
            return

        self.btn_login.config(state="disabled")
        self.update_status(f"正在打开 {browser} 浏览器，请手动登录...")
        self.log(f"🔑 浏览器 ({browser}) 已打开，请手动输入账号密码登录。")

        def login_work():
            driver = None
            try:
                driver = init_driver(browser, headless=False, use_mobile_ua=False)
                driver.get("https://cn.bing.com/")
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_h")))
                self.log("✅ 页面已加载，开始检测登录状态...")

                def is_login_button_visible():
                    try:
                        login_span = driver.find_element(By.ID, "id_s")
                        return login_span.is_displayed()
                    except:
                        return False

                def has_username():
                    try:
                        name_span = driver.find_element(By.ID, "id_n")
                        return name_span.text.strip() != ""
                    except:
                        return False

                login_appeared = False
                start = time.time()
                while time.time() - start < 30:
                    if is_login_button_visible():
                        login_appeared = True
                        self.log("✅ 检测到“登录”按钮，等待登录完成...")
                        break
                    time.sleep(0.5)

                if not login_appeared:
                    if has_username():
                        self.log("✅ 未检测到“登录”按钮，但已有用户名，视为已登录。")
                    else:
                        self.log("⏰ 未检测到“登录”按钮且无用户名，可能页面异常。")
                        answer = messagebox.askyesno("登录确认", "未检测到登录状态。如果您已经登录，请点击“是”；否则点击“否”重新尝试。")
                        if not answer:
                            self.log("❌ 用户取消登录")
                            self.update_status("登录取消")
                            return
                    logged_in = True
                else:
                    logged_in = False
                    start_time = time.time()
                    timeout = 300
                    while time.time() - start_time < timeout:
                        if not is_login_button_visible() and has_username():
                            logged_in = True
                            self.log("✅ “登录”按钮已消失，且检测到用户名，登录成功！")
                            break
                        time.sleep(1)

                    if not logged_in:
                        answer = messagebox.askyesno("登录确认", "登录按钮仍未消失。如果您已经登录，请点击“是”；否则点击“否”重新尝试。")
                        if answer:
                            logged_in = True
                        else:
                            self.log("❌ 用户取消登录")
                            self.update_status("登录取消")
                            return

                if logged_in:
                    self.log("✅ 登录流程完成，浏览器即将关闭。")
                    self.update_status(f"已登录 {browser}，可以开始搜索")
                    self.root.after(0, lambda: self.btn_5.config(state="normal"))
                    self.root.after(0, lambda: self.btn_10.config(state="normal"))
                    self.root.after(0, lambda: self.btn_20.config(state="normal"))
                    self.root.after(0, lambda: self.btn_custom.config(state="normal"))
                    self.root.after(0, lambda: self.btn_dailyset.config(state="normal"))
                    if driver:
                        driver.quit()
                        driver = None
                        self.log("✅ 浏览器已关闭。")
                else:
                    self.log("❌ 登录未成功，请重试")
                    self.update_status("登录失败")
            except Exception as e:
                self.log(f"❌ 登录出错: {e}")
                self.update_status("登录失败")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                self.root.after(0, lambda: self.btn_login.config(state="normal"))

        threading.Thread(target=login_work, daemon=True).start()

    def start_search(self, count):
        if not self.available_browsers:
            messagebox.showerror("错误", "没有可用的浏览器驱动！")
            return

        browser = self.browser_var.get()
        if not browser:
            messagebox.showerror("错误", "请先选择浏览器！")
            return

        if browser == "edge" and not os.path.exists(EDGE_DRIVER_PATH):
            messagebox.showerror("错误", "Edge 驱动文件缺失")
            return
        if browser == "chrome" and not os.path.exists(CHROME_DRIVER_PATH):
            messagebox.showerror("错误", "Chrome 驱动文件缺失")
            return

        if not os.path.exists(DICT_PATH):
            messagebox.showerror("错误", "找不到 dictionary.txt")
            return
        words = pick_words(count)
        if not words:
            messagebox.showerror("错误", "dictionary.txt 为空或未找到")
            return

        user_dir = USER_DATA_DIR_EDGE if browser == "edge" else USER_DATA_DIR_CHROME
        if not os.path.exists(user_dir) or not os.listdir(user_dir):
            messagebox.showinfo("提示", f"当前 {browser} 未登录，请先点击“登录账号”完成登录！")
            return

        self.btn_login.config(state="disabled")
        self.btn_5.config(state="disabled")
        self.btn_10.config(state="disabled")
        self.btn_20.config(state="disabled")
        self.btn_custom.config(state="disabled")
        self.btn_dailyset.config(state="disabled")
        self.update_status(f"正在执行 {count} 次搜索（{browser}，逐字输入）...")
        self.log(f"🚀 开始执行 {count} 次搜索，逐字输入（0.5秒/字符），提交后等待5秒。")

        def search_work():
            driver = None
            try:
                driver = init_driver(browser, headless=False, use_mobile_ua=False)
                driver.get("https://cn.bing.com/")
                wait = WebDriverWait(driver, 10)
                search_box = wait.until(EC.presence_of_element_located((By.ID, "sb_form_q")))

                for idx, word in enumerate(words, 1):
                    self.root.after(0, lambda w=word, i=idx, c=count: self.log(f"🔍 ({i}/{c}) 输入: {w}"))
                    self.root.after(0, lambda w=word: self.update_status(f"正在输入：{word}"))

                    search_box.clear()
                    type_with_delay(search_box, word, delay=0.5)
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(5)

                    search_box = wait.until(EC.presence_of_element_located((By.ID, "sb_form_q")))
                    search_box.send_keys(Keys.CONTROL, 'a')
                    search_box.send_keys(Keys.DELETE)
                    time.sleep(0.5)

                self.root.after(0, lambda: self.log("✅ 全部搜索任务执行完毕！"))
                self.root.after(0, lambda: self.update_status("搜索完成"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"已成功完成 {count} 次搜索！"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"❌ 搜索出错: {e}"))
                self.root.after(0, lambda: self.update_status("搜索异常"))
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                self.root.after(0, lambda: self.btn_login.config(state="normal"))
                self.root.after(0, lambda: self.btn_5.config(state="normal"))
                self.root.after(0, lambda: self.btn_10.config(state="normal"))
                self.root.after(0, lambda: self.btn_20.config(state="normal"))
                self.root.after(0, lambda: self.btn_custom.config(state="normal"))
                self.root.after(0, lambda: self.btn_dailyset.config(state="normal"))
                self.root.after(0, lambda: self.update_status("就绪"))

        threading.Thread(target=search_work, daemon=True).start()

    # ---------- 每日打卡 ----------
    def start_daily_set(self):
        """打开 Rewards 页面，点击'每日连续打卡活动'主卡片展开，点击后三个子任务"""
        if not self.available_browsers:
            messagebox.showerror("错误", "没有可用的浏览器驱动！")
            return

        browser = self.browser_var.get()
        if not browser:
            messagebox.showerror("错误", "请先选择浏览器！")
            return

        if browser == "edge" and not os.path.exists(EDGE_DRIVER_PATH):
            messagebox.showerror("错误", "Edge 驱动文件缺失")
            return
        if browser == "chrome" and not os.path.exists(CHROME_DRIVER_PATH):
            messagebox.showerror("错误", "Chrome 驱动文件缺失")
            return

        user_dir = USER_DATA_DIR_EDGE if browser == "edge" else USER_DATA_DIR_CHROME
        if not os.path.exists(user_dir) or not os.listdir(user_dir):
            messagebox.showinfo("提示", f"当前 {browser} 未登录，请先点击“登录账号”完成登录！")
            return

        self.btn_login.config(state="disabled")
        self.btn_5.config(state="disabled")
        self.btn_10.config(state="disabled")
        self.btn_20.config(state="disabled")
        self.btn_custom.config(state="disabled")
        self.btn_dailyset.config(state="disabled")

        self.update_status("正在打开 Rewards 页面，准备完成每日打卡任务...")
        self.log("📋 开始执行每日打卡任务...")

        def daily_set_work():
            driver = None
            try:
                driver = init_driver(browser, headless=False, use_mobile_ua=False,
                                     page_load_strategy='none')
                driver.get("https://rewards.bing.com/earn")
                time.sleep(5)
                self.root.after(0, lambda: self.log("✅ Rewards 页面已加载"))

                # ===== 步骤1：找到"每日连续打卡活动"主卡片 =====
                self.root.after(0, lambda: self.log("🔍 正在查找'每日连续打卡活动'主卡片..."))

                main_card = None
                for _ in range(15):
                    try:
                        main_card = driver.find_element(
                            By.XPATH,
                            "//button[.//p[contains(normalize-space(), '每日连续打卡活动')]]"
                        )
                        if main_card:
                            break
                    except:
                        pass
                    time.sleep(1)

                if not main_card:
                    self.root.after(0, lambda: self.log("❌ 未找到'每日连续打卡活动'主卡片"))
                    self.root.after(0, lambda: self.update_status("未找到主卡片"))
                    return

                self.root.after(0, lambda: self.log("✅ 已找到'每日连续打卡活动'主卡片"))

                def collect_visible_link_hrefs():
                    hrefs = set()
                    try:
                        links = driver.find_elements(By.XPATH, "//a[@href]")
                        for a in links:
                            try:
                                if a.is_displayed():
                                    h = a.get_attribute("href") or ""
                                    if h.startswith("http"):
                                        hrefs.add(h)
                            except:
                                pass
                    except:
                        pass
                    return hrefs

                # ===== 步骤2：确保主卡片处于折叠状态，记录点击前链接 =====
                try:
                    expanded = main_card.get_attribute("aria-expanded")
                except:
                    expanded = "false"

                if expanded == "true":
                    self.root.after(0, lambda: self.log("ℹ️ 主卡片已展开，先折叠以便对比新链接"))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", main_card)
                    try:
                        main_card.click()
                    except:
                        driver.execute_script("arguments[0].click();", main_card)
                    time.sleep(1)

                before_hrefs = collect_visible_link_hrefs()
                self.root.after(0, lambda n=len(before_hrefs):
                    self.log(f"ℹ️ 点击前页面可见链接数: {n}"))

                # ===== 步骤3：点击主卡片展开，等待1秒 =====
                self.root.after(0, lambda: self.log("🖱️ 正在点击主卡片展开任务列表..."))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", main_card)
                try:
                    main_card.click()
                except:
                    driver.execute_script("arguments[0].click();", main_card)

                time.sleep(1)

                # ===== 步骤4：找出点击后新增的链接 =====
                self.root.after(0, lambda: self.log("🔍 正在查找展开后新增的子任务链接..."))

                after_hrefs = collect_visible_link_hrefs()
                new_hrefs = after_hrefs - before_hrefs
                self.root.after(0, lambda n=len(new_hrefs):
                    self.log(f"ℹ️ 检测到 {n} 个新出现的链接"))

                # 优先：从 aria-controls 子面板取
                panel_hrefs = []
                try:
                    panel_id = main_card.get_attribute("aria-controls")
                except:
                    panel_id = None

                if panel_id:
                    try:
                        panel = driver.find_element(By.ID, panel_id)
                        raw = panel.find_elements(By.XPATH, ".//a[@href]")
                        for l in raw:
                            try:
                                if not l.is_displayed():
                                    continue
                                h = l.get_attribute("href") or ""
                                if h and h not in panel_hrefs:
                                    panel_hrefs.append(h)
                            except:
                                continue
                        if panel_hrefs:
                            self.root.after(0, lambda n=len(panel_hrefs):
                                self.log(f"✅ 通过 aria-controls 子面板找到 {n} 个链接"))
                    except:
                        pass

                # 组装最终 href 列表：优先用新出现的链接（按页面顺序）
                task_hrefs = []
                if new_hrefs:
                    try:
                        all_links = driver.find_elements(By.XPATH, "//a[@href]")
                    except:
                        all_links = []
                    for a in all_links:
                        try:
                            if not a.is_displayed():
                                continue
                            h = a.get_attribute("href") or ""
                            if h in new_hrefs and h not in task_hrefs:
                                task_hrefs.append(h)
                        except:
                            continue

                if not task_hrefs and panel_hrefs:
                    task_hrefs = panel_hrefs

                # ===== 关键：若超过3个，跳过第一个，保留后面三个 =====
                if len(task_hrefs) > 3:
                    skipped = task_hrefs[0]
                    task_hrefs = task_hrefs[1:4]
                    self.root.after(0, lambda s=skipped: self.log(
                        f"ℹ️ 检测到 {len(task_hrefs) + 1} 个链接，跳过第一个: {s[:80]}..."))
                else:
                    task_hrefs = task_hrefs[:3]

                if not task_hrefs:
                    self.root.after(0, lambda: self.log("❌ 未找到每日打卡子任务链接"))
                    self.root.after(0, lambda: self.update_status("未找到打卡任务"))
                    return

                total = len(task_hrefs)
                self.root.after(0, lambda n=total: self.log(
                    f"📋 共找到 {n} 个每日打卡子任务，开始依次点击"))

                # ===== 步骤5：依次点击每个子任务（不重新加载页面）=====
                for idx, href in enumerate(task_hrefs, 1):
                    self.root.after(0, lambda i=idx, n=total, h=href:
                        self.log(f"🖱️ ({i}/{n}) 点击 href: {h[:80]}..."))
                    self.root.after(0, lambda i=idx, n=total:
                        self.update_status(f"正在点击 {i}/{n}..."))

                    try:
                        clicked = driver.execute_script("""
                            var target = arguments[0];
                            var links = document.querySelectorAll('a[href]');
                            for (var i = 0; i < links.length; i++) {
                                if (links[i].href === target) {
                                    links[i].scrollIntoView({block: 'center'});
                                    links[i].click();
                                    return true;
                                }
                            }
                            return false;
                        """, href)
                    except Exception as e:
                        self.root.after(0, lambda e=e, i=idx:
                            self.log(f"  ⚠️ 任务{i} 点击异常: {e}"))
                        clicked = False

                    if clicked:
                        self.root.after(0, lambda i=idx: self.log(f"  ✅ 已点击任务 {i}"))
                    else:
                        self.root.after(0, lambda i=idx:
                            self.log(f"  ⚠️ 任务{i} 未找到对应元素，跳过"))

                    time.sleep(1)

                self.root.after(0, lambda: self.log("✅ 每日打卡任务执行完毕！"))
                self.root.after(0, lambda: self.update_status("每日打卡完成"))
                self.root.after(0, lambda: messagebox.showinfo("完成", "每日打卡任务已全部执行！"))

            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"❌ 每日打卡出错: {e}"))
                self.root.after(0, lambda: self.update_status("每日打卡异常"))
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                self.root.after(0, lambda: self.btn_login.config(state="normal"))
                self.root.after(0, lambda: self.btn_5.config(state="normal"))
                self.root.after(0, lambda: self.btn_10.config(state="normal"))
                self.root.after(0, lambda: self.btn_20.config(state="normal"))
                self.root.after(0, lambda: self.btn_custom.config(state="normal"))
                self.root.after(0, lambda: self.btn_dailyset.config(state="normal"))
                self.root.after(0, lambda: self.update_status("就绪"))

        threading.Thread(target=daily_set_work, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
