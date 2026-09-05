# -*- coding: utf-8 -*-
import os
import random
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk

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


# ========== 驱动初始化 ==========
def init_driver(browser, headless=False, use_mobile_ua=False):
    if browser == "edge":
        options = EdgeOptions()
        options.add_argument(f"--user-data-dir={USER_DATA_DIR_EDGE}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--disable-gpu")
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
        root.title("必应自动刷积分助手v2.0 (支持Edge/Chrome)")
        root.geometry("500x500")   # 宽度增加以适应更多按钮
        root.resizable(False, False)

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

        # 浏览器选择
        tk.Label(top_frame, text="选择浏览器:", font=("微软雅黑", 10)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        if self.available_browsers:
            self.browser_combo = ttk.Combobox(top_frame, textvariable=self.browser_var,
                                              values=self.available_browsers,
                                              state="readonly", width=12)
            self.browser_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        else:
            self.browser_combo = ttk.Combobox(top_frame, textvariable=self.browser_var,
                                              values=[], state="disabled", width=12)
            self.browser_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 按钮区域（第一行：登录 + 5次 + 10次 + 20次）
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

        # 第二行：自定义次数
        custom_frame = tk.Frame(top_frame)
        custom_frame.grid(row=1, column=0, columnspan=3, pady=5)

        tk.Label(custom_frame, text="自定义次数:", font=("微软雅黑", 10)).grid(row=0, column=0, padx=4, pady=4, sticky="e")
        self.custom_entry = tk.Entry(custom_frame, width=10)
        self.custom_entry.grid(row=0, column=1, padx=4, pady=4)
        self.custom_entry.insert(0, "5")

        self.btn_custom = tk.Button(custom_frame, text="▶ 自定义搜索",
                                    command=self.start_custom_search, width=12)
        self.btn_custom.grid(row=0, column=2, padx=4, pady=4)

        # 日志显示
        self.log_area = scrolledtext.ScrolledText(root, height=14, state='disabled', wrap=tk.WORD)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=10)

        # ---------- 初始状态 ----------
        if not self.available_browsers:
            self.btn_login.config(state="disabled")
            self.btn_5.config(state="disabled")
            self.btn_10.config(state="disabled")
            self.btn_20.config(state="disabled")
            self.btn_custom.config(state="disabled")
            self.update_status("驱动缺失，无法使用")
        else:
            self.btn_login.config(state="normal")
            # 搜索按钮初始禁用（需登录）
            self.btn_5.config(state="disabled")
            self.btn_10.config(state="disabled")
            self.btn_20.config(state="disabled")
            self.btn_custom.config(state="disabled")

            browser = self.browser_var.get()
            user_dir = USER_DATA_DIR_EDGE if browser == "edge" else USER_DATA_DIR_CHROME
            if os.path.exists(user_dir) and os.listdir(user_dir):
                self.update_status(f"检测到 {browser} 用户数据，可搜索")
                self.log(f"ℹ️ {browser} 用户数据目录已存在，若已登录可直接搜索")
                self.btn_5.config(state="normal")
                self.btn_10.config(state="normal")
                self.btn_20.config(state="normal")
                self.btn_custom.config(state="normal")
            else:
                self.update_status(f"未登录 {browser}，请点击“登录账号”")
                self.log(f"ℹ️ {browser} 用户数据目录为空，需要登录")

        if not os.path.exists(DICT_PATH):
            self.log("⚠️ 警告：找不到 dictionary.txt，请创建并填入搜索词。")

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

    # ---------- 登录 ----------
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
                    driver.quit()
                self.root.after(0, lambda: self.btn_login.config(state="normal"))

        threading.Thread(target=login_work, daemon=True).start()

    # ---------- 搜索 ----------
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

        # 禁用所有操作按钮
        self.btn_login.config(state="disabled")
        self.btn_5.config(state="disabled")
        self.btn_10.config(state="disabled")
        self.btn_20.config(state="disabled")
        self.btn_custom.config(state="disabled")
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
                self.root.after(0, lambda: self.log(f"❌ 搜索出错: {e}"))
                self.root.after(0, lambda: self.update_status("搜索异常"))
            finally:
                if driver:
                    driver.quit()
                # 恢复所有按钮
                self.root.after(0, lambda: self.btn_login.config(state="normal"))
                self.root.after(0, lambda: self.btn_5.config(state="normal"))
                self.root.after(0, lambda: self.btn_10.config(state="normal"))
                self.root.after(0, lambda: self.btn_20.config(state="normal"))
                self.root.after(0, lambda: self.btn_custom.config(state="normal"))
                self.root.after(0, lambda: self.update_status("就绪"))

        threading.Thread(target=search_work, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
