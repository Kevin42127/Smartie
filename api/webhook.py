import os
import json
import time
from groq import Groq
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')

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

def handler(request):
    try:
        method = 'GET'
        if hasattr(request, 'method'):
            try:
                method = request.method
            except Exception as e:
                print(f"Error accessing request.method: {e}")
        
        if method != 'POST':
            return {
                'statusCode': 405,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Method not allowed'})
            }
        
        headers = {}
        try:
            if hasattr(request, 'headers'):
                h = request.headers
                if isinstance(h, dict):
                    headers = h
                else:
                    try:
                        headers = dict(h)
                    except:
                        headers = {}
        except Exception as e:
            print(f"Error reading headers: {e}")
            headers = {}
        
        signature = headers.get('x-signature-ed25519', '') or headers.get('X-Signature-Ed25519', '')
        timestamp = headers.get('x-signature-timestamp', '') or headers.get('X-Signature-Timestamp', '')
        
        raw_body = b''
        try:
            if hasattr(request, 'body'):
                body = request.body
                if isinstance(body, str):
                    raw_body = body.encode('utf-8')
                elif body is not None:
                    raw_body = bytes(body) if not isinstance(body, bytes) else body
        except Exception as e:
            print(f"Error reading request body: {e}")
            raw_body = b''
        
        if not DISCORD_PUBLIC_KEY:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'DISCORD_PUBLIC_KEY not configured'})
            }
        
        if not verify_signature(raw_body, signature, timestamp):
            return {
                'statusCode': 401,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        try:
            data = json.loads(raw_body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"JSON decode error: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid JSON'})
            }
        
        if data.get('type') == 1:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'type': 1})
            }
        
        if data.get('type') == 2:
            command_name = data.get('data', {}).get('name', '')
            if command_name == '小智':
                options = data.get('data', {}).get('options', [])
                if not options:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'content': '請輸入有效的訊息內容'
                            }
                        })
                    }
                
                message = options[0].get('value', '')
                
                if not message or len(message.strip()) == 0:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'content': '請輸入有效的訊息內容'
                            }
                        })
                    }
                
                if len(message) > 2000:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'content': '訊息長度不能超過 2000 字元'
                            }
                        })
                    }
                
                if not GROQ_API_KEY:
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [{
                                    'color': 0xFF0000,
                                    'author': {'name': '小智'},
                                    'description': '🔐 API key 未設定，請檢查環境變數'
                                }]
                            }
                        })
                    }
                
                start_time = time.time()
                
                try:
                    groq_client = Groq(api_key=GROQ_API_KEY)
                    chat_completion = groq_client.chat.completions.create(
                        messages=[
                            {
                                "role": "system",
                                "content": "你是一個友善、自然的 AI 助手，由 Groq AI 提供技術支援。你的名字是小智，專門在 Discord 伺服器中幫助用戶回答問題和進行對話。請用繁體中文以自然、口語化的方式回應，就像和朋友聊天一樣。避免使用過於正式或生硬的語氣，讓對話更流暢自然。當被問到你是誰、你的身分或相關問題時，請自然地介紹自己是小智。"
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
                    
                    response_text = chat_completion.choices[0].message.content
                    
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
                    
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [embed]
                            }
                        })
                    }
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"Groq API error: {error_msg}")
                    embed = {
                        "color": 0xFF0000,
                        "author": {
                            "name": "小智"
                        }
                    }
                    
                    if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                        embed["description"] = "🔐 API 驗證失敗，請檢查 API key 設定"
                    elif "rate_limit" in error_msg.lower() or "quota" in error_msg.lower():
                        embed["description"] = "⚠️ API 使用量已達上限，請稍後再試"
                    else:
                        embed["description"] = "❌ 發生錯誤，請稍後再試"
                    
                    return {
                        'statusCode': 200,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'type': 4,
                            'data': {
                                'embeds': [embed]
                            }
                        })
                    }
            
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Unknown command'})
            }
    
    except Exception as e:
        error_msg = str(e)
        print(f"Unhandled exception in handler: {error_msg}")
        import traceback
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Internal server error'})
        }
