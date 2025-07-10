import redis
import json
import os
import uuid
from datetime import datetime

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

BATCH_QUEUE_KEY = "whistress:batch_queue"
RESULT_KEY_PREFIX = "whistress:result:"  # e.g. whistress:result:<id>

def add_request_to_queue(audio_bytes, prompt_text):
    task_id = str(uuid.uuid4())
    data = {
        "id": task_id,
        "audio_bytes": audio_bytes.hex(),  # binary → hex string
        "prompt_text": prompt_text,
        "timestamp": datetime.utcnow().isoformat()
    }
    r.rpush(BATCH_QUEUE_KEY, json.dumps(data))
    return task_id

def get_batch_requests(max_batch_size=8):
    items = []
    for _ in range(max_batch_size):
        item = r.lpop(BATCH_QUEUE_KEY)
        if item is None:
            break
        items.append(json.loads(item))
    return items

def store_result(task_id, result):
    r.setex(f"{RESULT_KEY_PREFIX}{task_id}", 300, json.dumps(result))  # 儲存 5 分鐘

def get_result(task_id):
    result = r.get(f"{RESULT_KEY_PREFIX}{task_id}")
    return json.loads(result) if result else None
