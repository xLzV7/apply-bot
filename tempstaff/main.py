import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# --- 1. ブラウザ・環境設定 ---
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--window-size=1920,1080')

MY_ID = os.environ.get('TEMPSTAFF_ID')
PASSWORD = os.environ.get('TEMPSTAFF_PASS')

if not MY_ID or not PASSWORD:
    raise ValueError("Environment variables TEMPSTAFF_ID or TEMPSTAFF_PASS are not set.")

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 15)

TARGET_URL = "https://www.tempstaff.co.jp/stmy/login?FROM_DISP_INFO=001&jcmy=GN01&ua=https%3A%2F%2Fwww.tempstaff.co.jp%2Fjbch%2Ftop"

try:
    # --- 2. ログイン ---
    driver.get(TARGET_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "myId"))).send_keys(MY_ID)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.XPATH, "//span[text()='ログインして仕事を探す']/ancestor::button").click()
    
    # --- 3. 検索条件設定 ---
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "h1_pink")))
    
    # エリア（東京23区）
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.modal_work-location"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-action*='selectChiki']"))).click()
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "custom-select-trigger"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@data-value='23' and text()='関東']"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), '東京都')]"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='splitChiki_13_00001']"))).click()
    
    # 職種（事務）
    wait.until(EC.element_to_be_clickable((By.ID, "addCondition"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-formaction*='selectSyokusyu']"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), '事務')]"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='0201']"))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.add_conditions"))).click()
    
    # 検索実行
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-formaction='/jbch/detailSearch']"))).click()

    # 給与順
    wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "custom-select-trigger"))).click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//li[@data-value='002' and text()='給与順']"))).click()
    time.sleep(3)

    # --- 5. エントリー繰り返しループ ---
    main_window = driver.current_window_handle
    processed_count = 0

    while True:
        # 求人カードのリストを取得
        job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_list_box")
        total_in_page = len(job_cards)
        
        if total_in_page == 0:
            break

        for i in range(processed_count, total_in_page):
            # 要素の再取得
            job_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_list_box")
            if i >= len(job_cards): break
            card = job_cards[i]

            try:
                # 1. 「派遣」アイコンのチェック
                is_haken = any(icon.text == "派遣" for icon in card.find_elements(By.CLASS_NAME, "icon_gray"))
                if not is_haken:
                    print(f"案件 {i+1}: 派遣ではないためスキップ")
                    processed_count += 1
                    continue

                # 2. ボタン状態のチェック
                # ボタン要素を取得（エントリー or エントリー一覧）
                btn = card.find_element(By.CSS_SELECTOR, "div.job_list_box_btn_box a")
                btn_text = btn.text.strip()

                if "エントリー一覧" in btn_text:
                    print(f"案件 {i+1}: すでにエントリー済みです")
                    processed_count += 1
                    continue
                
                if "エントリー" not in btn_text:
                    print(f"案件 {i+1}: エントリー不可（{btn_text}）")
                    processed_count += 1
                    continue

                # 3. エントリー実行
                for attempt in range(3):
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", btn)
                    
                    wait.until(lambda d: len(d.window_handles) > 1)
                    driver.switch_to.window(driver.window_handles[-1])
                    
                    if "ただいま混み合っております" in driver.page_source:
                        print(f"案件 {i+1}: 混雑リトライ ({attempt+1})")
                        driver.close()
                        driver.switch_to.window(main_window)
                        time.sleep(3)
                        continue
                    
                    try:
                        short_wait = WebDriverWait(driver, 7)
                        submit_btn = short_wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='エントリーする']/ancestor::button")))
                        driver.execute_script("arguments[0].click();", submit_btn)
                        
                        wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '完了') or contains(text(), '済み')]")))
                        print(f"案件 {i+1}: エントリー完了")
                    except:
                        print(f"案件 {i+1}: スキップ（詳細画面にボタンなし）")
                    
                    break # アテンプト終了

            except Exception as e:
                print(f"案件 {i+1}: 処理エラー {type(e).__name__}")

            # 後処理
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(main_window)
            processed_count += 1

        # --- もっと見る ---
        try:
            read_more = driver.find_element(By.ID, "readMore")
            if read_more.is_displayed():
                driver.execute_script("arguments[0].click();", read_more)
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.job_list_box")) > total_in_page)
            else:
                break
        except:
            break

    print(f"全工程終了。処理件数: {processed_count}")

finally:
    driver.quit()
