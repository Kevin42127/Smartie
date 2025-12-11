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

conversation_history = {}

MAX_HISTORY_LENGTH = 10
MAX_HISTORY_TOKENS = 2000

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

def get_conversation_history(user_id: int):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    return conversation_history[user_id]

def add_to_history(user_id: int, role: str, content: str):
    history = get_conversation_history(user_id)
    history.append({"role": role, "content": content})
    
    total_tokens = sum(len(msg["content"]) // 3 for msg in history)
    
    while len(history) > MAX_HISTORY_LENGTH or total_tokens > MAX_HISTORY_TOKENS:
        removed = history.pop(0)
        total_tokens -= len(removed["content"]) // 3

def build_messages(system_prompt: str, user_message: str, user_id: int):
    history = get_conversation_history(user_id)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history:
        messages.append(msg)
    
    messages.append({"role": "user", "content": user_message})
    return messages

@bot.tree.command(name="小智", description="與小智 AI 助手對話")
@app_commands.describe(message="要發送的訊息")
async def xiaozhi(interaction: discord.Interaction, message: str):
    import time
    start_time = time.time()
    user_id = interaction.user.id
    
    await interaction.response.defer(thinking=True)
    
    if not message or len(message.strip()) == 0:
        await interaction.followup.send("請輸入有效的訊息內容")
        return
    
    if len(message) > 2000:
        await interaction.followup.send("訊息長度不能超過 2000 字元")
        return
    
    try:
        message_length = len(message)
        
        if message_length > 1500:
            await interaction.followup.send("⚠️ 偵測到長訊息，正在處理中...")
        
        history = get_conversation_history(user_id)
        history_tokens = sum(len(msg["content"]) // 3 for msg in history)
        estimated_tokens = message_length // 3
        available_tokens = 4096 - history_tokens - estimated_tokens - 200
        max_tokens_value = max(512, min(2048, available_tokens))
        
        if message_length > 1500:
            system_prompt = "你是一個友善、自然的 AI 助手，由 Groq AI 提供技術支援。你的名字是小智，專門在 Discord 伺服器中幫助用戶回答問題和進行對話。\n\n重要：你必須且只能使用繁體中文回應，絕對不能使用簡體中文。所有回應都必須使用繁體中文字體，包括標點符號。如果遇到簡體中文輸入，請在回應時轉換為繁體中文。\n\n請用繁體中文以自然、口語化的方式回應，就像和朋友聊天一樣。避免使用過於正式或生硬的語氣，讓對話更流暢自然。當被問到你是誰、你的身分或相關問題時，請自然地介紹自己是小智。\n\n注意：用戶的訊息較長，請簡潔地回應重點。"
        else:
            system_prompt = "你是一個友善、自然的 AI 助手，由 Groq AI 提供技術支援。你的名字是小智，專門在 Discord 伺服器中幫助用戶回答問題和進行對話。\n\n重要：你必須且只能使用繁體中文回應，絕對不能使用簡體中文。所有回應都必須使用繁體中文字體，包括標點符號。如果遇到簡體中文輸入，請在回應時轉換為繁體中文。\n\n請用繁體中文以自然、口語化的方式回應，就像和朋友聊天一樣。避免使用過於正式或生硬的語氣，讓對話更流暢自然。當被問到你是誰、你的身分或相關問題時，請自然地介紹自己是小智。"
        
        messages = build_messages(system_prompt, message, user_id)
        
        response_text = ""
        message_obj = None
        update_queue = asyncio.Queue()
        update_interval = 1.5
        
        async def update_message_periodically():
            nonlocal message_obj
            last_text = ""
            
            while True:
                try:
                    current_text = await asyncio.wait_for(update_queue.get(), timeout=update_interval)
                    if current_text == "DONE":
                        break
                    
                    if current_text != last_text and len(current_text) > 50:
                        preview_text = current_text[:1900] + ("..." if len(current_text) > 1900 else "")
                        
                        embed = discord.Embed(
                            description=preview_text,
                            color=0x5865F2
                        )
                        embed.set_footer(text="⏳ 正在生成回應...")
                        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
                        
                        try:
                            if message_obj:
                                await message_obj.edit(embed=embed)
                            else:
                                message_obj = await interaction.followup.send(embed=embed)
                            last_text = current_text
                        except:
                            pass
                except asyncio.TimeoutError:
                    if last_text:
                        preview_text = last_text[:1900] + ("..." if len(last_text) > 1900 else "")
                        embed = discord.Embed(
                            description=preview_text,
                            color=0x5865F2
                        )
                        embed.set_footer(text="⏳ 正在生成回應...")
                        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
                        
                        try:
                            if message_obj:
                                await message_obj.edit(embed=embed)
                        except:
                            pass
        
        def stream_response():
            nonlocal response_text
            
            stream = groq_client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=max_tokens_value,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                    response_text += chunk.choices[0].delta.content
                    try:
                        update_queue.put_nowait(response_text)
                    except:
                        pass
            
            update_queue.put_nowait("DONE")
            return response_text
        
        update_task = asyncio.create_task(update_message_periodically())
        
        loop = asyncio.get_event_loop()
        response_text = await asyncio.wait_for(
            loop.run_in_executor(None, stream_response),
            timeout=60.0
        )
        
        await update_task
        
        add_to_history(user_id, "user", message)
        add_to_history(user_id, "assistant", response_text)
        
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
        
        if message_obj:
            await message_obj.edit(embed=embed)
        else:
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
        
        error_lower = error_msg.lower()
        if "api_key" in error_lower or "authentication" in error_lower:
            embed.description = "🔐 API 驗證失敗，請檢查 API key 設定"
        elif "rate_limit" in error_lower or "quota" in error_lower:
            embed.description = "⚠️ API 使用量已達上限，請稍後再試"
        elif "context_length" in error_lower or "token" in error_lower or "length" in error_lower or "too long" in error_lower:
            embed.description = "📝 訊息太長了！請將訊息縮短或分段發送。建議長度約為 1500 字元以內。"
        else:
            embed.description = f"❌ 發生錯誤，請稍後再試"
            print(f"錯誤詳情: {error_msg}")
        
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="清除記憶", description="清除與小智的對話記憶")
async def clear_memory(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    if user_id in conversation_history:
        conversation_history[user_id] = []
        embed = discord.Embed(
            description="✅ 已清除對話記憶",
            color=0x00FF00
        )
        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            description="ℹ️ 你還沒有對話記錄",
            color=0x5865F2
        )
        embed.set_author(name="小智", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

