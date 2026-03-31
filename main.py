import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- 設定（GitHub Secrets等を使う場合は os.environ.get を使用） ---
LOGIN_URL = "https://www.adeccogroup.jp/login?serviceType=A&startURL=PO_MyTopA"
USER_ID = os.environ.get("ADEKO_ID")
USER_PASS = os.environ.get("ADEKO_PASS")

# --- ブラウザ設定 ---
opts = Options()

# クラウド実行（画面なし）に対応するための必須設定
opts.add_argument("--headless")              # ヘッドレスモード（必須）
opts.add_argument("--no-sandbox")            # 権限エラー防止（必須）
opts.add_argument("--disable-dev-shm-usage") # メモリ不足防止（必須）

# 検知回避と安定化の設定
opts.add_argument("--window-size=1400,900")
opts.add_argument("--disable-blink-features=AutomationControlled")
opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
opts.add_experimental_option("excludeSwitches", ["enable-automation"])
opts.add_experimental_option("useAutomationExtension", False)

# 自動で最適なドライバをインストールして起動
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

# navigator.webdriver を隠して自動操作判定を回避
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

wait = WebDriverWait(driver, 20)

try:
    # ページアクセス
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 30)

    # 1. 「MyPage ログイン」の見出しが表示されるのを待機
    wait.until(EC.visibility_of_element_located((By.XPATH, "//h1[contains(@class,'login-title') and contains(text(), 'MyPage ログイン')]")))
    print("OK: ログイン画面表示")

    # 2. IDの入力 (id="login-id")
    login_id_input = wait.until(EC.element_to_be_clickable((By.ID, "login-id")))
    login_id_input.clear()
    login_id_input.send_keys(USER_ID)
    print(f"OK: ID入力完了")

# 3. パスワードの入力
    password_input = wait.until(EC.element_to_be_clickable((By.ID, "login-password")))
    password_input.clear()
    password_input.send_keys(USER_PASS)

    from selenium.webdriver.common.keys import Keys
    password_input.send_keys(Keys.ENTER)
    
    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", password_input)
    driver.execute_script("arguments[0].dispatchEvent(new Event('blur'));", password_input)
    
    print("OK: パスワード入力 & フォーカス外しの強制実行")

    # 4. ログインボタンのクリック
    login_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.callLogin")))
    driver.execute_script("arguments[0].click();", login_button)
    
    print("OK: ログインボタンを（JSで）強制クリックしました")
    
    # JavaScriptの実行が絡むボタンのため、通常のclickで反応しない場合はexecute_scriptを使用
    try:
        login_button.click()
    except:
        driver.execute_script("arguments[0].click();", login_button)
    
    print("OK: ログインボタンをクリックしました")

    # 「希望条件で求人検索」ボタンが表示されるまで待機してクリック
    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'PO_JobSearchA') and .//span[text()='希望条件で求人検索']]")))
    
    # 通常のクリックが効かない場合に備え、JSで実行
    driver.execute_script("arguments[0].click();", search_btn)
    print("OK: 希望条件で求人検索をクリック")

# 1. 勤務地選択
    area_btn = wait.until(EC.element_to_be_clickable((By.ID, "selWorkLocationId")))
    area_btn.click()

    # 2. 東京23区チェック（スクロールとチェックをJSで完結）
    cb_23 = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@value='東京都_23区']")))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb_23)
    if not cb_23.is_selected():
        driver.execute_script("arguments[0].click();", cb_23)

# 3. 勤務地確定（グレーアウト解除をループで監視してクリック）
    print("待機中: ボタンのグレーアウト解除を監視します...")
    
    # 最大20回（10秒間）ループして、disabled属性が消えるのを待つ
    for i in range(20):
        add_btn = driver.find_element(By.ID, "workloc_add_other_conditions")
        # get_attribute('disabled') が None なら「押せる状態」
        if add_btn.get_attribute("disabled") is None:
            # 活性化した瞬間にJSでクリックを実行
            driver.execute_script("arguments[0].click();", add_btn)
            print(f"OK: グレーアウト解除を確認（{i*0.5}秒後にクリック成功）")
            break
        time.sleep(0.5)
    else:
        # ループを抜けても押せなかった場合のエラー処理
        print("エラー: ボタンが活性化しませんでした")
        raise TimeoutException("Button did not become enabled")

    # モーダルが消えるのを待つ
    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))

    # 4. 職種選択（表示された場合のみ実行）
    try:
        # 変数が定義されていないエラーを防ぐため、ここで再定義するか直接指定します
        TARGET_JOB = "オフィスワーク・事務系-経理・財務"
        
        job_entry = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "selJobCategoryId")))
        driver.execute_script("arguments[0].click();", job_entry)
        print("OK: 職種選択ダイアログを表示")

        # 職種チェック（経理・財務）
        # 変数エラーを避けるため TARGET_JOB を使用
        cb_job = wait.until(EC.presence_of_element_located((By.XPATH, f"//input[@value='{TARGET_JOB}']")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb_job)
        
        if not cb_job.is_selected():
            driver.execute_script("arguments[0].click();", cb_job)
            print(f"OK: {TARGET_JOB} にチェック")

        # 5. 職種確定（勤務地と同じ「グレーアウト監視ループ」を適用）
        print("待機中: 職種確定ボタンのグレーアウト解除を監視します...")
        for i in range(20):
            jc_add = driver.find_element(By.ID, "jc_add_other_conditions")
            if jc_add.get_attribute("disabled") is None:
                driver.execute_script("arguments[0].click();", jc_add)
                print(f"OK: 職種確定ボタンをクリック成功（{i*0.5}秒待機）")
                break
            time.sleep(0.5)
        else:
            raise TimeoutException("職種確定ボタンが活性化しませんでした")

        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))
        print("--- すべての条件指定が完了しました ---")

    except TimeoutException:
        print("skip: 職種選択ステップでタイムアウトしました")

    # 6. 雇用形態選択（表示された場合のみ実行）
    try:
        # 「雇用形態を選ぶ」ボタンが表示されるまで待機
        employment_entry = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "selEmploymentTypeId"))
        )
        driver.execute_script("arguments[0].click();", employment_entry)
        print("OK: 雇用形態選択ダイアログを表示")

        # 「派遣」のチェックボックス（value="1"）を特定してチェック
        # label内のinputを直接狙います
        cb_haken = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@name='employmentType' and @value='1']")
        ))
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb_haken)
        if not cb_haken.is_selected():
            driver.execute_script("arguments[0].click();", cb_haken)
            print("OK: 「派遣」にチェック")

# 7. 検索実行（「この条件で検索」ボタンのグレーアウト解除を監視）
        print("待機中: 検索ボタン（ヒット件数確定）を監視します...")
        
        # 最大20回（10秒間）ループして、disabled属性が消えるのを待つ
        for i in range(20):
            # 検索ボタン（id="et_search_btn"）を取得
            search_exec_btn = driver.find_element(By.ID, "et_search_btn")
            
            # disabled属性が消えた ＝ 件数計算が終わり、押せる状態
            if search_exec_btn.get_attribute("disabled") is None:
                # 活性化した瞬間にJSでクリックを実行
                driver.execute_script("arguments[0].click();", search_exec_btn)
                print(f"OK: 検索実行ボタンをクリック成功（{i*0.5}秒待機）")
                break
            time.sleep(0.5)
        else:
            raise TimeoutException("検索実行ボタンが活性化しませんでした（件数取得タイムアウト）")

        # 検索結果ページへの遷移を待機（必要に応じて）
        print("OK: 検索結果ページへ遷移中...")
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "modal-backdrop")))

    except TimeoutException as e:
        print(f"エラーまたはスキップ: {e}")

    # 8. 検索結果ページの表示を確認
    wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), '派遣求人')]")))
    print("OK: 検索結果ページ表示")

    # 9. 「時給順」ラジオボタン（value="2"）をクリック
    sort_radio = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='sort-type' and @value='2']")))
    driver.execute_script("arguments[0].click();", sort_radio)
    print("OK: 「時給順」を選択")

    # 無限ループ（次のページがなくなるまで）
    while True:
        # ページ内の「応募する」ボタンの「数」をまず把握する
        wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]")))
        total_in_page = len(driver.find_elements(By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]"))
        print(f"このページに {total_in_page} 件の求人があります。順次処理します。")

        main_window = driver.current_window_handle

        # インデックス（番手）を使って1件ずつ処理
        for i in range(total_in_page):
            try:
                # 重要：1件終わるたびにボタン一覧を再取得（Staleエラー防止）
                btns = driver.find_elements(By.XPATH, "//a[contains(@class, 'mod-button-01') and .//span[text()='応募する']]")
                if i >= len(btns): break # 万が一ボタンが減っていたら終了
                
                target_btn = btns[i]
                print(f"--- {i+1}件目の処理開始 ---")
                
                # スクロールとクリック
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_btn)
                driver.execute_script("arguments[0].click();", target_btn)
                
                # --- 新規タブ（応募確認画面）での操作 ---
                wait.until(lambda d: len(d.window_handles) > 1)
                new_window = [h for h in driver.window_handles if h != main_window][0]
                driver.switch_to.window(new_window)

                # ボタンが表示されるまで待機
                final_btn = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "apply-jobs")))
                
                # すでに応募済みかチェック
                is_disabled = final_btn.get_attribute("disabled") is not None
                is_not_active = "not-active" in (final_btn.get_attribute("class") or "")

                if is_disabled or is_not_active:
                    print(f"結果: {i+1}件目は応募済みのためスキップ")
                else:
                    # 【ここから修正：クリック後のロードと上限エラー判定】
                    driver.execute_script("arguments[0].click();", final_btn)
                    print("   -> 応募実行（通信中...）")

                    # ロード中(display: noneでない状態)になるのを一瞬待つ
                    try:
                        WebDriverWait(driver, 1).until(lambda d: 
                            "display: none" not in d.find_element(By.ID, "loader-main").get_attribute("style")
                        )
                    except:
                        pass

                    # ロード完了(display: noneに戻る)を待機
                    WebDriverWait(driver, 20).until(lambda d: 
                        "display: none" in d.find_element(By.ID, "loader-main").get_attribute("style")
                    )

                    # ロード明け直後に「10件上限エラー」が出ているか判定
                    error_xpath = "//div[contains(@class, '_error')]//p[contains(text(), '1日に10件まで')]"
                    if len(driver.find_elements(By.XPATH, error_xpath)) > 0:
                        print("!!! ロード明けに上限エラー（10件制限）を検知。終了します。")
                        driver.close()
                        driver.switch_to.window(main_window)
                        raise RuntimeError("Daily Limit Reached")

                    # エラーがない場合は完了メッセージを待つ
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'お仕事応募が完了しました')]"))
                    )
                    print(f"結果: {i+1}件目の応募完了！")

                # タブを閉じて戻る
                driver.close()
                driver.switch_to.window(main_window)
                time.sleep(1.5)

            except Exception as e:
                        # もし「上限エラー」による中断なら、スキップせずにプログラムを終了させる
                        if "Daily Limit Reached" in str(e):
                            print(">>> [停止] 応募上限に達したため、全プロセスを終了します。")
                            # 上位の while ループも抜けるために、再度エラーを投げる
                            raise e
                        
                        # それ以外（通信エラーなど）は従来通りスキップして継続
                        print(f"警告: {i+1}件目でエラー発生。スキップして次へ: {e}")
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(main_window)
                        continue

        # --- ページ内の全件（forループ）が終わってから、初めて「次へ」の判定 ---
        print("現在のページの全件処理が終了しました。次ページを確認します。")
        try:
            # 「次へ」ボタンが有効（表示されている）か確認
            next_btn_xpath = "//a[contains(@class, '_next') and .//span[text()='次へ']]"
            next_btn = driver.find_element(By.XPATH, next_btn_xpath)
            
            # visible かどうかをチェック（ Knockout.js の visible バインド対応）
            if next_btn.is_displayed():
                driver.execute_script("arguments[0].click();", next_btn)
                print(">>> 次のページへ移動しました")
                
                # ロード完了待ち
                WebDriverWait(driver, 30).until(
                    lambda d: "display: none" in d.find_element(By.ID, "loader-main").get_attribute("style")
                )
                time.sleep(2)
            else:
                print("次のページはありません。終了します。")
                break
        except NoSuchElementException:
            print("「次へ」ボタンが存在しないため終了します。")
            break

    print("すべてのプロセスの自動化が完了しました。")

    # ログイン後の遷移を待つための待機（必要に応じて）
    time.sleep(5)

except RuntimeError as e:
    if str(e) == "Daily Limit Reached":
        print("本日の作業は正常に終了しました（上限到達）。")
    else:
        print(f"予期せぬ実行エラー: {e}")
except Exception as e:
    print(f"エラーが発生しました: {e}")
finally:
    driver.quit()
