# WhiStress Speech Stress Analysis System

This project is an implementation of the [WhiStress model](https://github.com/slp-rl/WhiStress), providing a complete pipeline for speech stress prediction. It includes:

- User-uploaded audio processing  
- Stress prediction using the WhiStress model  
- A FastAPI backend providing an HTTP API  
- A React-based frontend interface  
- Redis + Celery for task queue management

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Annikahhh/whistress_system.git
cd whistress_system
```

### 2. Set Up the Python Environment

Make sure you are using Python 3.10, then install the required packages:

```bash
pip install -r requirements.txt
```

### 3. Install Redis

Download and compile Redis:

```bash
# Navigate to a directory where you want to install Redis
wget http://download.redis.io/redis-stable.tar.gz
tar xzf redis-stable.tar.gz
cd redis-stable
make
```

### 4. Install Node.js and npm (for the Frontend)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

nvm install --lts
nvm use --lts
npm install

```

---

## Download WhiStress Model Weights

```bash
python backend/whistress/download_weights.py
```

After downloading, the expected project structure is:

```
whistress_system/
├── backend/
│   ├── whistress/
│   │   ├── weights/
│   │   ├── model.py
│   │   └── inference_client.py
│   ├── main.py
│   ├── tasks.py
│   ├── requirements.txt
│   └── download_weights.py
├── frontend/
│   ├── public/
│   ├── src/
│   └── package.json
└── README.md
```

---

## Usage

You can simply run:

```bash
make start
````

This command launches all major components of the system, including Redis, Celery Beat, Celery Worker, the FastAPI backend, and the React frontend.

### Individual Commands (Optional)

You can also start each component manually using either `make` or the equivalent shell command:


### 1. Start Redis (Keep Running)

```bash
make redis
```

or manually:

```bash
cd ~/myredis/redis-stable
src/redis-server
```


### 2. Start Celery Beat and Worker (Keep Running)

```bash
make celery-beat
make celery-worker
```

or manually:

```bash
cd whistress_system/backend
celery -A tasks beat --loglevel=info
celery -A tasks worker --loglevel=info --pool=threads
```


### 3. Start FastAPI Server

```bash
make api
```

or manually:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```


### 4. Start Frontend

```bash
make frontend
```

or manually:

```bash
cd frontend
npm start
```

### Stopping All Services

To stop all running services started via `make`, use:

```bash
make stop
```

This will attempt to kill Redis, Celery, FastAPI, and React processes using `pkill`.

---


- Web interface available at: [http://localhost:3000](http://localhost:3000)  
- API documentation available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## License

This project is licensed under the [MIT License](https://choosealicense.com/licenses/mit/).

---

## Citation

Original paper:

```bibtex
@misc{yosha2025whistress,
    title={WHISTRESS: Enriching Transcriptions with Sentence Stress Detection}, 
    author={Iddo Yosha and Dorin Shteyman and Yossi Adi},
    year={2025},
    eprint={2505.19103},
    archivePrefix={arXiv},
    primaryClass={cs.CL},
    url={https://arxiv.org/abs/2505.19103}, 
}
```