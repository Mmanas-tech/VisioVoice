"""Character-level vocabulary for lip-reading transcription."""

from typing import List, Optional


class CharacterVocab:
    """Character-level vocabulary with CTC blank and special tokens."""

    BLANK_TOKEN = "_"
    UNK_TOKEN = "<unk>"
    SPACE_TOKEN = " "

    def __init__(self, custom_chars: Optional[List[str]] = None):
        base_chars = list("abcdefghijklmnopqrstuvwxyz")
        punctuation = list(".,!?'-:;")
        digits = list("0123456789")
        spaces = [self.SPACE_TOKEN]

        all_chars = base_chars + punctuation + digits + spaces
        if custom_chars:
            all_chars.extend(custom_chars)

        self.chars = list(dict.fromkeys(all_chars))

        self.char_to_idx = {c: i + 1 for i, c in enumerate(self.chars)}
        self.char_to_idx[self.BLANK_TOKEN] = 0
        self.char_to_idx[self.UNK_TOKEN] = len(self.chars) + 1

        self.idx_to_char = {i: c for c, i in self.char_to_idx.items()}

    def encode(self, text: str, lowercase: bool = True) -> List[int]:
        """Convert text to character indices."""
        if lowercase:
            text = text.lower()
        return [self.char_to_idx.get(c, self.char_to_idx[self.UNK_TOKEN]) for c in text]

    def decode(self, indices: List[int], remove_blank: bool = True) -> str:
        """Convert indices to text, optionally removing CTC blanks."""
        chars = []
        for idx in indices:
            if remove_blank and idx == 0:
                continue
            chars.append(self.idx_to_char.get(idx, "?"))
        return "".join(chars)

    def ctc_decode(self, indices: List[int]) -> str:
        """CTC greedy decode: collapse repeats and remove blanks."""
        decoded = []
        prev_idx = None
        for idx in indices:
            if idx != 0 and idx != prev_idx:
                char = self.idx_to_char.get(idx, "?")
                if char != self.UNK_TOKEN:
                    decoded.append(char)
            prev_idx = idx
        return "".join(decoded)

    def ctc_beam_search(
        self, logits: List[List[float]], beam_width: int = 10
    ) -> List[tuple]:
        """CTC beam search decoding."""
        beams = [("", 0.0)]

        for frame_logits in logits:
            import numpy as np

            probs = np.exp(frame_logits) / np.sum(np.exp(frame_logits))
            top_indices = np.argsort(probs)[-beam_width:]

            new_beams = {}
            for text, score in beams:
                for idx in top_indices:
                    idx = int(idx)
                    prob = float(probs[idx])
                    char = self.idx_to_char.get(idx, "")

                    if idx == 0:
                        new_key = text
                    elif text and char == text[-1]:
                        new_key = text
                    else:
                        new_key = text + char

                    new_score = score + np.log(prob + 1e-10)
                    if new_key not in new_beams or new_score > new_beams[new_key]:
                        new_beams[new_key] = new_score

            beams = sorted(new_beams.items(), key=lambda x: x[1], reverse=True)[:beam_width]

        return [(text, score) for text, score in beams]

    @property
    def size(self) -> int:
        return len(self.char_to_idx)

    @property
    def blank_index(self) -> int:
        return 0

    def __len__(self) -> int:
        return self.size

    def __repr__(self) -> str:
        return f"CharacterVocab(size={self.size}, chars='{''.join(self.chars[:20])}...')"


DEFAULT_VOCAB = CharacterVocab()
