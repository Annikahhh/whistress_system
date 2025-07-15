import React, { useState, useRef } from "react";

const sentences = [
  { text: "I want to eat an apple", stresses: [0, 5] },
  { text: "She likes to play the piano", stresses: [1, 5] },
  { text: "Today is a beautiful sunny day", stresses: [0, 4] },
  { text: "Can you help me with this task", stresses: [1, 5] },
  { text: "He is reading a good book", stresses: [0, 5] },
  { text: "We will meet at the coffee shop", stresses: [2, 6] },
  { text: "They are watching a new movie", stresses: [1, 5] },
  { text: "The weather forecast says it will rain", stresses: [0, 7] },
  { text: "I bought some fresh vegetables today", stresses: [0, 6] },
  { text: "Please open the window for some air", stresses: [1, 6] },
];

// 模擬使用者重音結果 (隨機產生正確或錯誤)
/*function mockUserStress(correctStresses, wordCount) {
  return Array.from({ length: wordCount }, (_, i) => {
    if (correctStresses.includes(i)) {
      return Math.random() < 0.8 ? i : -1;
    } else {
      return Math.random() < 0.2 ? i : -1;
    }
  }).filter(i => i !== -1);
}*/

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [recording, setRecording] = useState(false);
  const [audioURL, setAudioURL] = useState(null);
  const [userStressIndices, setUserStressIndices] = useState([]);
  const [showResult, setShowResult] = useState(false);
  const [finished, setFinished] = useState(false); // 新增：是否結束全部題目

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  // 當全部題目答完時顯示結束畫面000
  if (finished) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#e3f2fd",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
          padding: 20,
        }}
      >
        <h1 style={{ color: "#1565c0", marginBottom: 20 }}>🎉 恭喜完成所有題目！</h1>
        <button
          onClick={() => {
            setCurrentIndex(0);
            setUserStressIndices([]);
            setAudioURL(null);
            setShowResult(false);
            setFinished(false);
          }}
          style={{
            padding: "12px 30px",
            fontSize: 18,
            borderRadius: 10,
            border: "none",
            backgroundColor: "#1976d2",
            color: "white",
            cursor: "pointer",
          }}
        >
          再玩一次
        </button>
      </div>
    );
  }

  const currentSentence = sentences[currentIndex];
  const words = currentSentence.text.split(" ");

  const startRecording = () => {
    setRecording(true);
    chunksRef.current = [];
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();

      mediaRecorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        setAudioURL(url);
      };
    });
  };

  const stopRecording = () => {
    setRecording(false);
    mediaRecorderRef.current.stop();
  };
  
  /*const sendAudio = () => {
    // 模擬分析
    const userStress = mockUserStress(currentSentence.stresses, words.length);
    setUserStressIndices(userStress);
    setShowResult(true);
  };*/
  const sendAudio = async () => {
    if (!chunksRef.current.length) return;
    const blob = new Blob(chunksRef.current, { type: "audio/wav" });
    const formData = new FormData();
    formData.append("audio_file", blob, "recording.wav");
    formData.append("prompt_text", currentSentence.text);

    try {
      const response = await fetch("http://localhost:8000/analyze_stress_async", {
        //http://140.122.184.162:8000/analyze_stress_async
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      if (data.success) {
        const taskId = data.task_id;
        pollTaskResult(taskId); // 啟動輪詢等待結果
      } else {
        alert("分析任務提交失敗");
      }
    } catch (err) {
      console.error("Error uploading audio:", err);
      alert("上傳錯誤");
    }
  };
/*
  const pollTaskResult = async (taskId) => {
    const interval = setInterval(async () => {
      const res = await fetch(`http://localhost:8000/tasks/${taskId}`);
      //http://140.122.184.162:8000/tasks/${taskId}
      const data = await res.json();

      if (data.status === "COMPLETED") {
        clearInterval(interval);
        const { predicted_stresses } = data.result;
        setUserStressIndices(predicted_stresses);
        setShowResult(true);
      } else if (data.status === "FAILED") {
        clearInterval(interval);
        alert("任務執行失敗：" + data.error);
      }
      // 否則繼續等待
    }, 1000);
  };
*/
  // App.js (請替換您的 pollTaskResult 函數)
  const pollTaskResult = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/tasks/${taskId}`);
        const data = await res.json();
        console.log(`Polling task ${taskId} status:`, data.status, "Result:", data.result); // 添加日誌來觀察

        if (data.status === "COMPLETED") { // <--- 這裡判斷的是模型分析完成的最終狀態
          console.log("任務已完成！收到的完整數據:", data); // <-- 重要！查看整個 data 物件
          console.log("任務已完成！結果部分:", data.result);
          /*clearInterval(interval);
          const { predicted_stresses } = data.result;
          setUserStressIndices(predicted_stresses);
          setShowResult(true);*/
          if (data.result.batch_task_id) {
            // 是個中繼轉交任務，這是你說的「新的 ID」
            const newTaskId = data.result.batch_task_id;
            console.log("轉交新的 task id:", newTaskId);
            clearInterval(interval);
            // 再用新的 ID 開一個 polling
            pollTaskResult(newTaskId);
          } else if (data.result.predicted_transcription) {
            const predicted_stresses = data.result.predicted_stresses;
            setUserStressIndices(predicted_stresses);
            setShowResult(true);
            clearInterval(interval);
          } else {
            console.log("COMPLETED，但結果格式不明：", data.result);
            clearInterval(interval);
          }
        } else if (data.status === "FAILED") {
          clearInterval(interval);
          alert("任務執行失敗：" + data.error);
          // 清理狀態，允許再次上傳
          setAudioURL(null);
          setRecording(false);
          } else if (data.status === "PENDING" || data.status === "SUBMITTED_TO_BATCH") {
            // 如果任務還在待處理或已提交到批次佇列，繼續等待
            // 這部分是 Celery 任務 analyze_stress_task 的直接結果
            // 而 process_pending_batch_task 處理後會更新原始任務的狀態
            console.log("Task still pending or submitted to batch, waiting for COMPLETED...");
        }
      } catch (err) {
        clearInterval(interval);
        console.error(`Error polling task ${taskId}:`, err);
        alert("查詢任務結果失敗：" + err.message);
        // 清理狀態，允許再次上傳
        setAudioURL(null);
        setRecording(false);
      }
    }, 1000); // 每秒查詢一次
  };


  const nextQuestion = () => {
    if (currentIndex + 1 >= sentences.length) {
      setFinished(true); // 完成所有題目
    } else {
      setCurrentIndex(idx => idx + 1);
      setAudioURL(null);
      setUserStressIndices([]);
      setShowResult(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#e3f2fd",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: 20,
        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        flexDirection: "column",
      }}
    >
      <h2 style={{ marginBottom: 20, color: "#1565c0" }}>
        朗讀重音分析示範（第 {currentIndex + 1} 題 / {sentences.length} 題）
      </h2>

      <div
        style={{
          backgroundColor: "white",
          borderRadius: 12,
          padding: 20,
          boxShadow: "0 4px 8px rgba(0,0,0,0.1)",
          maxWidth: 480,
          width: "100%",
          textAlign: "center",
        }}
      >
        <h3 style={{ marginBottom: 12, color: "#0d47a1" }}>請朗讀句子：</h3>
        <p
          style={{
            backgroundColor: "#bbdefb",
            padding: "10px 15px",
            borderRadius: 8,
            fontSize: 20,
            fontWeight: "500",
            userSelect: "none",
            marginBottom: 20,
          }}
        >
          {words.map((w, i) => {
            const isCorrectStress = currentSentence.stresses.includes(i);
            return (
              <span
                key={i}
                style={{
                  textDecoration: isCorrectStress ? "underline" : "none",
                  fontWeight: isCorrectStress ? "bold" : "normal",
                  marginRight: 6,
                }}
              >
                {w}
              </span>
            );
          })}
        </p>

        <div style={{ marginBottom: 12 }}>
          {!recording ? (
            <button
              onClick={startRecording}
              style={{
                padding: "8px 20px",
                fontSize: 16,
                borderRadius: 8,
                border: "none",
                backgroundColor: "#1976d2",
                color: "white",
                cursor: "pointer",
                marginRight: 12,
              }}
            >
              開始錄音
            </button>
          ) : (
            <button
              onClick={stopRecording}
              style={{
                padding: "8px 20px",
                fontSize: 16,
                borderRadius: 8,
                border: "none",
                backgroundColor: "#d32f2f",
                color: "white",
                cursor: "pointer",
                marginRight: 12,
              }}
            >
              停止錄音
            </button>
          )}

          <button
            onClick={sendAudio}
            disabled={!audioURL}
            style={{
              padding: "8px 20px",
              fontSize: 16,
              borderRadius: 8,
              border: "none",
              backgroundColor: audioURL ? "#388e3c" : "#9e9e9e",
              color: "white",
              cursor: audioURL ? "pointer" : "not-allowed",
            }}
          >
            送出錄音分析重音（模擬）
          </button>
        </div>

        {audioURL && (
          <div style={{ marginBottom: 20 }}>
            <audio src={audioURL} controls />
          </div>
        )}

        {showResult && (
          <div
            style={{
              backgroundColor: "#e8f5e9",
              padding: 15,
              borderRadius: 8,
              userSelect: "none",
            }}
          >
            <h4 style={{ color: "#2e7d32", marginBottom: 10 }}>
              你的重音分析結果：
            </h4>
            <p style={{ fontSize: 18 }}>
              {words.map((w, i) => {
                const userHasStress = userStressIndices.includes(i);
                const isCorrect = currentSentence.stresses.includes(i);
                if (userHasStress) {
                  return (
                    <span
                      key={i}
                      style={{
                        color: isCorrect ? "green" : "red",
                        fontWeight: "bold",
                        marginRight: 6,
                      }}
                    >
                      {w}
                    </span>
                  );
                } else {
                  if (isCorrect) {
                    return (
                      <span
                        key={i}
                        style={{
                          color: "orange",  // 應重音但用戶沒重音標橘色
                          fontWeight: "bold",
                          marginRight: 6,
                        }}
                      >
                        {w}
                      </span>
                    );
                  } else {
                    return <span key={i} style={{ marginRight: 6 }}>{w} </span>;
                  }
                }
              })}
            </p>
            <p style={{ fontStyle: "italic", color: "#555" }}>
              （綠字為正確重音，紅字為錯誤重音，橘字為漏念重音）
            </p>
          </div>
        )}

        {showResult && (
          <button
            onClick={nextQuestion}
            style={{
              marginTop: 20,
              padding: "8px 20px",
              fontSize: 16,
              borderRadius: 8,
              border: "none",
              backgroundColor: "#1565c0",
              color: "white",
              cursor: "pointer",
            }}
          >
            下一題
          </button>
        )}
      </div>
    </div>
  );
}

export default App;



