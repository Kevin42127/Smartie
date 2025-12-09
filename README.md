# Discord Bot with Groq AI

使用 Python 開發的 Discord bot，整合 Groq AI，透過斜線指令與 AI 對話。

## 功能

- `/chat` - 與 Groq AI 進行對話

## 安裝步驟

1. 安裝 Python 3.8 或更高版本

2. 安裝依賴套件：
```bash
pip install -r requirements.txt
```

3. 設定環境變數：
   - 建立 `.env` 檔案
   - 填入以下資訊：
     - `DISCORD_TOKEN` - Discord Bot Token
     - `GROQ_API_KEY` - Groq API Key
     - `DISCORD_PUBLIC_KEY` - Discord Public Key（可選，用於互動式組件驗證）
     - `DISCORD_APPLICATION_ID` - Discord Application ID（可選）

4. 取得 Discord Bot Token：
   - 前往 [Discord Developer Portal](https://discord.com/developers/applications)
   - 建立新應用程式或選擇現有的
   - 前往 Bot 頁面，建立 bot 並複製 Token
   - 在 Bot Permissions 頁面勾選以下權限：
     - **View Channels**（查看頻道）
     - **Send Messages**（發送訊息）
     - **Use Slash Commands**（使用斜線指令）
     - **Read Message History**（讀取訊息歷史，建議勾選）
   - 在 OAuth2 > URL Generator 中，選擇 `bot` 和 `applications.commands` 權限
   - 將生成的 URL 貼到瀏覽器，將 bot 邀請到你的伺服器

5. 執行 bot：
```bash
python main.py
```

## 使用方式

在 Discord 中輸入 `/chat` 指令，然後輸入你想問的問題。

## Bot 資訊

- Application ID: `1447853825057619981`
- Public Key: `fa62dd363db8dd7603e5db5b2c916c18bec55cdec02968ca714755ed2d395f2c`

## 注意事項

- 確保 `.env` 檔案已加入 `.gitignore`，不會被提交到版本控制
- Bot 需要 `applications.commands` 權限才能使用斜線指令
- API 有使用頻率限制，請適度使用
- Public Key 和 Application ID 主要用於互動式組件驗證，目前實作中為可選項目

