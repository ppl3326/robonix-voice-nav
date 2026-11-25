from robonix_api import Service, Ok
import roslibpy
import time
import math
import json
import openai
from aip import AipSpeech
import speech_recognition as sr
import threading
import os
import sys

# 屏蔽 ALSA 驱动的底层刷屏报错
os.close(sys.stderr.fileno()) 

# ================= 配置区 =================
APP_ID = '8098922'
API_KEY = 'O8fdBfbhOJLBTj8z2x06keHl'
SECRET_KEY = os.getenv("SECRET_KEY"," ")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-your-api-key-here")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

CAR_IP = "10.206.236.227"  # 你的小车 IP

# 增加了更多的目标点（注意坐标要在你地图的空地上）
SEMANTIC_MAP = """
- 目标点一 (坐标: x=1.0, y=0.0, 朝向=0.0)
- 目标点二 (坐标: x=2.0, y=1.0, 朝向=0.0)
- 目标点三 (坐标: x=3.0, y=-1.0, 朝向=0.0)
- 目标点四 (坐标: x=4.0, y=-2.0, 朝向=0.0)
- 目标点五 (坐标: x=6.0, y=-3.0, 朝向=0.0)
- 原点 (坐标: x=0.0, y=0.0, 朝向=0.0)
"""
# ==========================================

baidu_client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)
openai.api_key = DEEPSEEK_API_KEY
openai.api_base = DEEPSEEK_BASE_URL
ros_client = None
r = sr.Recognizer()

provider = Service(id="voice_nav_service", namespace="robonix/service/voice_nav")

@provider.on_init
def init(cfg: dict):
    global ros_client
    print("[Provider Init] 正在连接小车 rosbridge...")
    try:
        ros_client = roslibpy.Ros(host=CAR_IP, port=9090)
        ros_client.run(timeout=3)
        if ros_client.is_connected:
            print("[Provider Init] ✅ 连接成功")
        else:
            print("[Provider Init] ⚠️ 未连接，检查小车")
    except Exception as e:
        print(f"[Provider Init] ⚠️ 连接异常: {e}")
    return Ok()

@provider.on_activate
def activate():
    def voice_loop():
        print("\n🎤 [Liaison] 语音监听已启动！请直接说出指令...")
        
        while True:
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=5, phrase_time_limit=5)
                    
                    audio_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    result = baidu_client.asr(audio_data, 'pcm', 16000, {'dev_pid': 1537})
                    
                    if result.get('err_no') == 0:
                        user_input = result['result'][0]
                        if len(user_input) < 2: 
                            continue
                            
                        print(f"\n🗣️ [Liaison] 识别成功: {user_input}")
                        print("🧠 [Pilot] 正在解析意图...")
                        
                        prompt = f"""
                        你是机器人导航大脑。可选目标点：
                        {SEMANTIC_MAP}
                        请根据用户输入判断去哪。只返回JSON：
                        {{"target_name": "名称", "x": 1.0, "y": 0.0, "yaw": 0.0}}
                        无法识别则返回 {{"error": "无法识别"}}
                        用户说: "{user_input}"
                        """
                        
                        response = openai.ChatCompletion.create(
                            model=MODEL,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0,
                        )
                        ans = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
                        data = json.loads(ans)
                        
                        if "error" not in data and ros_client and ros_client.is_connected:
                            # ====================================================
                            # 【核心修正】因为地图偏左45度，强行减去 0.785 弧度（往右掰）
                            corrected_yaw = data['yaw'] - 0.785
                            
                            qz = math.sin(corrected_yaw / 2.0)
                            qw = math.cos(corrected_yaw / 2.0)
                            # ====================================================
                            
                            goal_msg = {
                                'header': {'frame_id': 'map', 'stamp': {'secs': int(time.time()), 'nsecs': 0}},
                                'pose': {'position': {'x': data['x'], 'y': data['y'], 'z': 0.0}, 'orientation': {'x': 0.0, 'y': 0.0, 'z': qz, 'w': qw}}
                            }
                            topic = roslibpy.Topic(ros_client, '/move_base_simple/goal', 'geometry_msgs/PoseStamped')
                            topic.publish(roslibpy.Message(goal_msg))
                            print(f"🚀 [Executor] 任务下发: {data['target_name']}，坐标 ({data['x']:.2f}, {data['y']:.2f})，修正后朝向 {corrected_yaw:.2f}")
                        else:
                            print("⚠️ 无法下发：未连上小车或未识别目标")
            except sr.WaitTimeoutError:
                pass
            except Exception:
                pass
            time.sleep(0.5)

    thread = threading.Thread(target=voice_loop, daemon=True)
    thread.start()
    return Ok()

if __name__ == "__main__":
    provider.run()
