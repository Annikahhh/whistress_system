import io
import librosa
import torch
from celery import Celery
from whistress import WhiStressInferenceClient
import os
import json # 用於儲存複雜的結果到 Redis
from io import BytesIO
import soundfile as sf
from pydub import AudioSegment
import tempfile
from celery.schedules import timedelta # 用於 Celery Beat 的時間排程
import numpy as np # 用於處理 audio_array
import redis # 需要安裝 pip install redis
import base64
import time
import uuid
from celery.result import AsyncResult

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

# Celery 配置的更動
celery_app.conf.update(
    task_serializer='pickle', # 支持 bytes 數據傳輸
    accept_content=['json', 'pickle'],
    result_serializer='json', # 結果序列化為 JSON
    timezone='Asia/Taipei',
    enable_utc=True,
    worker_prefetch_multiplier=1, # 確保 Worker 不會預先抓取太多任務
    task_time_limit=3600, # 任務時間限制
    task_soft_time_limit=3000, # 軟時間限制

    # Celery Beat 配置，用於定期觸發批次處理任務
    beat_schedule={
        'process-pending-batch-every-5-seconds': {
            'task': 'tasks.process_pending_batch_task', # 指向新任務
            'schedule': timedelta(seconds=3), # 每 5 秒觸發一次
        },
    },
    # 這裡的 timezone 已經在上面的 update 包含了
    # timezone='Asia/Taipei', 
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

# --- Redis 客戶端用於共享批次佇列 ---
# 使用不同的 DB，以防與 Celery 的 broker/backend 衝突
redis_client = redis.StrictRedis(host='localhost', port=6379, db=1)
REDIS_BATCH_QUEUE_KEY = "whistress_inference_batch_queue"
BATCH_SIZE_THRESHOLD = 4 # 你希望的批次大小

# <--- 新增一個直接連接到 Celery backend (DB 0) 的 Redis 客戶端 ---
# 這將用於在 Celery Worker 內部直接驗證 DB 0 的寫入
redis_backend_test_conn = redis.StrictRedis(host='localhost', port=6379, db=0)
# -------------------------------------------------------------------

# --- 新增的測試任務 ---
# 這個任務僅用於測試 Fast API 的 Celery 後端讀取能力
@celery_app.task(name="test_fastapi_backend_read")
def test_fastapi_backend_read(value):
    return f"Test value received: {value}"
# ---------------------

# --- 定義 Celery 任務 ---
@celery_app.task(bind=True)
def analyze_stress_task(self, audio_bytes: bytes, prompt_text: str = None):
    #with open("debug_upload.webm", "wb") as f:
    #    f.write(audio_bytes)
    """
    Celery 任務：接收音頻二進制數據和引導文本，進行重音模式分析。
    """
    #1
    """try:
        # 測試能不能被 soundfile 正確打開
        audio_io = BytesIO(audio_bytes)
        info = sf.info(audio_io)  # ← 如果這裡報錯，代表格式錯誤
        print("Audio info:", info)
    except Exception as e:
        print("Error when reading audio:", e)
        raise e  # 讓 Celery 正常拋錯
    """
    #2
    '''
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

        pred_transcription, pred_stresses_indices = client.predict(
            audio=test_audio,
            transcription=prompt_text,
            return_pairs=False
        )
        pred_stresses = [i for i, x in enumerate(pred_stresses_indices) if x == 1]
        result = {
            "predicted_transcription": pred_transcription,
            "predicted_stresses": pred_stresses
        }

        return json.dumps(result)
    except Exception as e:
        print("Error during prediction:", e)
        raise e
    '''
    #3
    # --- 1. 修改 analyze_stress_task 為批次收集器 ---
    # 為了 JSON 序列化，將 bytes 轉換為 base64 字串
    # json 不直接支持 bytes 類型
    print("INFO: Attempting to base64 encode audio bytes...")
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    print("INFO: Successfully base64 encoded audio data.")
    new_id = str(uuid.uuid4())
    print(f"task_result_new_id-----------------{new_id}")
    task_data = {
        "audio_base64": audio_base64, # 儲存 base64 編碼的音頻數據
        "prompt_text": prompt_text,
        "original_task_id": new_id#self.request.id # 保存原始任務的 ID
    }
    
    # 將任務數據推送到 Redis 列表的左側 (作為 FIFO 佇列)
    redis_client.lpush(REDIS_BATCH_QUEUE_KEY, json.dumps(task_data))
    
    print(f"Task {self.request.id} added to Redis batch queue. Current queue length: {redis_client.llen(REDIS_BATCH_QUEUE_KEY)}")
    print(";;;;;;;;;;;;;;;;;;;;;;;;;")
    # --- 在 analyze_stress_task 內部直接向 DB 0 寫入一個測試鍵 ---
    test_key = f"worker-test-write-{self.request.id}"
    test_value = "Worker successfully wrote to DB0"
    redis_backend_test_conn.set(test_key, test_value)
    print(f"DEBUG: Worker: 已嘗試寫入測試鍵 '{test_key}' 到 DB 0。")
    # ----------------------------------------------------------------
    # 立即返回，告訴客戶端任務已提交到批次隊列
    '''self.update_state(
        state='YessssssssSUBMITTED_TO_BATCH',
        meta={'message': 'Task submitted to batch queue for processing.'}
    )'''
    return {"status": "NOOOOOOSUBMITTED_TO_BATCH", "batch_task_id": new_id , "message": "Task submitted to batch queue for processing."}

# --- 2. 新增批次處理任務 ---
@celery_app.task(bind=True)    
def process_pending_batch_task(self):
    print("in batch@@@@@@@@@@@")
    """
    Celery Beat 定期觸發的任務：從 Redis 佇列中取出待處理的任務，執行批次推論。
    """
    # 獲取推理客戶端 (確保模型只在需要時載入一次)
    client = get_whistress_client()

    items_to_process = []
    
    # 原子性地從 Redis 佇列中取出多個元素
    # 我們嘗試取出 BATCH_SIZE_THRESHOLD 數量或佇列中所有元素
    # rpop 命令從列表的右側彈出元素 (LIFO)，lpush 是從左側推入。
    # 如果你想要 FIFO (先進先出)，lpush 和 rpop 組合是正確的。
    # 如果你想要 LIFO (後進先出)，lpush 和 lpop 組合。
    # 這裡我們用 lpush 和 rpop，實現 FIFO。

    # 使用 Pipeline 實現原子性地批量拉取
    pipe = redis_client.pipeline()
    for _ in range(BATCH_SIZE_THRESHOLD):
        pipe.rpop(REDIS_BATCH_QUEUE_KEY)
    results = pipe.execute()
    print("before process@@@@@@@@@@@")
    for item_json in results:
        if item_json is None:
            continue # 佇列已空或未達批次大小
        items_to_process.append(json.loads(item_json))

    if not items_to_process:
        print("No pending tasks in batch queue to process.")
        return

    print(f"Processing batch of {len(items_to_process)} items.")

    audio_dicts_for_model = []
    prompt_texts_for_model = []
    original_task_ids = []

    for item in items_to_process:
        original_task_ids.append(item["original_task_id"])
        prompt_texts_for_model.append(item["prompt_text"])
        
        # 解碼 base64 字串回 bytes
        import base64
        audio_bytes = base64.b64decode(item["audio_base64"])

        # 音頻轉換邏輯 (從 analyze_stress_task 搬過來)
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_in:
                temp_in.write(audio_bytes)
                temp_in.flush()

                audio = AudioSegment.from_file(temp_in.name, format="webm")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_out:
                    audio.export(temp_out.name, format="wav")
                    audio_array, sampling_rate = librosa.load(temp_out.name, sr=None)
            
            # 清理臨時文件
            os.unlink(temp_in.name)
            os.unlink(temp_out.name)

            audio_dicts_for_model.append({
                "array": audio_array,
                "sampling_rate": sampling_rate
            })
        except Exception as e:
            # 如果單個音頻轉換失敗，標記該原始任務為失敗，並繼續處理批次中的其他任務
            error_message = f"Audio conversion failed for task {item['original_task_id']}: {e}"
            print(error_message)
            celery_app.backend.mark_as_failure(item['original_task_id'], error_message)
            # 將該任務從批次中移除，避免傳遞給模型
            # 這裡需要一個更複雜的數據結構來處理失敗的單個任務
            # 為了簡化，我們直接跳過，但這會導致 audio_dicts_for_model 和 original_task_ids 長度不匹配
            # 更好的方法是使用一個列表來保存結果狀態，然後在最後統一處理
            # 這裡我們假設所有音頻轉換都會成功，否則需要更嚴謹的錯誤處理。
            # 簡化處理：如果轉換失敗，則不加入批次推論，並將其結果標記為失敗。
            # 然後在批次推論成功後，只更新成功的任務。
            pass # 這裡只是演示，實際生產應更嚴謹

    # 確保只有成功轉換的音頻才參與批次推論
    if not audio_dicts_for_model:
        print("No valid audio to process in this batch after conversion.")
        return

    # 過濾掉那些音頻轉換失敗的 prompt_text 和 original_task_ids
    # 這裡的邏輯需要與 audio_dicts_for_model 的生成保持一致
    # 為了簡化，我們假設所有音頻都會成功轉換，並且 prompt_texts_for_model 和 original_task_ids
    # 的長度與 audio_dicts_for_model 相同。
    
    try:
        # 調用客戶端的批次推論方法
        batch_processed_results = client.predict_batch(
            audio_list=audio_dicts_for_model, 
            transcription_list=prompt_texts_for_model,
            return_pairs=False # 這裡讓它返回格式化的結果，方便直接儲存
        )

        # 將每個原始任務的結果寫回 Celery 後端
        for i, result in enumerate(batch_processed_results):
            original_task_id = original_task_ids[i] # 這裡需要確保索引正確對應
            # result 已經是 (pred_transcription, pred_stresses_indices)
            # 我們需要轉換回你期望的 JSON 格式
            formatted_result = {
                "predicted_transcription": result[0],
                "predicted_stresses": [idx for idx, val in enumerate(result[1]) if val == 1]
            }
            print(f"DEBUG: 準備寫入 Redis 的最終結果: {formatted_result}")
            print(f"新ID: {original_task_id}")
            #celery_app.backend.mark_as_done(original_task_id, json.dumps(formatted_result))
            celery_app.backend.store_result(original_task_id, json.dumps(formatted_result), state='SUCCESS')
            #celery_app.backend.store_result(original_task_id, formatted_result,  state='SUCCESS')
            #redis_client.set(f"stress_result:{original_task_id}", json.dumps(formatted_result))
            #time.sleep(5)
                          # 任務 ID
                        # 結果（這裡直接傳 dict，不用 json.dumps）
                         # 狀態設為成功
            #----------------------
            checked_task_result = AsyncResult(original_task_id, app=celery_app)
            
            print(f"~~~DEBUG: WORKER SELF-CHECK: 任務 {original_task_id} - 狀態: {checked_task_result.state}")
            print(f"DEBUG: WORKER SELF-CHECK: 任務 {original_task_id} - 結果: {checked_task_result.result}")
            print(f"DEBUG: WORKER SELF-CHECK: 任務 {original_task_id} - 結果類型: {type(checked_task_result.result)}")
            #-------------------------------
            print(f"Marked original task {original_task_id} as COMPLETED with result.")

    except Exception as e:
        error_message = f"Batch analysis failed: {e}"
        print(f"Error in batch processing task: {error_message}")
        # 標記批次中所有仍在 PENDING 狀態的原始任務為失敗
        # 這裡需要一個更可靠的方式來處理，確保不會覆蓋已經成功的任務狀態
        for original_task_id in original_task_ids:
            # 僅更新那些尚未被標記為成功的任務
            current_status = celery_app.backend.get_status(original_task_id)
            if current_status not in ["SUCCESS", "FAILURE"]: # 避免重複標記
                celery_app.backend.mark_as_failure(original_task_id, error_message)
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # 不要重新拋出異常，讓 Beat 任務可以繼續運行
        return {"status": "BATCH_PROCESSING_FAILED", "message": error_message} # 在異常情況下返回失敗訊息
    return #formatted_result#{"status": "BATCH_PROCESSING_COMPLETED", "message": "All items in batch processed."} 