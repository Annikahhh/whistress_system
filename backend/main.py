import io
import librosa
import torch
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from celery.result import AsyncResult # 用於查詢 Celery 任務狀態
from tasks import analyze_stress_task, celery_app # 從 tasks.py 導入 Celery 應用和任務
import json
from fastapi.middleware.cors import CORSMiddleware

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

# --- 1. 定義非同步 API 接口 ---
@app.post("/analyze_stress_async")
async def analyze_stress_async(audio_file: UploadFile = File(...), prompt_text: str = Form(None)):
    """
    接收音頻檔案和引導文本，將重音模式分析任務發送到 Celery 佇列。
    立即返回任務 ID。
    """
    # 驗證音頻文件類型 (可選，但推薦)
    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

    try:
        audio_bytes = await audio_file.read()
        with open("debug_uploaded_audio.wav", "wb") as f:
            f.write(audio_bytes)

        # 將任務發送到 Celery 佇列
        # audio_bytes 直接作為參數傳遞
        task = analyze_stress_task.delay(audio_bytes, prompt_text)
        
        # 立即返回任務 ID
        return JSONResponse(content={
            "success": True,
            "message": "Analysis task submitted successfully.",
            "task_id": task.id
        })

    except Exception as e:
        print(f"Error submitting analysis task: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

# --- 2. 定義查詢任務狀態和結果的 API 接口 ---
@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    根據任務 ID 查詢 Celery 任務的狀態和結果。
    """
    task_result = AsyncResult(task_id, app=celery_app) # 使用導入的 celery_app

    if task_result.ready(): # 任務已完成 (SUCCESS 或 FAILURE)
        if task_result.successful():
            result_data = json.loads(task_result.result) # 解析 JSON 字串
            return JSONResponse(content={
                "status": "COMPLETED",
                "result": result_data
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

# 注意：這裡去除了 on_event("startup") 的模型載入，因為模型現在由 Celery Worker 載入
# 如果你的 FastAPI 應用還有其他需要模型的功能，你可能需要重新評估模型載入策略
# 但對於這個 POC，模型推論現在專門由 Celery Worker 負責。