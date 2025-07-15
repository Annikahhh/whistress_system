import React, { useState, useRef } from "react";

const sentences = [
  { text: "The cat slept under the warm blanket", stresses: [1, 5] },
  { text: "My brother plays the guitar every night", stresses: [1, 5] },
  { text: "She quickly answered the difficult question", stresses: [1, 5] },
  { text: "He opened the door without making a sound", stresses: [2, 7] },
  { text: "I usually drink coffee before work", stresses: [2, 4] },
  { text: "They traveled across the country by train", stresses: [1, 6] },
  { text: "The flowers bloom beautifully in spring", stresses: [2, 4] },
  { text: "You should always tell the truth", stresses: [2, 4] },
  { text: "We watched a movie at the cinema", stresses: [1, 6] },
  { text: "The teacher gave us an interesting assignment", stresses: [1, 6] },
];

function App() {
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

  const updateState = (idx, newPartialState) => {
    setStates((prevStates) =>
      prevStates.map((state, i) =>
        i === idx ? { ...state, ...newPartialState } : state
      )
    );
  };

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

  const stopRecording = (idx) => {
    const recorder = mediaRecorderRefs.current[idx];
    if (recorder && recorder.state === "recording") {
      recorder.stop();
      updateState(idx, { recording: false });
    }
  };

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

  const pollTaskResult = (taskId, idx) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/tasks/${taskId}`);
        const data = await res.json();

        if (data.status === "COMPLETED") {
          clearInterval(interval);

          if (data.result.batch_task_id) {
            pollTaskResult(data.result.batch_task_id, idx);
          } else if (data.result.predicted_transcription) {
            const predicted = data.result.predicted_stresses;

            updateState(idx, {
              userStressIndices: [...predicted],
              showResult: true,
            });
          } else {
            console.warn("COMPLETED，但結果格式不明：", data.result);
          }
        } else if (data.status === "FAILED") {
          clearInterval(interval);
          alert("任務失敗：" + data.error);
        }
      } catch (err) {
        clearInterval(interval);
        alert("任務查詢錯誤：" + err.message);
      }
    }, 1000);
  };

  return (
    <div
      style={{
        backgroundColor: "#e3f2fd",
        fontFamily: "sans-serif",
        minHeight: "100vh",
        padding: "40px 5vw",
        boxSizing: "border-box",
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
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <p style={{ fontSize: 18, margin: 0, flex: 1 }}>
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

              <div style={{ display: "flex", gap: 10, marginLeft: 12 }}>
                {!recording ? (
                  <button
                    onClick={() => startRecording(idx)}
                    style={{
                      fontSize: 16,
                      padding: "8px 14px",
                      cursor: "pointer",
                      borderRadius: 6,
                      border: "none",
                      backgroundColor: "#1976d2",
                      color: "white",
                    }}
                  >
                    🎙️ 開始錄音
                  </button>
                ) : (
                  <button
                    onClick={() => stopRecording(idx)}
                    style={{
                      fontSize: 16,
                      padding: "8px 14px",
                      cursor: "pointer",
                      borderRadius: 6,
                      border: "none",
                      backgroundColor: "#d32f2f",
                      color: "white",
                    }}
                  >
                    ⏹️ 停止錄音
                  </button>
                )}
                <button
                  onClick={() => sendAudio(idx)}
                  disabled={!audioURL}
                  style={{
                    fontSize: 16,
                    padding: "8px 14px",
                    cursor: audioURL ? "pointer" : "not-allowed",
                    borderRadius: 6,
                    border: "none",
                    backgroundColor: audioURL ? "#4caf50" : "#ccc",
                    color: "white",
                  }}
                >
                  📤 分析重音
                </button>
              </div>
            </div>

            {audioURL && (
              <audio
                src={audioURL}
                controls
                style={{ marginBottom: 10, width: "100%" }}
              />
            )}

            {showResult && (
              <div
                style={{
                  backgroundColor: "#f1f8e9",
                  padding: 12,
                  borderRadius: 6,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "flex-start",
                  height: 80,
                  userSelect: "none",
                }}
              >
                <p
                  style={{
                    fontSize: 18,
                    margin: 0,
                    wordBreak: "break-word",
                    lineHeight: 1.4,
                  }}
                >
                  {words.map((w, i) => {
                    const userHas =
                      Array.isArray(userStressIndices) &&
                      userStressIndices.includes(i);
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
                    fontSize: 14,
                    color: "#555",
                    marginTop: 8,
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
