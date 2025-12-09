import os
import discord
from discord import app_commands
from discord.ext import commands
from groq import Groq
from dotenv import load_dotenv
import asyncio
from pathlib import Path

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')
DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN 環境變數未設定，請檢查 .env 檔案")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY 環境變數未設定，請檢查 .env 檔案")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

groq_client = Groq(api_key=GROQ_API_KEY)

@bot.event
async def on_ready():
    print(f'{bot.user} 已上線')
    try:
        synced = await bot.tree.sync()
        print(f'已同步 {len(synced)} 個全局斜線指令')
        for cmd in synced:
            print(f'  - /{cmd.name}')
        print('提示：全局指令更新可能需要 1-2 小時才會在 Discord 中顯示')
        print('如果急需使用，可以等待幾分鐘後重新整理 Discord')
    except Exception as e:
        print(f'同步指令時發生錯誤: {e}')
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="正在幫助用戶"))

@bot.tree.command(name="小智", description="與小智 AI 助手對話")
@app_commands.describe(message="要發送的訊息")
async def xiaozhi(interaction: discord.Interaction, message: str):
    import time
    start_time = time.time()
    
    await interaction.response.defer(thinking=True)
    
    if not message or len(message.strip()) == 0:
        await interaction.followup.send("請輸入有效的訊息內容")
        return
    
    if len(message) > 2000:
        await interaction.followup.send("訊息長度不能超過 2000 字元")
        return
    
    try:
        loop = asyncio.get_event_loop()
        chat_completion = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: groq_client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一個友善、自然的 AI 助手，由 Groq AI 提供技術支援。你的名字是小智，專門在 Discord 伺服器中幫助用戶回答問題和進行對話。\n\n重要：你必須且只能使用繁體中文回應，絕對不能使用簡體中文。所有回應都必須使用繁體中文字體，包括標點符號。如果遇到簡體中文輸入，請在回應時轉換為繁體中文。\n\n請用繁體中文以自然、口語化的方式回應，就像和朋友聊天一樣。避免使用過於正式或生硬的語氣，讓對話更流暢自然。當被問到你是誰、你的身分或相關問題時，請自然地介紹自己是小智。"
                        },
                        {
                            "role": "user",
                            "content": message
                        }
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                    max_tokens=1024
                )
            ),
            timeout=30.0
        )
        
        response_text = chat_completion.choices[0].message.content
        
        if len(response_text) > 2000:
            response_text = response_text[:1997] + "..."
        
        elapsed_time = time.time() - start_time
        response_time_text = f"⏱️ 回應時間: {elapsed_time:.2f} 秒"
        
        embed = discord.Embed(
            description=response_text,
            color=0x5865F2
        )
        embed.set_footer(text=response_time_text)
        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        await interaction.followup.send(embed=embed)
        
    except asyncio.TimeoutError:
        embed = discord.Embed(
            description="⏰ 抱歉，處理時間過長，請稍後再試",
            color=0xFF0000
        )
        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        error_msg = str(e)
        embed = discord.Embed(color=0xFF0000)
        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            embed.description = "🔐 API 驗證失敗，請檢查 API key 設定"
        elif "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
            embed.description = "⚠️ API 使用量已達上限，請稍後再試"
        else:
            embed.description = f"❌ 發生錯誤，請稍後再試"
            print(f"錯誤詳情: {error_msg}")
        
        await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

