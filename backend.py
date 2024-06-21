# voice to backend to text
from openai import AsyncOpenAI
import pyaudio
import requests
import asyncio
import pyaudio
import aiohttp
import audioop
import wave
import os
import queue

# 配置音频流参数
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5  # 每次录音的时长（秒）
AUDIO_FILE = "D:\\Code\\audio.wav"


client = AsyncOpenAI(api_key="cant-be-empty", base_url="http://localhost:8001/v1/")

audio_file = open("D:\\Code\\warmup.mp3", "rb")

# 创建一个线程安全的队列
audio_queue = queue.Queue()
# 初始化PyAudio
p = pyaudio.PyAudio()
async def record_audio():
    # 打开音频流
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    silence_threshold = 500
    try:
        print("开始录音... 按Ctrl+C停止")
        while True:
            frames = []

            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK)
                avg_amplitude = audioop.rms(data, 2)  # 计算平均振幅
                if avg_amplitude > silence_threshold:
                    frames.append(data)

            if frames:  # 如果有非静音数据，则加入队列
                audio_queue.put(b''.join(frames))

            await asyncio.sleep(0.1)  # 确保文件写入完成
    except KeyboardInterrupt:
        print("录音结束")
    finally:
        # 关闭音频流
        stream.stop_stream()
        stream.close()
        p.terminate()

async def send_audio():
    async with aiohttp.ClientSession() as session:
        try:
            while True:
                if audio_queue.empty():
                    await asyncio.sleep(0.1)
                    continue
                audio_data = audio_queue.get()
                
                # 保存音频数据到文件
                with wave.open(AUDIO_FILE, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(audio_data)

                if os.path.exists(AUDIO_FILE):
                    with open(AUDIO_FILE, 'rb') as f:
                        audio_data = f.read()

                        transcript = await client.audio.transcriptions.create(
                                model="large-v3", 
                                file=audio_data, 
                                language="zh",
                                response_format="text"
                            )
                        for res in transcript:
                            print(res,end="",flush=True)

                    os.remove(AUDIO_FILE)  # 发送成功后删除文件

                await asyncio.sleep(0.1)  # 等待下一次发送
        except KeyboardInterrupt:
            print("发送音频任务结束")

async def main():
    record_task = asyncio.create_task(record_audio())
    send_task = asyncio.create_task(send_audio())

    await asyncio.gather(record_task, send_task)

if __name__ == "__main__":
    asyncio.run(main())
