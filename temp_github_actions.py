import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# --- 1. GitHub Actions専用ブラウザ設定 ---
chrome_options = Options()
chrome_options.add_argument('--headless')  # 必須
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1920,1080')

# ID/パスワードはGitHub Secretsからのみ取得（ソースには一切残さない）
MY_ID = os.environ.get('TEMPSTAFF_ID')
PASSWORD = os.environ.get('TEMPSTAFF_PASS')

if not MY_ID or not PASSWORD:
    raise ValueError("Environment variables TEMPSTAFF_ID or TEMPSTAFF_PASS are not set.")

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 15)

TARGET_URL = "https://www.tempstaff.co.jp/stmy/login?FROM_DISP_INFO=001&jcmy=GN01&ua=https%3A%2F%2Fwww.tempstaff.co.jp%2Fjbch%2Ftop"

try:
    # --- 2. ログイン処理 ---
    driver.get(TARGET_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "myId"))).send_keys(MY_ID)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//span[text()='ログインして仕事を探す']/ancestor::button").click()
    
    # --- 3. 検索条件の設定（東京・23区・事務・派遣） ---
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "h1_pink")))
    
    # エリア選択
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.modal_work-location"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-action*='selectChiki']"))).click()
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "custom-select-trigger"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@data-value='23' and text()='関東']"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//p[contains(@class, 'acc_title') and contains(text(), '東京都')]"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='splitChiki_13_00001']"))).click()
    
    # 職種選択
    wait.until(EC.element_to_be_clickable((By.ID, "addCondition"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-formaction*='selectSyokusyu']"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//p[contains(@class, 'acc_title') and contains(text(), '事務')]"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='0201']"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.add_conditions"))).click()
    
    # 検索実行
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-formaction='/jbch/detailSearch']"))).click()

    # --- 4. 並べ替え (給与順) ---
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "custom-select-trigger"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@data-value='002' and text()='給与順']"))).click()
    time.sleep(3) # 並べ替え反映待機

    # --- 5. エントリー繰り返しループ ---
    main_window = driver.current_window_handle
    processed_count = 0

    while True:
        entry_buttons = driver.find_elements(By.CSS_SELECTOR, "a.btn_pink01.entry")
        total_count = len(entry_buttons)
        
        if total_count == 0:
            print("表示される案件がありません。")
            break

        for i in range(processed_count, total_count):
            # 再取得（DOM更新対策）
            current_btns = driver.find_elements(By.CSS_SELECTOR, "a.btn_pink01.entry")
            if i >= len(current_btns): break
            
            target_btn = current_btns[i]
            max_retries = 3
            success = False

            for attempt in range(max_retries):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", target_btn)
                    
                    wait.until(lambda d: len(d.window_handles) > 1)
                    new_window = [w for w in driver.window_handles if w != main_window][0]
                    driver.switch_to.window(new_window)
                    
                    # 混雑チェック
                    if "ただいま混み合っております" in driver.page_source:
                        print(f"案件 {i+1}: 混雑エラーリトライ ({attempt+1}/{max_retries})")
                        driver.close()
                        driver.switch_to.window(main_window)
                        time.sleep(3)
                        continue
                    
                    # 個別案件処理
                    try:
                        short_wait = WebDriverWait(driver, 7)
                        submit_xpath = "//span[text()='エントリーする']/ancestor::button"
                        
                        submit_btn = short_wait.until(EC.element_to_be_clickable((By.XPATH, submit_xpath)))
                        driver.execute_script("arguments[0].click();", submit_btn)
                        
                        # 結果確認
                        wait.until(EC.presence_of_element_located((By.XPATH, 
                            "//span[contains(text(), 'エントリーが完了しました') or contains(text(), 'この仕事はエントリー済みです')]")))
                        
                        status = "新規完了" if "完了しました" in driver.page_source else "済み"
                        print(f"案件 {i+1}: {status}")
                        success = True
                    except:
                        print(f"案件 {i+1}: スキップ（エントリーボタン不在/仮登録等）")
                    
                    break # リトライループ脱出

                except Exception as e:
                    print(f"案件 {i+1}: 試行エラー {type(e).__name__}")
                    break

            # タブのクリーンアップ
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(main_window)
            
            processed_count += 1

        # --- もっと見る判定 ---
        try:
            read_more = driver.find_element(By.ID, "readMore")
            if read_more.is_displayed():
                print(f"--- 現在 {total_count} 件。さらに読み込みます ---")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", read_more)
                read_more.click()
                # ボタンが増えるまで待機（動的待機）
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.btn_pink01.entry")) > total_count)
            else:
                break
        except:
            print("これ以上「もっと見る」ボタンはありません。")
            break

    print(f"最終処理件数: {processed_count}")

finally:
    driver.quit()