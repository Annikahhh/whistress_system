import numpy as np
from .utils import get_loaded_model, scored_transcription, scored_transcription_batch
from typing import Union, Dict, Optional, List


class WhiStressInferenceClient:
    def __init__(self, device="cuda"):
        self.device = device
        self.whistress = get_loaded_model(self.device)

    def predict(
        self, audio: Dict[str, Union[np.ndarray, int]], transcription=None, return_pairs=True
    ):
        '''
        word_emphasis_pairs = scored_transcription(
            audio=audio, 
            model=self.whistress, 
            device=self.device, 
            strip_words=True, 
            transcription=transcription
        )
        if return_pairs:
            return word_emphasis_pairs
        # returs transcription str and list of emphasized words
        ''''''return " ".join([x[0] for x in word_emphasis_pairs]), [
            x[0] for x in word_emphasis_pairs if x[1] == 1
        ]''''''
        return " ".join([x[0] for x in word_emphasis_pairs]), [
            #i for i, x in enumerate(word_emphasis_pairs) if x[1] == 1
            1 if x[1] == 1 else 0 for x in word_emphasis_pairs 
        ]
        '''
        audio_dicts = [audio]
        transcriptions_list = [transcription] if transcription is not None else None

        word_emphasis_pairs_batch = scored_transcription_batch(
            audio_dicts=audio_dicts, 
            model=self.whistress, 
            device=self.device, 
            strip_words=True, 
            transcriptions=transcriptions_list # 傳遞列表
        )

        word_emphasis_pairs = word_emphasis_pairs_batch[0] # 取出單個結果

        if return_pairs:
            return word_emphasis_pairs
        return " ".join([x[0] for x in word_emphasis_pairs]), [
            1 if x[1] == 1 else 0 for x in word_emphasis_pairs 
        ]

    def predict_batch(
        self, 
        audio_list: List[Dict[str, Union[np.ndarray, int]]], 
        transcription_list: Optional[List[str]] = None, 
        return_pairs=True
    ):
        """
        對多個音頻和轉錄進行批次推論。
        """
        print("&&&inclient: predict_batch")
        word_emphasis_pairs_list_of_lists = scored_transcription_batch(
            audio_dicts=audio_list, 
            model=self.whistress, 
            device=self.device, 
            strip_words=True, 
            transcriptions=transcription_list
        )

        if return_pairs:
            return word_emphasis_pairs_list_of_lists

        # 如果 return_pairs 為 False，則為批次中的每個結果格式化輸出
        formatted_results = []
        for word_emphasis_pairs in word_emphasis_pairs_list_of_lists:
            formatted_results.append((
                " ".join([x[0] for x in word_emphasis_pairs]), 
                [1 if x[1] == 1 else 0 for x in word_emphasis_pairs]
            ))
        return formatted_results
