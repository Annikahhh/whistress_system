# whistress_system
conda create -n whistress python=3.10
conda activate whistress
pip install -r requirements.txt
 1. 進入家目錄或其他工作資料夾
cd ~
mkdir -p myredis && cd myredis

 2. 下載 Redis 原始碼
wget http://download.redis.io/redis-stable.tar.gz
tar xzf redis-stable.tar.gz
cd redis-stable

 3. 編譯 Redis（會產生可執行檔，不需要 sudo）
make

 4. 測試一下
src/redis-server --version

 1. 下載並安裝 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

 2. 重新加載 shell 設定檔
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"

 3. 安裝最新 LTS 版本的 Node.js
nvm install --lts

 4. 使用剛剛安裝的版本（可選）
nvm use --lts

npm install

cd ~/myredis/redis-stable

src/redis-server

(new ternimal)
cd whistress_system

celery -A tasks worker --loglevel=info -P solo

============================================
(new terminal)
uvicorn main:app --reload

npm start

============================================
uvicorn main:app --host 0.0.0.0 --port 8000
