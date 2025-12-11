import os
import json
import time
from http.server import BaseHTTPRequestHandler
from groq import Groq
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')

conversation_history = {}

MAX_HISTORY_LENGTH = 10
MAX_HISTORY_TOKENS = 2000

def get_conversation_history(user_id: str):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    return conversation_history[user_id]

def add_to_history(user_id: str, role: str, content: str):
    history = get_conversation_history(user_id)
    history.append({"role": role, "content": content})
    
    total_tokens = sum(len(msg["content"]) // 3 for msg in history)
    
    while len(history) > MAX_HISTORY_LENGTH or total_tokens > MAX_HISTORY_TOKENS:
        removed = history.pop(0)
        total_tokens -= len(removed["content"]) // 3

def build_messages(system_prompt: str, user_message: str, user_id: str):
    history = get_conversation_history(user_id)
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history:
        messages.append(msg)
    
    messages.append({"role": "user", "content": user_message})
    return messages

def verify_signature(raw_body, signature, timestamp):
    try:
        if not DISCORD_PUBLIC_KEY:
            print("DISCORD_PUBLIC_KEY not configured")
            return False
        message = timestamp.encode() + raw_body
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(message, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, TypeError) as e:
        print(f"Signature verification error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in verify_signature: {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            signature = self.headers.get('x-signature-ed25519', '') or self.headers.get('X-Signature-Ed25519', '')
            timestamp = self.headers.get('x-signature-timestamp', '') or self.headers.get('X-Signature-Timestamp', '')
            
            content_length = int(self.headers.get('Content-Length', 0))
            raw_body = self.rfile.read(content_length)
            
            if not DISCORD_PUBLIC_KEY:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'DISCORD_PUBLIC_KEY not configured'}).encode())
                return
            
            if not verify_signature(raw_body, signature, timestamp):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid signature'}).encode())
                return
            
            try:
                data = json.loads(raw_body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"JSON decode error: {e}")
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())
                return
            
            if data.get('type') == 1:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'type': 1}).encode())
                return
            
            if data.get('type') == 2:
                command_name = data.get('data', {}).get('name', '')
                if command_name == '小智':
                    options = data.get('data', {}).get('options', [])
                    if not options:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'content': '請輸入有效的訊息內容'
                            }
                        }).encode())
                        return
                    
                    message = options[0].get('value', '')
                    
                    if not message or len(message.strip()) == 0:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'content': '請輸入有效的訊息內容'
                            }
                        }).encode())
                        return
                    
                    if len(message) > 2000:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'content': '訊息長度不能超過 2000 字元'
                            }
                        }).encode())
                        return
                    
                    if not GROQ_API_KEY:
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [{
                                    'color': 0xFF0000,
                                    'author': {'name': '小智'},
                                    'description': '🔐 API key 未設定，請檢查環境變數'
                                }]
                            }
                        }).encode())
                        return
                    
                    start_time = time.time()
                    message_length = len(message)
                    user_id = str(data.get('member', {}).get('user', {}).get('id', '') or data.get('user', {}).get('id', ''))
                    
                    try:
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
                        
                        groq_client = Groq(api_key=GROQ_API_KEY)
                        chat_completion = groq_client.chat.completions.create(
                            messages=messages,
                            model="llama-3.3-70b-versatile",
                            temperature=0.7,
                            max_tokens=max_tokens_value
                        )
                        
                        response_text = chat_completion.choices[0].message.content
                        
                        add_to_history(user_id, "user", message)
                        add_to_history(user_id, "assistant", response_text)
                        
                        if len(response_text) > 2000:
                            response_text = response_text[:1997] + "..."
                        
                        elapsed_time = time.time() - start_time
                        response_time_text = f"⏱️ 回應時間: {elapsed_time:.2f} 秒"
                        
                        embed = {
                            "description": response_text,
                            "color": 0x5865F2,
                            "footer": {
                                "text": response_time_text
                            },
                            "author": {
                                "name": "小智"
                            }
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [embed]
                            }
                        }).encode())
                        return
                        
                    except Exception as e:
                        error_msg = str(e)
                        print(f"Groq API error: {error_msg}")
                        embed = {
                            "color": 0xFF0000,
                            "author": {
                                "name": "小智"
                            }
                        }
                        
                        error_lower = error_msg.lower()
                        if "api_key" in error_lower or "authentication" in error_lower:
                            embed["description"] = "🔐 API 驗證失敗，請檢查 API key 設定"
                        elif "rate_limit" in error_lower or "quota" in error_lower:
                            embed["description"] = "⚠️ API 使用量已達上限，請稍後再試"
                        elif "context_length" in error_lower or "token" in error_lower or "length" in error_lower or "too long" in error_lower:
                            embed["description"] = "📝 訊息太長了！請將訊息縮短或分段發送。建議長度約為 1500 字元以內。"
                        else:
                            embed["description"] = "❌ 發生錯誤，請稍後再試"
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [embed]
                            }
                        }).encode())
                        return
                
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unknown command'}).encode())
                return
            
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unknown interaction type'}).encode())
            
        except Exception as e:
            error_msg = str(e)
            print(f"Unhandled exception in do_POST: {error_msg}")
            import traceback
            print(traceback.format_exc())
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Internal server error'}).encode())
            except:
                pass
    
    def do_GET(self):
        self.send_response(405)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'Method not allowed'}).encode())
    
    def log_message(self, format, *args):
        pass
