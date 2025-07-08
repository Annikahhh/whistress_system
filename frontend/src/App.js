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
function mockUserStress(correctStresses, wordCount) {
  // 80%機率對，20%機率錯
  return Array.from({ length: wordCount }, (_, i) => {
    if (correctStresses.includes(i)) {
      return Math.random() < 0.8 ? i : -1;
    } else {
      return Math.random() < 0.2 ? i : -1;
    }
  }).filter(i => i !== -1);
}

function App() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [recording, setRecording] = useState(false);
  const [audioURL, setAudioURL] = useState(null);
  const [userStressIndices, setUserStressIndices] = useState([]);
  const [showResult, setShowResult] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

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
    // 模擬分析：用mockUserStress 隨機生成一個使用者重音結果
    const userStress = mockUserStress(currentSentence.stresses, words.length);
    setUserStressIndices(userStress);
    setShowResult(true);
  };*/
  const sendAudio = async () => {
    if (!audioURL) return;

    // 1. 取得 Blob
    const response = await fetch(audioURL);
    const blob = await response.blob();

    // 2. 建立 FormData，加入 audio 和 prompt_text
    const formData = new FormData();
    formData.append("audio_file", blob, "recording.wav");
    formData.append("prompt_text", currentSentence.text);

    // 3. 發送到後端
    const res = await fetch("http://localhost:8000/analyze_stress_async", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (data.success && data.task_id) {
      pollResult(data.task_id);
    } else {
      alert("送出失敗");
    }
  };

  const pollResult = async (taskId) => {
    const interval = setInterval(async () => {
      const res = await fetch(`http://localhost:8000/tasks/${taskId}`);
      const data = await res.json();

      if (data.status === "COMPLETED") {
        clearInterval(interval);
        const stressIndices = data.result.stressed_indices || [];
        setUserStressIndices(stressIndices);
        setShowResult(true);
      } else if (data.status === "FAILED") {
        clearInterval(interval);
        alert("重音分析失敗：" + data.error);
      }
      // 否則繼續等待
    }, 1000);
  };

  const nextQuestion = () => {
    setCurrentIndex((idx) => (idx + 1) % sentences.length);
    setAudioURL(null);
    setUserStressIndices([]);
    setShowResult(false);
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
                  return <span key={i} style={{ marginRight: 6 }}>{w} </span>;
                }
              })}
            </p>
            <p style={{ fontStyle: "italic", color: "#555" }}>
              （綠字為正確重音，紅字為錯誤重音）
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



