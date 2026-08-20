# -*- coding: utf-8 -*-
import os
import random
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========== 全局配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRIVER_PATH = os.path.join(BASE_DIR, "msedgedriver.exe")
USER_DATA_DIR = os.path.join(BASE_DIR, "user_data")
DICT_PATH = os.path.join(BASE_DIR, "dictionary.txt")
os.makedirs(USER_DATA_DIR, exist_ok=True)

# ========== 驱动初始化 ==========
def init_driver(headless=False, use_mobile_ua=False):
    options = Options()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
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
    service = Service(DRIVER_PATH)
    return webdriver.Edge(service=service, options=options)

# ========== 读取词典 ==========
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

# ========== 辅助：逐字输入 ==========
def type_with_delay(element, text, delay=0.5):
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)

# ========== APP 主界面 ==========
class App:
    def __init__(self, root):
        self.root = root
        root.title("必应自动刷积分助手v2.0")
        root.geometry("440x450")
        root.resizable(False, False)

        self.status_var = tk.StringVar()
        tk.Label(root, textvariable=self.status_var, fg="blue", relief="sunken",
                 anchor="w", padx=5).pack(fill="x", padx=10, pady=5)

        # 按钮区域
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        # 第1行：固定按钮
        self.btn_login = tk.Button(btn_frame, text="🔑 1. 登录账号", command=self.login_task,
                                   width=14, bg="#FFD700")
        self.btn_login.grid(row=0, column=0, padx=4, pady=4)

        self.btn_20 = tk.Button(btn_frame, text="▶ 20次",
                                command=lambda: self.start_search(20), width=8)
        self.btn_20.grid(row=0, column=1, padx=4, pady=4)

        self.btn_30 = tk.Button(btn_frame, text="▶ 30次",
                                command=lambda: self.start_search(30), width=8)
        self.btn_30.grid(row=0, column=2, padx=4, pady=4)

        # 第2行：自定义次数
        tk.Label(btn_frame, text="自定义次数:", font=("微软雅黑", 10)).grid(row=1, column=0, padx=4, pady=4, sticky="e")
        self.custom_entry = tk.Entry(btn_frame, width=10)
        self.custom_entry.grid(row=1, column=1, padx=4, pady=4)
        self.custom_entry.insert(0, "5")

        self.btn_custom = tk.Button(btn_frame, text="▶ 自定义搜索",
                                    command=self.start_custom_search, width=12)
        self.btn_custom.grid(row=1, column=2, padx=4, pady=4)

        # 日志显示框
        self.log_area = scrolledtext.ScrolledText(root, height=14, state='disabled', wrap=tk.WORD)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=10)

        # ---------- 文件检查 ----------
        if not os.path.exists(DRIVER_PATH):
            self.log("❌ 错误：找不到 msedgedriver.exe，请放在程序同目录下！")
        if not os.path.exists(DICT_PATH):
            self.log("⚠️ 警告：找不到 dictionary.txt，请创建并填入搜索词。")

        # ---------- ★ 启动时检测 user_data 目录 ----------
        if os.path.exists(USER_DATA_DIR) and os.listdir(USER_DATA_DIR):
            self.btn_20.config(state="normal")
            self.btn_30.config(state="normal")
            self.btn_custom.config(state="normal")
            self.update_status("检测到用户数据目录，默认已经登录。如果打开浏览器后没有账号信息请重新登录。")
            self.log("ℹ️ 检测到用户数据目录，默认已经登录。如果打开浏览器后没有账号信息请重新登录。")
        else:
            self.btn_20.config(state="disabled")
            self.btn_30.config(state="disabled")
            self.btn_custom.config(state="disabled")
            self.update_status("未登录，请点击“登录账号”")
            self.log("ℹ️ user_data 目录为空或不存在，需要登录。")

    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self.root.update_idletasks()

    def update_status(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg))

    # ========== 自定义次数校验 ==========
    def start_custom_search(self):
        try:
            count = int(self.custom_entry.get().strip())
            if count <= 0:
                raise ValueError
            self.start_search(count)
        except ValueError:
            messagebox.showerror("错误", "请输入有效的正整数（如 1、10、50）！")

    # ---------- 登录（基于真实Bing页面结构：id_s 和 id_n） ----------
    def login_task(self):
        if not os.path.exists(DRIVER_PATH):
            messagebox.showerror("错误", "找不到 msedgedriver.exe")
            return
        self.btn_login.config(state="disabled")
        self.update_status("正在打开浏览器，请手动登录...")
        self.log("🔑 浏览器已打开，请手动输入账号密码登录。")

        def login_work():
            driver = None
            try:
                driver = init_driver(headless=False, use_mobile_ua=False)
                driver.get("https://cn.bing.com/")
                # 等待身份标识容器加载
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_h")))
                self.log("✅ 页面已加载，开始检测登录状态...")

                # ---------- 辅助检测函数 ----------
                def is_login_button_visible():
                    """返回 True 表示“登录”按钮可见（未登录）"""
                    try:
                        login_span = driver.find_element(By.ID, "id_s")
                        return login_span.is_displayed()
                    except:
                        return False

                def has_username():
                    """返回 True 表示已显示用户名（已登录）"""
                    try:
                        name_span = driver.find_element(By.ID, "id_n")
                        return name_span.text.strip() != ""
                    except:
                        return False

                # ---------- 第一阶段：等待“登录”按钮出现（最多30秒） ----------
                login_appeared = False
                start = time.time()
                while time.time() - start < 30:
                    if is_login_button_visible():
                        login_appeared = True
                        self.log("✅ 检测到“登录”按钮，等待登录完成...")
                        break
                    time.sleep(0.5)

                if not login_appeared:
                    # 如果30秒内没出现“登录”按钮，检查是否已登录（有用户名）
                    if has_username():
                        self.log("✅ 未检测到“登录”按钮，但已有用户名，视为已登录。")
                    else:
                        self.log("⏰ 未检测到“登录”按钮且无用户名，可能页面异常。")
                        answer = messagebox.askyesno("登录确认", "未检测到登录状态。如果您已经登录，请点击“是”；否则点击“否”重新尝试。")
                        if not answer:
                            self.log("❌ 用户取消登录")
                            self.update_status("登录取消")
                            return
                    logged_in = True  # 用户确认或已有用户名
                else:
                    # ---------- 第二阶段：等待“登录”按钮消失（最多5分钟） ----------
                    logged_in = False
                    start_time = time.time()
                    timeout = 300  # 5分钟
                    while time.time() - start_time < timeout:
                        if not is_login_button_visible() and has_username():
                            logged_in = True
                            self.log("✅ “登录”按钮已消失，且检测到用户名，登录成功！")
                            break
                        time.sleep(1)

                    if not logged_in:
                        # 超时后询问用户
                        answer = messagebox.askyesno("登录确认", "登录按钮仍未消失。如果您已经登录，请点击“是”；否则点击“否”重新尝试。")
                        if answer:
                            logged_in = True
                        else:
                            self.log("❌ 用户取消登录")
                            self.update_status("登录取消")
                            return

                # ---------- 处理登录成功 ----------
                if logged_in:
                    self.log("✅ 登录流程完成，浏览器即将关闭。")
                    self.update_status("已登录，可以开始搜索")
                    self.root.after(0, lambda: self.btn_20.config(state="normal"))
                    self.root.after(0, lambda: self.btn_30.config(state="normal"))
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

    # ---------- 搜索（桌面UA，逐字输入） ----------
    def start_search(self, count):
        if not os.path.exists(DICT_PATH):
            messagebox.showerror("错误", "找不到 dictionary.txt")
            return
        words = pick_words(count)
        if not words:
            messagebox.showerror("错误", "dictionary.txt 为空或未找到")
            return
        if not os.listdir(USER_DATA_DIR):
            messagebox.showinfo("提示", "请先点击“登录账号”完成登录！")
            return

        # 禁用所有按钮（防连点）
        self.btn_login.config(state="disabled")
        self.btn_20.config(state="disabled")
        self.btn_30.config(state="disabled")
        self.btn_custom.config(state="disabled")
        self.update_status(f"正在执行 {count} 次搜索（桌面UA，逐字输入）...")
        self.log(f"🚀 开始执行 {count} 次搜索，逐字输入（0.5秒/字符），提交后等待5秒。")

        def search_work():
            driver = None
            try:
                driver = init_driver(headless=False, use_mobile_ua=False)
                driver.get("https://cn.bing.com/")
                wait = WebDriverWait(driver, 10)
                search_box = wait.until(EC.presence_of_element_located((By.ID, "sb_form_q")))

                for idx, word in enumerate(words, 1):
                    self.root.after(0, lambda w=word, i=idx, c=count: self.log(f"🔍 ({i}/{c}) 输入: {w}"))
                    self.root.after(0, lambda w=word: self.update_status(f"正在输入：{word}"))

                    # 清空搜索框
                    search_box.clear()
                    # 逐字输入
                    type_with_delay(search_box, word, delay=0.5)
                    # 回车提交
                    search_box.send_keys(Keys.RETURN)
                    # 等待5秒
                    time.sleep(5)

                    # 重新定位搜索框（页面刷新后元素会变）
                    search_box = wait.until(EC.presence_of_element_located((By.ID, "sb_form_q")))
                    # 全选+删除（模拟清空）
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
                self.root.after(0, lambda: self.btn_20.config(state="normal"))
                self.root.after(0, lambda: self.btn_30.config(state="normal"))
                self.root.after(0, lambda: self.btn_custom.config(state="normal"))
                self.root.after(0, lambda: self.update_status("就绪"))

        threading.Thread(target=search_work, daemon=True).start()

# ========== 启动 ==========
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
