import torch
from transformers import WhisperConfig
import librosa
import numpy as np
import pathlib
from torch.nn import functional as F
from ..model import WhiStress
#from typing import Optional, List, Dict, Union
from typing import List, Union, Dict, Optional

PATH_TO_WEIGHTS = pathlib.Path(__file__).parent.parent / "weights"


def get_loaded_model(device="cuda"):
    whisper_model_name = f"openai/whisper-small.en"
    whisper_config = WhisperConfig()
    whistress_model = WhiStress(
        whisper_config, layer_for_head=9, whisper_backbone_name=whisper_model_name
    ).to(device)
    whistress_model.processor.tokenizer.model_input_names = [
        "input_ids",
        "input_features", # 添加 input_features
        "attention_mask",
        "labels_head",
    ]
    whistress_model.load_model(PATH_TO_WEIGHTS)
    whistress_model.to(device)
    whistress_model.eval()
    return whistress_model


def get_word_emphasis_pairs(
    transcription_preds, emphasis_preds, processor, filter_special_tokens=True
):
    emphasis_preds_list = emphasis_preds.tolist()
    transcription_preds_words = [
        processor.tokenizer.decode([i], skip_special_tokens=False)
        for i in transcription_preds
    ]
    if filter_special_tokens:
        special_tokens_indices = [
            i
            for i, x in enumerate(transcription_preds)
            if x in processor.tokenizer.all_special_ids
        ]
        emphasis_preds_list = [
            x
            for i, x in enumerate(emphasis_preds_list)
            if i not in special_tokens_indices
        ]
        transcription_preds_words = [
            x
            for i, x in enumerate(transcription_preds_words)
            if i not in special_tokens_indices
        ]
    return list(zip(transcription_preds_words, emphasis_preds_list))


def inference_from_audio(audio: np.ndarray, model: WhiStress, device: str):
    input_features = model.processor.feature_extractor(
        audio, sampling_rate=16000, return_tensors="pt"
    )["input_features"]
    out_model = model.generate_dual(input_features=input_features.to(device))
    emphasis_probs = F.softmax(out_model.logits, dim=-1)
    emphasis_preds = torch.argmax(emphasis_probs, dim=-1)
    emphasis_preds_right_shifted = torch.cat((emphasis_preds[:, -1:], emphasis_preds[:, :-1]), dim=1)
    word_emphasis_pairs = get_word_emphasis_pairs(
        out_model.preds[0],
        emphasis_preds_right_shifted[0],
        model.processor,
        filter_special_tokens=True,
    )
    return word_emphasis_pairs


def prepare_audio(audio, target_sr=16000):
    # resample to 16kHz
    sr = audio["sampling_rate"]
    y = audio["array"]
    y = np.array(y, dtype=float)
    y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
    # Normalize the audio (scale to [-1, 1])
    y_resampled /= max(abs(y_resampled))
    return y_resampled


def merge_stressed_tokens(tokens_with_stress):
    """
    tokens_with_stress is a list of tuples: (token_string, stress_value)
    e.g.:
       [(" I", 0), (" didn", 1), ("'t", 0), (" say", 0), (" he", 0), (" stole", 0),
        (" the", 0), (" money", 0), (".", 0)]
    Returns a list of merged tuples, combining subwords into full words.
    """
    merged = []

    current_word = ""
    current_stress = 0  # 0 means not stressed, 1 means stressed

    for token, stress in tokens_with_stress:
        # If token starts with a space (or is the very first), we treat it as a new word
        # or if current_word is empty (first iteration).
        if token.startswith(" ") or current_word == "":
            # If we already have something in current_word, push it into merged
            # before starting a new one
            if current_word:
                merged.append((current_word, current_stress))

            # Start a new word
            current_word = token
            current_stress = stress
        else:
            # Otherwise, it's a subword that should be appended to the previous word
            current_word += token
            # If any sub-token is stressed, the whole merged word is stressed
            current_stress = max(current_stress, stress)

    # Don't forget to append the final word
    if current_word:
        merged.append((current_word, current_stress))

    return merged


def inference_from_audio_and_transcription(
    audio: np.ndarray, transcription, model: WhiStress, device: str
):
    input_features = model.processor.feature_extractor(
        audio, sampling_rate=16000, return_tensors="pt"
    )["input_features"]
    # convert transcription to input_ids
    input_ids = model.processor.tokenizer(
        transcription,
        return_tensors="pt",
        padding="max_length",
        truncation=True,
        max_length=30,
    )["input_ids"]
    out_model = model(
                    input_features=input_features.to(device),
                    decoder_input_ids=input_ids.to(device),
                )
    emphasis_probs = F.softmax(out_model.logits, dim=-1)
    emphasis_preds = torch.argmax(emphasis_probs, dim=-1)
    emphasis_preds_right_shifted = torch.cat((emphasis_preds[:, -1:], emphasis_preds[:, :-1]), dim=1)
    word_emphasis_pairs = get_word_emphasis_pairs(
        input_ids[0],
        emphasis_preds_right_shifted[0],
        model.processor,
        filter_special_tokens=True,
    )
    return word_emphasis_pairs

def scored_transcription(audio, model, strip_words=True, transcription: str = None, device="cuda"):
    audio_arr = prepare_audio(audio)
    token_stress_pairs = None
    if transcription: # if we want to use the ground truth transcription
        token_stress_pairs = inference_from_audio_and_transcription(audio_arr, transcription, model, device)
    else:
        token_stress_pairs = inference_from_audio(audio_arr, model, device)
    # token_stress_pairs = inference_from_audio(audio_arr, model)
    word_level_stress = merge_stressed_tokens(token_stress_pairs)
    if strip_words:
        word_level_stress = [(word.strip(), stress) for word, stress in word_level_stress]
    return word_level_stress

#####################################
def inference_from_audio_batch(audio_list: list[np.ndarray], model: WhiStress, device: str):
    """
    接收一個音頻 NumPy 陣列的列表，執行批次模型推論。
    """
    # 1. 預處理所有音頻並收集 feature tensors
    # WhisperProcessor.feature_extractor 可以直接處理音頻列表並自動填充
    input_features_output = model.processor.feature_extractor(
        audio_list, sampling_rate=16000, return_tensors="pt"
    )
    batch_input_features = input_features_output["input_features"].to(device)
    
    # 2. 執行模型推論
    out_model = model.generate_dual(input_features=batch_input_features)

    # 3. 後處理結果 (這部分需要適應批次輸出)
    emphasis_probs_batch = F.softmax(out_model.logits, dim=-1) # (batch_size, seq_len, num_classes)
    emphasis_preds_batch = torch.argmax(emphasis_probs_batch, dim=-1) # (batch_size, seq_len)
    
    # 處理 emphasis_preds_right_shifted_batch 的維度
    # `emphasis_preds_batch` 的形狀是 `(batch_size, sequence_length)`
    emphasis_preds_right_shifted_batch = torch.cat(
        (emphasis_preds_batch[:, -1:].unsqueeze(1), emphasis_preds_batch[:, :-1]), dim=1 # 修正 cat dim
    )
    # 再次確認：如果 emphasis_preds_batch 是 (B, S)，那麼 -1: 和 :-1 是在 S 維度
    # cat 的結果還是 (B, S)
    # emphasis_preds_right_shifted_batch = torch.cat(
    #     (emphasis_preds_batch[:, -1:], emphasis_preds_batch[:, :-1]), dim=1
    # )
    # 這個應該是錯的，因為 `emphasis_preds[:, -1:]` 是一個 `(B, 1)` 的 tensor。
    # `emphasis_preds[:, :-1]` 是一個 `(B, S-1)` 的 tensor。
    # 它們在 dim=1 堆疊是正確的。

    # 然而，原始代碼的 `torch.cat((emphasis_preds[:, -1:], emphasis_preds[:, :-1]), dim=1)`
    # 實際上是對 `(Batch_size, Sequence_length)` 的 `emphasis_preds` 進行操作，
    # 其中 `emphasis_preds[:, -1:]` 會得到 `(Batch_size, 1)`，
    # `emphasis_preds[:, :-1]` 會得到 `(Batch_size, Sequence_length - 1)`。
    # 這兩個在 `dim=1` 上 concatenate 會得到 `(Batch_size, Sequence_length)`。
    # 所以原始代碼在新的批次場景下是正確的。

    all_word_emphasis_pairs = []
    # 遍歷批次中的每個結果
    for i in range(len(audio_list)):
        single_transcription_preds = out_model.preds[i] # 取得單個音頻的轉錄預測
        single_emphasis_preds = emphasis_preds_right_shifted_batch[i] # 取得單個音頻的重音預測

        word_emphasis_pairs = get_word_emphasis_pairs(
            single_transcription_preds,
            single_emphasis_preds,
            model.processor,
            filter_special_tokens=True,
        )
        all_word_emphasis_pairs.append(word_emphasis_pairs)

    return all_word_emphasis_pairs

# --- 新增的帶轉錄的批次推論函數 ---
def inference_from_audio_and_transcription_batch(
    audio_list: list[np.ndarray], transcription_list: list[str], model: WhiStress, device: str
):
    """
    接收音頻 NumPy 陣列列表和對應的轉錄文本列表，執行批次模型推論。
    """
    # 1. 預處理所有音頻特徵
    input_features_output = model.processor.feature_extractor(
        audio_list, sampling_rate=16000, return_tensors="pt"
    )
    batch_input_features = input_features_output["input_features"].to(device)

    # 2. 預處理所有轉錄文本為 input_ids
    input_ids_output = model.processor.tokenizer(
        transcription_list,
        return_tensors="pt",
        padding="max_length", # 確保填充到相同長度
        truncation=True,
        max_length=30, # 使用模型定義的 max_length
    )
    batch_input_ids = input_ids_output["input_ids"].to(device)

    # 3. 執行模型推論
    out_model = model(
        input_features=batch_input_features,
        decoder_input_ids=batch_input_ids,
    )
    
    # 4. 後處理結果
    emphasis_probs_batch = F.softmax(out_model.logits, dim=-1)
    emphasis_preds_batch = torch.argmax(emphasis_probs_batch, dim=-1)

    emphasis_preds_right_shifted_batch = torch.cat(
        (emphasis_preds_batch[:, -1:], emphasis_preds_batch[:, :-1]), dim=1
    )

    all_word_emphasis_pairs = []
    for i in range(len(audio_list)):
        single_transcription_ids = batch_input_ids[i]
        single_emphasis_preds = emphasis_preds_right_shifted_batch[i]

        word_emphasis_pairs = get_word_emphasis_pairs(
            single_transcription_ids,
            single_emphasis_preds,
            model.processor,
            filter_special_tokens=True,
        )
        all_word_emphasis_pairs.append(word_emphasis_pairs)
    
    return all_word_emphasis_pairs

# --- 最終的 `scored_transcription` 和 `scored_transcription_batch` 函數 ---
def scored_transcription(audio_dict, model, strip_words=True, transcription: str = None, device="cuda"):
    audio_arr = prepare_audio(audio_dict)
    token_stress_pairs = None
    if transcription:
        # 單個音頻和轉錄的推論
        token_stress_pairs = inference_from_audio_and_transcription(audio_arr, transcription, model, device)
    else:
        # 單個音頻的推論
        token_stress_pairs = inference_from_audio(audio_arr, model, device)
    
    word_level_stress = merge_stressed_tokens(token_stress_pairs)
    if strip_words:
        word_level_stress = [(word.strip(), stress) for word, stress in word_level_stress]
    return word_level_stress

def scored_transcription_batch(
    audio_dicts: List[Dict[str, Union[np.ndarray, int]]], # 確保 List, Dict, Union 也被導入
    model: WhiStress,
    strip_words=True,
    transcriptions: Optional[List[str]] = None, # 這裡的 Optional 就能正常使用了
    device="cuda"
):
    """
    接收一個音頻字典列表，對所有音頻執行批次推論。
    如果提供了 transcriptions 列表，則使用帶轉錄的批次推論。
    """
    print("&&&in utils: scored_transciption_batch")
    prepared_audio_arrs = [prepare_audio(audio_dict) for audio_dict in audio_dicts]
    
    if transcriptions:
        if len(transcriptions) != len(audio_dicts):
            raise ValueError("Length of transcriptions list must match length of audio_dicts list.")
        batch_token_stress_pairs_list = inference_from_audio_and_transcription_batch(
            prepared_audio_arrs, transcriptions, model, device
        )
    else:
        batch_token_stress_pairs_list = inference_from_audio_batch(
            prepared_audio_arrs, model, device
        )

    all_results = []
    for token_stress_pairs in batch_token_stress_pairs_list:
        word_level_stress = merge_stressed_tokens(token_stress_pairs)
        if strip_words:
            word_level_stress = [(word.strip(), stress) for word, stress in word_level_stress]
        all_results.append(word_level_stress)
    
    return all_results