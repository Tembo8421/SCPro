使用說明
1. 使用原碼請安裝相關套件
python -m pip install -r requirements.txt

2. 修改 upload or download 設定檔：
    - 上傳檔案請編輯存儲庫下 'upload' 開頭的 JSON 檔案
    - 下載檔案請編輯存儲庫下 'download' 開頭的 JSON 檔案
    - 預設存儲庫: 'storage/'
    - 可自行新增字定義設定檔，但請依照命名規則命名。

JSON 檔參數說明：

- ref_folder: 目標來源的參考路徑，
    - 在download設定檔中：
        如果是相對路徑，則相對於 `遠端電腦的根目錄`。
        如果是絕對路徑，那就是遠端電腦的該路徑。

    - 在upload設定檔中：
        如果是相對路徑，則相對於 `該設定檔的所在目錄`。
        如果是絕對路徑，那就是本機電腦的該路徑。

- pre_cmds: 檔案傳輸操作前要在遠端主機執行的指令列表。

- post_cmds: 檔案傳輸操作後要在遠端主機執行的指令列表。

    指令列表支援參數：
      "retry":       重發次數 (default=2)，
      "timeout_sec": 逾時時間 (default=10),
      "retry":       重試次數 (default=2),
      "readuntil":   如果有設定字詞，則執行指令直到讀取到關鍵字詞,
      "waiting_sec": 指令結束後讓程序等待 (default=0),

    範例：
    {
        "cmd": "echo 'Hello SCPro'",
        "timeout_sec": 3, 
        "retry": 2,
        "readuntil": "SCPro",
        "waiting_sec": 10
    }

  - files: 要上傳或下載的檔案或目錄
        "update_or_not":  是否要執行的開關。
        "name":           檔名/目錄名。
        "folder":         所在子目錄 (相對於 ref_folder)。
        "target_path":    傳輸檔案的目標路徑，如果是'/'結尾，則表示將該傳輸目標以原檔名傳送到該目錄下，否則將以此路徑重新命名。
        "pre_cmds":       傳檔案操作前要在遠端主機執行的指令列表。
        "post_cmds":      傳檔案操作後要在遠端主機執行的指令列表。

        範例：
        {
            "update_or_not": true,
            "name": "libuv_1.41.0-1_realtek.ipk",
            "folder": "",
            "target_path": "/root/",
            "post_cmds": [
                {
                    "cmd": "opkg install /root/libuv_1.41.0-1_realtek.ipk"
                }
            ]
        }

  - 設定檔的魔術變數：
      在設定檔中，可以看到有用大括弧刮起來的 '{魔術變數}'，它會在程式執行時，被替換成對應的文字串。
      可以按下 SCP Setting 按鈕查看對應內容，並可自行添加變數。

3. 執行方式
在 SCPRO 資料夾中執行python指令 python ./scpro.py

    1. 輸入要掃描的網路範圍：
      192.168.50.2-120 或 192.168.48.0/21

    2. 選擇要針對的目標裝置操作：
        a. Get Device Info
            - 獲取裝置資訊包含：
                OS:       作業系統版本
                RS        restart_server.sh 版本
                RN        restart_server.sh 版本
                OTA       ota.sh 版本
                MAC       mac address
                Model     model-id
                FW        commit-id
                LGW       light_gw_server 版本
                Product   product-id
        b. Ping
            獨立程序，運行後可在介面上對個別裝置進行參加或離開Ping程序
        c. SCP Upload
            選擇對應的設定檔後，程式會依照內容進行操作。(此功能只在OS連線模式為SSH時可用)
        d. SCP Download
            選擇對應的設定檔後，程式會依照內容進行操作。(此功能只在OS連線模式為SSH時可用)
        e. Send OS Commands
            新增可一次貼上多筆 OS 指令程式會以換行符號進行分割，程式會把這些指令當作是一組連續的操作流程。
        f. Send LGW Commands
            所有新增的 LGW 指令只要有 target-id 的部分在程式發送之前都會被自動替換成對應的值。
            新增可一次貼上多筆指令程式會以換行符號進行分割，並以一筆指令為單位加入程式。
            - **目前的限制:**
              1. 發送 enumerate 指令會有問題。
              2. 對LGW 同時發送超過30個指令會發生失敗，同一台裝置 `發送的channel數量` 乘以 `發送的指令數目` 請控制在 30 以內。

    3. Configure 按鈕可以選擇 OS 連線的方式，預設是 SSH 密碼是預設密碼

    4. Ping 按鈕會對當前選取的裝置進行 Ping 操作

    5. SCP Setting 按鈕可以設定儲存庫路徑與SCP 設定檔變數

    6. 雙擊兩下 Scan Table 的裝置會給你他歷史的結果 (藍色)，雙擊空白區會清空選取狀態，雙擊標題列會進行遞增排序。

    7. log 在 log目錄下以裝置分目錄

