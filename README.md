使用說明
1. 安裝相關套件
python -m pip install -r requirements.txt


2. 修改 storage/upload.json or storage/download.json
上傳檔案請修改storage/upload.json
下載檔案請修改storage/download.json

參數說明：

ref_folder: 來源目標的參考路徑，
  在download.json中預設是 "/"
  在upload.json中如果是相對路徑，則相對於該json所在目錄。

pre_cmds: 操作前要在遠端主機執行的指令列表。

post_cmds: 操作後要在遠端主機執行的指令列表。

指令列表支援參數：
"retry"       重發次數 (default=2)，
"timeout_sec" 逾時時間 (default=10),
"retry"       重試次數 (default=2),
"waiting_sec" 指令結束後讓程序等待 (default=0),


範例：
{
    "cmd": "flash get HW_NIC1_ADDR | cut -d '=' -f 2",
    "timeout_sec": 3, 
    "retry": 2,
    "waiting_sec":
}

files: 要上傳或下載的檔案/目錄
    update_or_not: 更新開關。
    name: 檔名/目錄名。
    folder: 所在子目錄。
    pre_cmds: 傳檔案操作前要在遠端主機執行的指令列表。
    post_cmds: 傳檔案操作後要在遠端主機執行的指令列表。


3. 執行方式
在 SCPRO 資料夾中執行python指令 python ./scpro.py

    1. 輸入要掃描的網路範圍：
      192.168.50.2-120 或 192.168.48.0/21

    2. 選擇要針對的目標裝置操作

    3. Configure 按鈕可以選擇 OS 連線的方式，預設是 SSH 密碼是預設密碼

    4. Ping 按鈕會對當前選取的裝置進行 Ping 操作

    5. SCP setting 按鈕可以更換儲存庫路徑

    6. 雙擊兩下 device table 的裝置會給你他歷史操作的結果

    7. log 在 log目錄下以裝置分目錄

4. Note:

  echo -e "Aekoathi0Ahchoa1Iokeejex3doo9tu0\nAekoathi0Ahchoa1Iokeejex3doo9tu0" | passwd root
  reboot


## Package
pip install auto-py-to-exe

pyinstaller --noconfirm --onefile --windowed --add-data "D:/SCPro/core;core/" --add-data "D:/SCPro/network;network/" --add-data "D:/SCPro/scanner;scanner/" --add-data "D:/SCPro/arp-scan-windows;arp-scan-windows/" --hidden-import "win32timezone"  "D:/SCPro/scpro.py"