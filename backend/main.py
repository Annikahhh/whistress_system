from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from celery.result import AsyncResult # 用於查詢 Celery 任務狀態
from tasks import analyze_stress_task, celery_app, test_fastapi_backend_read  # 從 tasks.py 導入 Celery 應用和任務
import json
from fastapi.middleware.cors import CORSMiddleware
import traceback
import time
import redis
# --- FastAPI 應用初始化 ---
app = FastAPI(
    title="WhiStress POC Backend",
    description="Backend for stress pattern analysis using WhiStress model."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可改成限定來源如 ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
'''
# --- 新增的測試任務 ---
# 這個任務僅用於測試 Fast API 的 Celery 後端讀取能力
@celery_app.task(name="test_fastapi_backend_read")
def test_fastapi_backend_read(value):
    return f"Test value received: {value}"
# ---------------------


@app.on_event("startup")
async def startup_event():
    print("FastAPI 應用程式啟動中...")
    # 啟動時發送一個 Celery 測試任務，並嘗試讀取其結果
    try:
        test_task = test_fastapi_backend_read.delay("hello_celery")
        print(f"DEBUG: 發送測試任務: {test_task.id}")
        
        # 等待一小段時間，讓 Worker 有機會處理這個測試任務
        # 實際應用中不建議在啟動時長時間阻塞，這裡僅為測試目的
        time.sleep(2) 
        
        # 嘗試從後端獲取測試任務的結果
        test_result = AsyncResult(test_task.id, app=celery_app)
        print(f"DEBUG: 測試任務狀態: {test_result.state}")
        print(f"DEBUG: 測試任務結果: {test_result.result}")
        print(f"DEBUG: 測試任務結果類型: {type(test_result.result)}")

        if test_result.successful() and test_result.result == "Test value received: hello_celery":
            print("DEBUG: Celery 後端連接與讀取測試成功！")
        else:
            print("DEBUG: Celery 後端連接或讀取測試失敗！請檢查 Redis 連線和 Celery 配置。")
            print(f"DEBUG: 預期結果: 'Test value received: hello_celery', 實際結果: {test_result.result}")
    except Exception as e:
        print(f"DEBUG: 啟動時執行 Celery 測試任務時發生錯誤: {e}")

# ... (其餘的 /tasks/{task_id} 端點程式碼不變)
# ... (您的其他 FastAPI 端點)
'''
@app.on_event("startup")
async def startup_event():
    print("FastAPI 應用程式啟動中...")
    try:
        # 現在呼叫的是 tasks.py 中定義的測試任務
        test_task = test_fastapi_backend_read.delay("hello_celery") 
        print(f"DEBUG: 發送測試任務: {test_task.id}")
        
        # 給 Worker 一點時間處理
        time.sleep(2) 
        
        test_result = AsyncResult(test_task.id, app=celery_app)
        print(f"DEBUG: 測試任務狀態: {test_result.state}")
        print(f"DEBUG: 測試任務結果: {test_result.result}")
        print(f"DEBUG: 測試任務結果類型: {type(test_result.result)}")

        if test_result.successful() and test_result.result == "Test value received: hello_celery":
            print("DEBUG: Celery 後端連接與讀取測試成功！")
        else:
            print("DEBUG: Celery 後端連接或讀取測試失敗！請檢查 Redis 連線和 Celery 配置。")
            print(f"DEBUG: 預期結果: 'Test value received: hello_celery', 實際結果: {test_result.result}")
    except Exception as e:
        print(f"DEBUG: 啟動時執行 Celery 測試任務時發生錯誤: {e}")

# --- 1. 定義非同步 API 接口 ---
@app.post("/analyze_stress_async")
async def analyze_stress_async(audio_file: UploadFile = File(...), prompt_text: str = Form(None)):
    """
    接收音頻檔案和引導文本，將重音模式分析任務發送到 Celery 佇列。
    立即返回任務 ID。
    """
    print(f"INFO: Received request for analyze_stress_async with prompt: {prompt_text}")
    print(f"INFO: Audio file name: {audio_file.filename}, content type: {audio_file.content_type}")

    # 驗證音頻文件類型 (可選，但推薦)
    if not audio_file.content_type.startswith("audio/"):
        print(f"ERROR: Invalid file type received: {audio_file.content_type}")
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    try:
        print("INFO: Attempting to read audio file bytes...")
        audio_bytes = await audio_file.read()
        #with open("debug_uploaded_audio.wav", "wb") as f:
        #    f.write(audio_bytes)
        #print("INFO: Attempting to base64 encode audio bytes...")
        #audio_base64_data = base64.b64encode(audio_bytes).decode('utf-8')
        #print("INFO: Successfully base64 encoded audio data.")

        # 將任務發送到 Celery 佇列
        # audio_bytes 直接作為參數傳遞
        print("INFO: Attempting to submit task to Celery...")
        task = analyze_stress_task.delay(audio_bytes, prompt_text)
        print(";;;;;;;;;;;;;;;;;;;;;;;;;")
        print(f"INFO: Task submitted to Celery. Task ID: {task.id}")
        # 立即返回任務 ID
        return JSONResponse(content={
            "success": True,
            "message": "Analysis task submitted successfully.",
            "task_id": task.id
        })

    except Exception as e:
        print(f"Error submitting analysis task: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# --- 2. 定義查詢任務狀態和結果的 API 接口 ---
@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    根據任務 ID 查詢 Celery 任務的狀態和結果。
    """
    print("]]]]]]]]]]]]]]]]]]]]]]]]")
    #task_result = AsyncResult(task_id, app=celery_app) # 使用導入的 celery_app
    # *** 新增：強制刷新 AsyncResult 的內部狀態 ***
    # 嘗試讓 AsyncResult 重新從後端獲取最新狀態
    # 這是透過觸發其內部方法來實現的，確保資料是最新狀態
    #task_result.forget() # 讓 Celery 忘記這個任務的本地快取，以便下次查詢時重新獲取
    # 重新創建 AsyncResult 實例，因為 forget() 會影響當前實例的內部狀態
    #task_result = redis_client.get(f"stress_result:{task_id}")#AsyncResult(task_id, app=celery_app)
    task_result = celery_app.backend.get_task_meta(task_id)

    current_redis_backend_conn = redis.StrictRedis(host='localhost', port=6379, db=1)
    # get_task_meta 返回的是一個字典，其中包含 'status' 和 'result'
    current_status = task_result.get('status', 'PENDING')
    current_result = task_result.get('result')

    redis_key_main_task = f"celery-task-meta-{task_id}"
    raw_redis_data_main_task = current_redis_backend_conn.get(redis_key_main_task)
    print(f"DEBUG: Redis Key (主任務): {redis_key_main_task}")
    print(f"DEBUG: 原始 Redis 數據 (主任務): {raw_redis_data_main_task}")
    if raw_redis_data_main_task:
        try:
            parsed_redis_data_main = json.loads(raw_redis_data_main_task)
            print(f"DEBUG: 解析後的 Redis 數據 (主任務): {parsed_redis_data_main}")
        except json.JSONDecodeError:
            print(f"DEBUG: 無法解析 Redis 數據 (主任務): {raw_redis_data_main_task}")

    print(f"\n--- 查詢任務 {task_id} ---")
    print(f"DEBUG: 原始狀態: {current_status}") # 使用從 get_task_meta 獲取到的狀態
    print(f"DEBUG: 原始結果: {current_result}") # 使用從 get_task_meta 獲取到的結果
    print(f"DEBUG: 原始結果類型: {type(current_result)}")
    # 以下邏輯保持不變，但現在使用 current_status 和 current_result
    if current_status in ["SUCCESS", "FAILURE"]: # 任務已完成或失敗
        if current_status == "SUCCESS":
            result_data = None
            if isinstance(current_result, str):
                try:
                    result_data = json.loads(current_result)
                    print(f"DEBUG: 解析字串結果為字典: {result_data}")
                except json.JSONDecodeError:
                    result_data = current_result
                    print(f"DEBUG: 結果是無法解析的字串: {result_data}")
            elif isinstance(current_result, dict):
                result_data = current_result
                print(f"DEBUG: 結果直接是字典: {result_data}")
            else:
                result_data = str(current_result)
                print(f"DEBUG: 結果是其他類型 (轉字串): {result_data}")

            if isinstance(result_data, dict):
                print(f"DEBUG: 判斷 result_data['status']: {result_data.get('status')}")
            else:
                print(f"DEBUG: result_data 不是字典，無法檢查 'status' 鍵。")

            if isinstance(result_data, dict) and result_data.get("status") == "SUBMITTED_TO_BATCH":
                print(f"DEBUG: 返回 PENDING_BATCH_PROCESSING")
                return JSONResponse(content={
                    "status": "PENDING_BATCH_PROCESSING",
                    "message": result_data.get("message", "Task is waiting in batch queue."),
                    "task_id": task_id
                })
            else:
                print(f"DEBUG: 返回 COMPLETED")
                return JSONResponse(content={
                    "status": "COMPLETED",
                    "result": result_data
                })
        else: # current_status == "FAILURE"
            print(f"DEBUG: 任務 {task_id} 失敗: {current_result}")
            return JSONResponse(content={
                "status": "FAILED",
                "error": str(current_result)
            }, status_code=500)
    else: # 任務仍在進行中
        print(f"DEBUG: 任務 {task_id} 仍在進行中 (狀態: {current_status})")
        return JSONResponse(content={
            "status": current_status,
            "task_id": task_id
        })
    '''
    print(f"\n--- 查詢任務 {task_id} ---")
    print(f"DEBUG: 原始狀態: {task_result.state}")
    print(f"DEBUG: 原始結果: {task_result.result}")
    print(f"DEBUG: 原始結果類型: {type(task_result.result)}") # 打印類型很重要！
    if task_result.ready(): # 任務已完成 (SUCCESS 或 FAILURE)
        if task_result.successful():
            print("yyyyyyyyyyyyyyyyyyyyy")
            ''''''
            result_data = json.loads(task_result.result) # 解析 JSON 字串
            return JSONResponse(content={
                "status": "COMPLETED",
                "result": result_data
            })
            ''''''
            if isinstance(task_result.result, str):
                try:
                    result_data = json.loads(task_result.result) # 嘗試解析 JSON 字串
                except json.JSONDecodeError:
                    # 如果不是有效的 JSON 字串，可能是其他格式的字串，直接作為結果
                    result_data = task_result.result 
            elif isinstance(task_result.result, dict):
                # 如果是字典，直接使用它
                result_data = task_result.result
            else:
                # 處理其他意外類型，例如 None 或其他
                result_data = str(task_result.result) # 將其轉為字串以避免進一步錯誤
            print(f"88888888{result_data.get('status')}")
            # 根據 result_data 的內容來判斷是提交成功還是最終結果
            if result_data.get("status") == "SUBMITTED_TO_BATCH":
                return JSONResponse(content={
                    "status": "PENDING_BATCH_PROCESSING", # 新的狀態名稱
                    "message": result_data.get("message", "Task is waiting in batch queue."),
                    "task_id": task_id
                })
            else:
                # 這是最終的成功結果
                return JSONResponse(content={
                    "status": "COMPLETED",
                    "result": result_data # 這裡直接使用已經處理好的字典或字串
                })
        else:
            # 任務失敗
            return JSONResponse(content={
                "status": "FAILED",
                "error": str(task_result.info) # 獲取錯誤信息
            }, status_code=500)
    else:
        # 任務仍在進行中
        return JSONResponse(content={
            "status": task_result.state # PENDING, STARTED, RETRY 等
        })
'''
# 注意：這裡去除了 on_event("startup") 的模型載入，因為模型現在由 Celery Worker 載入
# 如果你的 FastAPI 應用還有其他需要模型的功能，你可能需要重新評估模型載入策略
# 但對於這個 POC，模型推論現在專門由 Celery Worker 負責。