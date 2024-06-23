# voice to backend to text
from openai import AsyncOpenAI
import requests
import asyncio
import pyaudio
import aiohttp
import audioop
import wave
import os
from multiprocessing import Queue, Process
import time
from datetime import datetime
# 配置音频流参数
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 2  # 每次录音的时长（秒）
AUDIO_FILE = "D:\\Code\\audio.wav"


stt_client = AsyncOpenAI(api_key="cant-be-empty", base_url="http://localhost:8001/v1/")
tts_client = AsyncOpenAI(api_key="cant-be-empty", base_url="http://localhost:7870/v1/")

audio_file = open("D:\\Code\\warmup.mp3", "rb")

def record_audio(audio_queue):
    # 初始化PyAudio
    p = pyaudio.PyAudio()
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

            time.sleep(0.1)  # 确保文件写入完成
    except KeyboardInterrupt:
        print("录音结束")
    finally:
        # 关闭音频流
        stream.stop_stream()
        stream.close()
        p.terminate()

async def send_audio(audio_queue, text_queue):
    try:
        while True:
            if audio_queue.empty():
                await asyncio.sleep(0.1)
                continue
            audio_data = audio_queue.get()
            
            # 保存音频数据到文件
            with wave.open(AUDIO_FILE, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(audio_data)

            if os.path.exists(AUDIO_FILE):
                with open(AUDIO_FILE, 'rb') as f:
                    audio_data = f.read()
                    # start_time = time.time()
                    # print(f"发送音频中...{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                    transcript = await stt_client.audio.transcriptions.create(
                            model="large-v3", 
                            file=audio_data, 
                            language="zh",
                            response_format="text"
                        )
                    print(transcript,flush=True)
                    new_text = await generate(transcript)
                    text_queue.put(new_text)
                    # end_time = time.time()
                    # print(f"接收完成...{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
                    # print("耗时：", end_time - start_time, "秒", flush=True)

                os.remove(AUDIO_FILE)  # 发送成功后删除文件

            await asyncio.sleep(0.1)  # 等待下一次发送
    except KeyboardInterrupt:
        print("发送音频任务结束")

async def generate(text):
    sleep_time = 0.1
    await asyncio.sleep(sleep_time)
    return text

# 文本转语音
async def tts(text_queue):
    while True:
        if text_queue.empty():
            await asyncio.sleep(0.1)
            continue
        text = text_queue.get()
        speech_file_path = "D:\\Code\\speech.mp3"
        response = await tts_client.audio.speech.create(
            model="chattts-4w",
            input=text,
            voice="female2",
        )
        response.stream_to_file(speech_file_path)
        print("语音合成完成")

def stt_async_worker(audio_queue, text_queue):
    asyncio.run(send_audio(audio_queue, text_queue))

def tts_async_worker(text_queue):
    asyncio.run(tts(text_queue))

def start_processes():
    audio_queue = Queue()
    text_queue = Queue()
    record_process = Process(target=record_audio, args=(audio_queue,))
    stt_process = Process(target=stt_async_worker, args=(audio_queue, text_queue))
    tts_process = Process(target=tts_async_worker, args=(text_queue,))
    record_process.start()
    stt_process.start()
    tts_process.start()
    record_process.join()
    stt_process.join()
    tts_process.join()


if __name__ == "__main__":
    # asyncio.run(main())
    start_processes()
