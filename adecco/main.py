import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ==========================================
# 定数・設定
# ==========================================
LOGIN_URL = "https://www.adeccogroup.jp/login?serviceType=A&startURL=PO_MyTopA"
TARGET_JOB = "オフィスワーク・事務系-経理・財務"
DEFAULT_WAIT_SEC = 20

# 機密情報は必ず環境変数(GitHub Secrets)から取得
USER_ID = os.environ.get("ADECCO_ID")
USER_PASS = os.environ.get("ADECCO_PASS")

if not USER_ID or not USER_PASS:
    print("【致命的エラー】環境変数 'ADECCO_ID' または 'ADECCO_PASS' が設定されていません。")
    print("GitHubの Settings > Secrets and variables > Actions にて設定してください。")
    sys.exit(1)

# ==========================================
# カスタム例外（大域脱出用）
# ==========================================
class LimitReachedException(Exception):
    """1日の応募上限（10件）に達したことを知らせる例外"""
    pass

# ==========================================
# 共通ヘルパー関数
# ==========================================
def js_click(driver, element):
    """JavaScriptを用いて要素を強制クリックする"""
    driver.execute_script("arguments[0].click();", element)

def scroll_to_center(driver, element):
    """要素を画面の中央にスクロールする"""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)

def wait_for_loader(driver, timeout_sec=30):
    """画面上のローダー（くるくる）が消えるまで待機する"""
    try:
        WebDriverWait(driver, timeout_sec).until(
            lambda d: "display: none" in d.find_element(By.ID, "loader-main").get_attribute("style")
        )
    except TimeoutException:
        pass # ローダーがそもそも出なかった場合は無視

def wait_for_enabled_and_click(driver, element_id, timeout_sec=10):
    """ボタンの disabled 属性が消えるのを監視し、活性化した瞬間にクリックする"""
    for i in range(int(timeout_sec * 2)):
        btn = driver.find_element(By.ID, element_id)
        if btn.get_attribute("disabled") is None:
            js_click(driver, btn)
            return
        time.sleep(0.5)
    raise TimeoutException(f"ボタン({element_id})が活性化しませんでした")

# ==========================================
# メイン機能モジュール
# ==========================================
def setup_browser():
    """GitHub Actions用のブラウザセットアップ"""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # 💡 画面サイズをフルHDに広げて、要素が隠れるのを防ぐ
    opts.add_argument("--window-size=1920,1080") 
    
    # Bot検知回避
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(options=opts)
    
    # navigator.webdriver を隠蔽
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def login(driver, wait):
    """ログイン処理"""
    print("--- ログイン開始 ---")
    driver.get(LOGIN_URL)
    wait.until(EC.visibility_of_element_located((By.XPATH, "//h1[contains(@class,'login-title') and contains(text(), 'MyPage ログイン')]")))

    # ID入力
    login_id_input = wait.until(EC.element_to_be_clickable((By.ID, "login-id")))
    login_id_input.clear()
    login_id_input.send_keys(USER_ID)

    # パスワード入力とフォーカス外し（Vue/React等のイベント発火用）
    password_input = wait.until(EC.element_to_be_clickable((By.ID, "login-password")))
    password_input.clear()
    password_input.send_keys(USER_PASS)
    password_input.send_keys(Keys.ENTER)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", password_input)
    driver.execute_script("arguments[0].dispatchEvent(new Event('blur'));", password_input)

    # ログイン実行
    login_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.callLogin")))
    js_click(driver, login_btn)
    print("OK: ログイン完了")

def set_search_conditions(driver, wait):
    """検索条件の設定（勤務地、職種、雇用形態）"""
    print("--- 検索条件の設定 ---")
    
    # 求人検索画面へ遷移
    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'PO_JobSearchA') and .//span[text()='希望条件で求人検索']]")))
    js_click(driver, search_btn)

    # 1. 勤務地選択（東京23区）
    wait.until(EC.element_to_be_clickable((By.ID, "selWorkLocationId"))).click()
    cb_23 = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@value='東京都_23区']")))
    scroll_to_center(driver, cb_23)
    if not cb_23.is_selected():
        js_click(driver, cb_23)
    wait_for_enabled_and_click(driver, "workloc_add_other_conditions")
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))

    # 2. 職種選択（経理・財務）
    try:
        job_entry = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "selJobCategoryId")))
        js_click(driver, job_entry)
        
        cb_job = wait.until(EC.presence_of_element_located((By.XPATH, f"//input[@value='{TARGET_JOB}']")))
        scroll_to_center(driver, cb_job)
        if not cb_job.is_selected():
            js_click(driver, cb_job)
            
        wait_for_enabled_and_click(driver, "jc_add_other_conditions")
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))
    except TimeoutException:
        print("職種選択ステップをスキップしました（表示されず）")

    # 3. 雇用形態選択（派遣）
    try:
        employment_entry = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "selEmploymentTypeId")))
        js_click(driver, employment_entry)
        
        cb_haken = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='employmentType' and @value='1']")))
        scroll_to_center(driver, cb_haken)
        if not cb_haken.is_selected():
            js_click(driver, cb_haken)
    except TimeoutException:
        pass

    # 4. 検索実行
    wait_for_enabled_and_click(driver, "et_search_btn")
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))
    print("OK: 検索実行完了")

def sort_by_hourly_wage(driver, wait):
    """検索結果を時給順に並べ替え"""
    wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), '派遣求人')]")))
    sort_radio = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='sort-type' and @value='2']")))
    js_click(driver, sort_radio)
    print("OK: 「時給順」にソートしました")

def process_single_job(driver, wait, job_btn, job_index, main_window):
    """1件の求人へ応募処理を行う。上限到達時は LimitReachedException を投げる"""
    scroll_to_center(driver, job_btn)
    js_click(driver, job_btn)
    
    try:
        # 新規タブへ移動
        wait.until(lambda d: len(d.window_handles) > 1)
        new_window = [h for h in driver.window_handles if h != main_window][0]
        driver.switch_to.window(new_window)

        # 応募ボタンの状態確認
        final_btn = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "apply-jobs")))
        is_disabled = final_btn.get_attribute("disabled") is not None
        is_not_active = "not-active" in (final_btn.get_attribute("class") or "")

        if is_disabled or is_not_active:
            print(f"案件 {job_index:03d}: 応募済みのためスキップ")
            return

        # 応募実行
        js_click(driver, final_btn)
        print(f"案件 {job_index:03d}: 応募実行（通信中...）")

        # 通信完了を待機
        time.sleep(0.5)
        wait_for_loader(driver)

        # 1日の上限エラー（10件）検知
        error_xpath = "//div[contains(@class, '_error')]//p[contains(text(), '1日に10件まで')]"
        if driver.find_elements(By.XPATH, error_xpath):
            raise LimitReachedException("本日の応募上限（10件）に達しました。")

        # 完了メッセージ待機
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'お仕事応募が完了しました')]"))
        )
        print(f"案件 {job_index:03d}: ✨ 応募完了！")

    except LimitReachedException:
        raise # 呼び出し元の auto_entry_loop に例外をそのまま渡して全体を終了させる
    except Exception as e:
        print(f"案件 {job_index:03d}: エラー発生によりスキップ ({type(e).__name__})")
    finally:
        # 例外時も必ず元のタブに戻る安全設計
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(main_window)
            time.sleep(1.5)

def auto_entry_loop(driver, wait):
    """検索結果ページを巡回し、自動応募を行うループ"""
    print("--- 自動応募処理開始 ---")
    main_window = driver.current_window_handle

    while True:
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]")))
        job_btns = driver.find_elements(By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]")
        total_in_page = len(job_btns)
        print(f"\n--- 現在のページ: {total_in_page} 件の求人を処理します ---")

        for i in range(total_in_page):
            # 要素の再取得（StaleElementReferenceException対策）
            btns = driver.find_elements(By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]")
            if i >= len(btns):
                break
            
            target_btn = btns[i]
            job_index = i + 1
            
            # 1件処理を実行（上限到達時はここで例外が投げられ、ループを抜ける）
            process_single_job(driver, wait, target_btn, job_index, main_window)

        print("--- ページ内の全件処理が完了しました ---")

        # 次のページへ遷移
        try:
            next_btn_xpath = "//a[contains(@class, '_next') and .//span[text()='次へ']]"
            next_btn = driver.find_element(By.XPATH, next_btn_xpath)
            
            if next_btn.is_displayed():
                js_click(driver, next_btn)
                print(">>> 次のページへ移動します")
                wait_for_loader(driver)
                time.sleep(2)
            else:
                print("次のページはありません（ボタン非表示）。全処理を終了します。")
                break
        except NoSuchElementException:
            print("「次へ」ボタンが存在しません。全処理を終了します。")
            break

# ==========================================
# 実行エントリーポイント
# ==========================================
def main():
    print("ブラウザを起動しています...")
    driver = setup_browser()
    wait = WebDriverWait(driver, DEFAULT_WAIT_SEC)
    
    try:
        login(driver, wait)
        time.sleep(3)  # 💡 ログイン後の画面遷移が完了するまで少し待機させる
        set_search_conditions(driver, wait)
        sort_by_hourly_wage(driver, wait)
        auto_entry_loop(driver, wait)
        
    except LimitReachedException as e:
        print(f"\n✅ プロセス完了: {e}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 予期せぬエラーが発生しました: {e}")
        # 💡 ここからデバッグ用の機能を追加
        try:
            driver.save_screenshot("error_screenshot.png")
            with open("error_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("📸 エラー時のスクリーンショットとHTMLを保存しました。Artifactsから確認してください。")
        except Exception as save_err:
            print(f"スクリーンショット保存中にエラー: {save_err}")
        # 💡 ここまで
        sys.exit(1)
    finally:
        driver.quit()
        print("ブラウザを終了しました。")

if __name__ == "__main__":
    main()
