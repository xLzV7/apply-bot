import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ==========================================
# 定数・設定
# ==========================================
LOGIN_URL = "https://www.tempstaff.co.jp/stmy/login?FROM_DISP_INFO=001&jcmy=GN01&ua=https%3A%2F%2Fwww.tempstaff.co.jp%2Fjbch%2Ftop"

# 機密情報は環境変数(GitHub Secrets)から取得する
USER_ID = os.environ.get('TEMPSTAFF_ID')
PASSWORD = os.environ.get('TEMPSTAFF_PASS')

if not USER_ID or not PASSWORD:
    print("【致命的エラー】環境変数 'TEMPSTAFF_ID' または 'TEMPSTAFF_PASS' が設定されていません。")
    print("GitHubの Settings > Secrets and variables > Actions にて設定してください。")
    sys.exit(1)

DEFAULT_WAIT_SEC = 20

# ==========================================
# 共通ヘルパー関数
# ==========================================
def wait_and_click(wait, by, selector):
    wait.until(EC.element_to_be_clickable((by, selector))).click()

def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def scroll_to_center(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

# ==========================================
# メイン機能モジュール
# ==========================================
def setup_browser():
    """GitHub Actions (Linux環境) 用のブラウザ設定"""
    options = Options()
    options.add_argument('--headless=new') # 画面なしモード（必須）
    options.add_argument('--no-sandbox') # Linux環境でのエラー回避
    options.add_argument('--disable-dev-shm-usage') # メモリ不足エラー回避
    options.add_argument('--window-size=1920,1080') # 要素が見切れずにクリックできるように大きめに設定
    
    # Bot検知を回避するための標準的なUser-Agent設定
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    return webdriver.Chrome(options=options)

def login(driver, wait):
    print("--- ログイン開始 ---")
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "myId"))).send_keys(USER_ID)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    wait_and_click(wait, By.XPATH, "//span[text()='ログインして仕事を探す']/ancestor::button")

def set_search_conditions(driver, wait):
    print("--- 検索条件の設定 ---")
    # エリア選択
    wait_and_click(wait, By.CSS_SELECTOR, "a.modal_work-location")
    wait_and_click(wait, By.CSS_SELECTOR, "a[data-action*='selectChiki']")
    wait_and_click(wait, By.CLASS_NAME, "custom-select-trigger")
    wait_and_click(wait, By.XPATH, "//li[@data-value='23' and text()='関東']")
    wait_and_click(wait, By.XPATH, "//p[contains(@class, 'acc_title') and contains(text(), '東京都')]")
    wait_and_click(wait, By.CSS_SELECTOR, "label[for='splitChiki_13_00001']")
    wait_and_click(wait, By.ID, "addCondition")
    
    # 職種選択
    wait_and_click(wait, By.CSS_SELECTOR, "a[data-formaction*='selectSyokusyu']")
    wait_and_click(wait, By.XPATH, "//p[contains(@class, 'acc_title') and contains(text(), '事務')]")
    wait_and_click(wait, By.CSS_SELECTOR, "label[for='0201']")
    wait_and_click(wait, By.CSS_SELECTOR, "a.add_conditions")
    
    # 派遣選択
    haken_checkbox = wait.until(EC.presence_of_element_located((By.ID, "employmentTypeList0")))
    if not haken_checkbox.is_selected():
        js_click(driver, haken_checkbox)

def execute_search_and_sort(wait):
    print("--- 検索実行と並べ替え ---")
    wait_and_click(wait, By.CSS_SELECTOR, "a[data-formaction='/jbch/detailSearch']")
    wait_and_click(wait, By.CLASS_NAME, "custom-select-trigger")
    wait_and_click(wait, By.XPATH, "//li[@data-value='002' and text()='給与順']")

def process_single_job(driver, wait, job_element, job_index, main_window):
    scroll_to_center(driver, job_element)

    icons = job_element.find_elements(By.CSS_SELECTOR, "ul.icon_list li")
    is_haken = any("派遣" in icon.text for icon in icons)
    if not is_haken:
        print(f"案件 {job_index:03d}: 派遣ではないためスキップ")
        return

    entry_btns = job_element.find_elements(By.CSS_SELECTOR, "a.btn_pink01.entry")
    if not entry_btns:
        print(f"案件 {job_index:03d}: エントリー済みのためスキップ")
        return

    try:
        js_click(driver, entry_btns[0])
        wait.until(lambda d: len(d.window_handles) > 1)
        driver.switch_to.window(driver.window_handles[-1])
        
        if "www.tempstaff.co.jp" not in driver.current_url:
            print(f"案件 {job_index:03d}: 外部サイトのため即閉じ")
            return

        if "ただいま混み合っております" in driver.page_source:
            print(f"案件 {job_index:03d}: サイト混雑エラー")
            return

        try:
            submit_btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='エントリーする']/ancestor::button"))
            )
            js_click(driver, submit_btn)
            
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '完了') or contains(text(), '済み')]"))
            )
            print(f"案件 {job_index:03d}: ✨ エントリー成功")
        except Exception:
            print(f"案件 {job_index:03d}: 確定ボタン不在（詳細画面など）")

    except Exception as e:
        print(f"案件 {job_index:03d}: エラー発生 ({type(e).__name__})")
        
    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(main_window)

def auto_entry_loop(driver, wait):
    print("--- 自動エントリー処理開始 ---")
    main_window = driver.current_window_handle
    processed_count = 0

    while True:
        job_elements = driver.find_elements(By.CSS_SELECTOR, "li.jobInfo")
        total_jobs = len(job_elements)
        print(f"--- 走査中: 合計 {total_jobs} 件の求人を確認 (処理済: {processed_count} 件) ---")

        if processed_count < total_jobs:
            for i in range(processed_count, total_jobs):
                current_jobs = driver.find_elements(By.CSS_SELECTOR, "li.jobInfo")
                if i >= len(current_jobs):
                    break
                
                target_job = current_jobs[i]
                job_index = i + 1

                processed_count = job_index
                process_single_job(driver, wait, target_job, job_index, main_window)

            continue

        try:
            read_more_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "readMore"))
            )
            
            if read_more_btn.is_displayed():
                print(f"「もっと見る」をクリック（現在 {total_jobs} 件）")
                scroll_to_center(driver, read_more_btn)
                js_click(driver, read_more_btn)
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "li.jobInfo")) > total_jobs)
            else:
                print("「もっと見る」ボタンが非表示です。すべての案件を処理しました。")
                break
        except Exception:
            print("追加の案件はありません。処理を終了します。")
            break

    print(f"--- 全工程終了。最終処理件数: {processed_count} 件 ---")

# ==========================================
# 実行エントリーポイント
# ==========================================
def main():
    print("ブラウザを起動しています...")
    driver = setup_browser()
    wait = WebDriverWait(driver, DEFAULT_WAIT_SEC)
    
    try:
        login(driver, wait)
        set_search_conditions(driver, wait)
        execute_search_and_sort(wait)
        auto_entry_loop(driver, wait)
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        sys.exit(1) # GitHub ActionsのステータスをFailにするため
    finally:
        driver.quit() # メモリリーク防止のため確実にブラウザを閉じる
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
