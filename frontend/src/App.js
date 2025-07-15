import React, { useState, useRef } from "react";

const sentences = [
  { text: "I want to eat an apple.", stresses: [0, 5] },
  { text: "She likes to play the piano.", stresses: [1, 5] },
  { text: "Today is a beautiful sunny day.", stresses: [0, 4] },
  { text: "Can you help me with this task.", stresses: [1, 5] },
  { text: "He is reading a good book.", stresses: [0, 5] },
  { text: "We will meet at the coffee shop.", stresses: [2, 6] },
  { text: "They are watching a new movie.", stresses: [1, 5] },
  { text: "The weather forecast says it will rain.", stresses: [0, 7] },
  { text: "I bought some fresh vegetables today.", stresses: [0, 6] },
  { text: "Please open the window for some air.", stresses: [1, 6] },
];

function App() {
  // states 陣列：每題的錄音狀態、音檔 URL、重音分析結果、是否顯示結果
  const [states, setStates] = useState(
    sentences.map(() => ({
      recording: false,
      audioURL: null,
      userStressIndices: [],
      showResult: false,
    }))
  );

  const mediaRecorderRefs = useRef([]);
  const chunksRefs = useRef(sentences.map(() => []));

  // 更新單題狀態的輔助函式，確保創建新陣列以觸發重渲染
  const updateState = (idx, newPartialState) => {
    setStates((prevStates) =>
      prevStates.map((state, i) =>
        i === idx ? { ...state, ...newPartialState } : state
      )
    );
  };

  // 開始錄音
  const startRecording = (idx) => {
    updateState(idx, { recording: true, audioURL: null, showResult: false });
    chunksRefs.current[idx] = [];

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRefs.current[idx] = mediaRecorder;
        mediaRecorder.start();

        mediaRecorder.ondataavailable = (e) => {
          chunksRefs.current[idx].push(e.data);
        };

        mediaRecorder.onstop = () => {
          const blob = new Blob(chunksRefs.current[idx], { type: "audio/wav" });
          const url = URL.createObjectURL(blob);
          updateState(idx, { audioURL: url });
        };
      })
      .catch((err) => {
        alert("麥克風存取失敗：" + err.message);
        updateState(idx, { recording: false });
      });
  };

  // 停止錄音
  const stopRecording = (idx) => {
    const recorder = mediaRecorderRefs.current[idx];
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      updateState(idx, { recording: false });
    }
  };

  // 送出音檔分析重音
  const sendAudio = async (idx) => {
    const chunks = chunksRefs.current[idx];
    if (!chunks.length) {
      alert("尚未錄音");
      return;
    }

    const blob = new Blob(chunks, { type: "audio/wav" });
    const formData = new FormData();
    formData.append("audio_file", blob, "recording.wav");
    formData.append("prompt_text", sentences[idx].text);

    try {
      const response = await fetch("http://localhost:8000/analyze_stress_async", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (data.success) {
        pollTaskResult(data.task_id, idx);
      } else {
        alert("分析任務提交失敗");
      }
    } catch (err) {
      alert("上傳錯誤：" + err.message);
    }
  };

  // 輪詢任務結果
  const pollTaskResult = (taskId, idx) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/tasks/${taskId}`);
        const data = await res.json();

        console.log(`Polling task ${taskId} status:`, data.status, "Result:", data.result);

        if (data.status === "COMPLETED") {
          clearInterval(interval);

          if (data.result.batch_task_id) {
            // 中繼任務，換成新的 task_id 繼續輪詢
            pollTaskResult(data.result.batch_task_id, idx);
          } else if (data.result.predicted_transcription) {
            const predicted = data.result.predicted_stresses;
            console.log("✅ 更新第", idx, "題重音：", predicted);

            updateState(idx, {
              userStressIndices: [...predicted], // 確保新陣列觸發更新
              showResult: true,
            });
          } else {
            console.warn("COMPLETED，但結果格式不明：", data.result);
          }
        } else if (data.status === "FAILED") {
          clearInterval(interval);
          alert("任務失敗：" + data.error);
        }
        // 其他狀態繼續等待
      } catch (err) {
        clearInterval(interval);
        alert("任務查詢錯誤：" + err.message);
      }
    }, 1000);
  };

  return (
    <div
      style={{
        padding: 40,
        backgroundColor: "#e3f2fd",
        fontFamily: "sans-serif",
        maxWidth: 720,
        margin: "auto",
      }}
    >
      <h2 style={{ color: "#1565c0", marginBottom: 30 }}>🔊 一頁多題句子重音分析</h2>

      {sentences.map((sentence, idx) => {
        const words = sentence.text.split(" ");
        const { recording, audioURL, userStressIndices, showResult } = states[idx];

        return (
          <div
            key={idx}
            style={{
              backgroundColor: "white",
              padding: 20,
              borderRadius: 12,
              boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
              marginBottom: 24,
            }}
          >
            <h4 style={{ color: "#0d47a1" }}>第 {idx + 1} 題</h4>
            <p style={{ fontSize: 18, marginBottom: 10 }}>
              {words.map((w, i) => {
                const isCorrect = sentence.stresses.includes(i);
                return (
                  <span
                    key={i}
                    style={{
                      textDecoration: isCorrect ? "underline" : "none",
                      fontWeight: isCorrect ? "bold" : "normal",
                      marginRight: 6,
                    }}
                  >
                    {w}
                  </span>
                );
              })}
            </p>

            <div style={{ marginBottom: 10 }}>
              {!recording ? (
                <button
                  onClick={() => startRecording(idx)}
                  style={{ marginRight: 10 }}
                >
                  🎙️ 開始錄音
                </button>
              ) : (
                <button
                  onClick={() => stopRecording(idx)}
                  style={{ marginRight: 10 }}
                >
                  ⏹️ 停止錄音
                </button>
              )}

              <button
                onClick={() => sendAudio(idx)}
                disabled={!audioURL}
                style={{
                  backgroundColor: audioURL ? "#4caf50" : "#ccc",
                  color: "white",
                  padding: "6px 12px",
                  border: "none",
                  borderRadius: 4,
                  cursor: audioURL ? "pointer" : "not-allowed",
                }}
              >
                📤 分析重音
              </button>
            </div>

            {audioURL && (
              <audio src={audioURL} controls style={{ marginBottom: 10 }} />
            )}

            {showResult && (
              <div
                style={{
                  backgroundColor: "#f1f8e9",
                  padding: 10,
                  borderRadius: 6,
                }}
              >
                <p style={{ fontSize: 16 }}>
                  {words.map((w, i) => {
                    const userHas = Array.isArray(userStressIndices) && userStressIndices.includes(i);
                    const shouldHave = sentence.stresses.includes(i);

                    if (userHas) {
                      return (
                        <span
                          key={i}
                          style={{
                            color: shouldHave ? "green" : "red",
                            fontWeight: "bold",
                            marginRight: 6,
                          }}
                        >
                          {w}
                        </span>
                      );
                    } else {
                      return shouldHave ? (
                        <span
                          key={i}
                          style={{
                            color: "orange",
                            fontWeight: "bold",
                            marginRight: 6,
                          }}
                        >
                          {w}
                        </span>
                      ) : (
                        <span key={i} style={{ marginRight: 6 }}>
                          {w}
                        </span>
                      );
                    }
                  })}
                </p>
                <p
                  style={{
                    fontStyle: "italic",
                    fontSize: 12,
                    color: "#555",
                    marginTop: 4,
                  }}
                >
                  綠=正確、紅=錯誤、橘=漏標重音
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default App;