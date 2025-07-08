import io
import librosa
import torch
from celery import Celery
from whistress import WhiStressInferenceClient
import os
import json # 用於儲存複雜的結果到 Redis
import traceback
from io import BytesIO
import soundfile as sf
import logging
from pydub import AudioSegment
import tempfile
#import multiprocessing

#multiprocessing.set_start_method('spawn', force=True)
# --- Celery 配置 ---
# BROKER_URL 指向你的 Redis 服務
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
# RESULT_BACKEND 用於儲存任務結果，也指向 Redis
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    'whistress_tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# --- 模型載入 (在 Celery Worker 啟動時載入) ---
# 這裡確保模型在每個 Worker 進程中載入一次
whistress_client: WhiStressInferenceClient = None
def get_whistress_client():
    global whistress_client
    if whistress_client is None:
        print("Loading WhiStress model for Celery Worker...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        whistress_client = WhiStressInferenceClient(device=device)
        print(f"WhiStress model loaded successfully on {device} for Celery Worker.")
    return whistress_client

# --- 定義 Celery 任務 ---
@celery_app.task(bind=True)
def analyze_stress_task(self, audio_bytes: bytes, prompt_text: str = None):
    #with open("debug_upload.webm", "wb") as f:
    #    f.write(audio_bytes)
    """
    Celery 任務：接收音頻二進制數據和引導文本，進行重音模式分析。
    """
    """try:
        # 測試能不能被 soundfile 正確打開
        audio_io = BytesIO(audio_bytes)
        info = sf.info(audio_io)  # ← 如果這裡報錯，代表格式錯誤
        print("Audio info:", info)
    except Exception as e:
        print("Error when reading audio:", e)
        raise e  # 讓 Celery 正常拋錯

    try:
        client = get_whistress_client() # 獲取模型實例

        audio_io = io.BytesIO(audio_bytes)
        audio_array, sampling_rate = librosa.load(audio_io, sr=None)

        test_audio = {
            "array": audio_array,
            "sampling_rate": sampling_rate
        }

        # 執行模型推論
        pred_transcription, pred_stresses = client.predict(
            audio=test_audio,
            transcription=prompt_text, # 如果有 prompt_text，可以傳遞給模型
            return_pairs=False
        )

        result = {
            "predicted_transcription": pred_transcription,
            "predicted_stresses": pred_stresses
        }

        # 將結果儲存到 Celery 的結果後端 (Redis)
        return json.dumps(result) # Celery 結果 backend 最好儲存 JSON 字串或基本類型

    except Exception as e:
        # 任務失敗時，設置任務狀態為失敗
        self.update_state(state='FAILURE', meta={'exc': repr(e), 'traceback': traceback.format_exc()})
        #print(f"Task error: {e}")
        raise # 重新拋出異常讓 Celery 標記任務失敗
    """
    try:
        # 儲存為 temp .webm 檔
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_in:
            temp_in.write(audio_bytes)
            temp_in.flush()

            # 轉為 wav
            audio = AudioSegment.from_file(temp_in.name, format="webm")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_out:
                audio.export(temp_out.name, format="wav")

                # 用 librosa 讀取
                audio_array, sampling_rate = librosa.load(temp_out.name, sr=None)

    except Exception as e:
        print("Error converting/reading audio:", e)
        raise e

    try:
        client = get_whistress_client()
        test_audio = {
            "array": audio_array,
            "sampling_rate": sampling_rate
        }

        pred_transcription, pred_stresses = client.predict(
            audio=test_audio,
            transcription=prompt_text,
            return_pairs=False
        )

        result = {
            "predicted_transcription": pred_transcription,
            "predicted_stresses": pred_stresses
        }

        return json.dumps(result)
    except Exception as e:
        print("Error during prediction:", e)
        raise e
    