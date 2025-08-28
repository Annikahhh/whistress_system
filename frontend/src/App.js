import React, { useState, useRef } from "react";

const sentences = [
  //{ text: "Andy and his friends went to the amusement park last weekend. They were very excited! First, they rode the big roller coaster. It went fast! Andy screamed, but he was happy. Next, they ate ice cream and hot dogs. The ice cream was cold and sweet. The hot dog was delicious.", stresses: [0, 3, 7, 8, 10, 13, 14, 15, 17, 19, 20, 21, 24, 25, 26, 30, 31, 33, 34, 35, 37, 38, 40, 41, 43, 45, 47, 48, 50] },
  { text: "I usually wake up at seven in the morning", stresses: [2, 5, 8] },
  { text: "She quickly answered the difficult question", stresses: [1, 5] },
  { text: "My brother plays the guitar every night", stresses: [1, 4] },
  { text: "He opened the door without making a sound", stresses: [1, 3, 7] },
  { text: "I usually drink coffee before work", stresses: [2, 4] },
  { text: "They traveled across the country by train", stresses: [1, 6] },
  { text: "The flowers bloom beautifully in spring", stresses: [2, 5] },
  { text: "You should always tell the truth", stresses: [2, 5] },
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
      prevStates.map((state, i) => (i === idx ? { ...state, ...newPartialState } : state))
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
          sendAudio(idx); // ✅ 確保 chunks 有資料後再送出分析
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
      <h2 style={{ color: "#1565c0", marginBottom: 30 }}>🔊 英文句子重音分析</h2>

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
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <div style={{fontSize: 18, fontWeight: "500" }}
                  // fontSize: 18,
                  // fontWeight: "500",
                  // flex: 1,
                  // flexWrap: "wrap",
                  // wordWrap: "break-word",
                  // overflowWrap: "break-word",
                  // whiteSpace: "normal", // <-- 最重要這一行
                  // lineHeight: 1.6,
                //}}
              >
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
              </div>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                {!recording ? (
                  <button
                    onClick={() => startRecording(idx)}
                    style={{ padding: "8px 14px", fontSize: 16, cursor: "pointer" }}
                  >
                    🎙️ 開始錄音
                  </button>
                ) : (
                  <button
                    onClick={() => stopRecording(idx)}
                    style={{ padding: "8px 14px", fontSize: 16, cursor: "pointer" }}
                  >
                    ⏹️ 停止錄音
                  </button>
                )}
              </div>
            </div>

            {audioURL && <audio src={audioURL} controls style={{ marginBottom: 12 }} />}

            {showResult && (
              <div
                style={{
                  backgroundColor: "#f1f8e9",
                  padding: 12,
                  borderRadius: 6,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  minHeight: 80,
                }}
              >
                <p style={{ fontSize: 18, margin: 0 }}>
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
                            marginRight: 8,
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
                            marginRight: 8,
                          }}
                        >
                          {w}
                        </span>
                      ) : (
                        <span key={i} style={{ marginRight: 8 }}>
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
                    textAlign: "left",
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
