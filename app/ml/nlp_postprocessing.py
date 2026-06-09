"""NLP postprocessing for refining lip-reading transcription output."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TranscriptionPostprocessor:
    """
    NLP-based postprocessing to refine lip-reading predictions.

    Pipeline:
    1. Spell correction for low-confidence words
    2. Capitalization (sentence starts, proper nouns)
    3. Punctuation insertion
    4. Context-based correction
    5. Grammar refinement
    """

    COMMON_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "shall",
        "should", "may", "might", "can", "could", "must", "need", "dare",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "hello", "hi", "hey", "goodbye", "bye", "thanks", "thank",
        "yes", "no", "please", "sorry", "excuse",
    }

    SENTENCE_STARTERS = {
        "i", "the", "a", "an", "my", "we", "they", "he", "she", "it",
        "hello", "hi", "hey", "goodbye", "yes", "no", "please", "thank",
        "what", "where", "when", "why", "how", "who", "which",
    }

    def __init__(self, use_grammar_tool: bool = False):
        self._grammar_tool = None
        if use_grammar_tool:
            try:
                import language_tool_python
                self._grammar_tool = language_tool_python.LanguageTool("en-US")
                logger.info("LanguageTool grammar checker loaded")
            except ImportError:
                logger.warning("language_tool_python not available")

    def refine_transcription(
        self,
        raw_text: str,
        confidence_scores: Optional[List[float]] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Refine transcription using NLP techniques.

        Args:
            raw_text: Raw model output text
            confidence_scores: Per-character confidence scores
            context: Optional context for domain-specific correction

        Returns:
            Dict with original, refined, changes, confidence_boost
        """
        refined = raw_text
        changes = []

        refined, spell_changes = self._fix_spelling(refined, confidence_scores)
        changes.extend(spell_changes)

        refined, cap_changes = self._fix_capitalization(refined)
        changes.extend(cap_changes)

        refined, punct_changes = self._fix_punctuation(refined)
        changes.extend(punct_changes)

        refined, clean_changes = self._clean_artifacts(refined)
        changes.extend(clean_changes)

        if self._grammar_tool:
            refined, grammar_changes = self._grammar_check(refined)
            changes.extend(grammar_changes)

        if context:
            refined, ctx_changes = self._apply_context(refined, context)
            changes.extend(ctx_changes)

        confidence_boost = min(len(changes) * 0.02, 0.15)

        return {
            "original": raw_text,
            "refined": refined,
            "changes": changes,
            "confidence_boost": round(confidence_boost, 3),
            "change_count": len(changes),
        }

    def _fix_spelling(
        self, text: str, confidence_scores: Optional[List[float]] = None
    ) -> Tuple[str, List[str]]:
        """Correct likely misspellings using dictionary lookup."""
        changes = []
        words = text.split()
        corrected_words = []

        for i, word in enumerate(words):
            lower = word.lower().strip(".,!?;:'\"")
            if lower in self.COMMON_WORDS or len(lower) <= 2:
                corrected_words.append(word)
                continue

            if self._is_likely_misspelling(lower):
                suggestion = self._suggest_correction(lower)
                if suggestion and suggestion != lower:
                    original_word = word
                    if word[0].isupper():
                        suggestion = suggestion.capitalize()
                    corrected_words.append(suggestion)
                    changes.append(f"Spell: '{original_word}' -> '{suggestion}'")
                    continue

            corrected_words.append(word)

        return " ".join(corrected_words), changes

    def _is_likely_misspelling(self, word: str) -> bool:
        """Heuristic to detect likely misspellings."""
        if len(word) < 3:
            return False
        vowels = sum(1 for c in word if c in "aeiou")
        if vowels == 0 and len(word) > 2:
            return True
        if len(word) > 6 and vowels / len(word) < 0.2:
            return True
        repeated = sum(1 for i in range(1, len(word)) if word[i] == word[i - 1])
        if repeated > len(word) * 0.4:
            return True
        return False

    def _suggest_correction(self, word: str) -> Optional[str]:
        """Suggest spelling correction using edit distance."""
        best_match = None
        best_distance = float("inf")

        for known in self.COMMON_WORDS:
            dist = self._edit_distance(word, known)
            if dist < best_distance and dist <= 2:
                best_distance = dist
                best_match = known

        return best_match

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance."""
        if len(s1) < len(s2):
            return TranscriptionPostprocessor._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row

        return prev_row[-1]

    @staticmethod
    def _fix_capitalization(text: str) -> Tuple[str, List[str]]:
        """Capitalize sentence starts and proper nouns."""
        changes = []
        if not text:
            return text, changes

        sentences = re.split(r'(?<=[.!?])\s+', text)
        capitalized = []

        for sent in sentences:
            if not sent:
                continue
            original = sent
            sent = sent[0].upper() + sent[1:]
            if original != sent:
                changes.append(f"Capitalize: '{original[:30]}' -> '{sent[:30]}'")
            capitalized.append(sent)

        result = " ".join(capitalized)
        return result, changes

    @staticmethod
    def _fix_punctuation(text: str) -> Tuple[str, List[str]]:
        """Fix common punctuation issues."""
        changes = []
        original = text

        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',{2,}', ',', text)
        text = re.sub(r'\?{2,}', '?', text)
        text = re.sub(r'!{2,}', '!', text)

        if text and not text.endswith(('.', '!', '?')):
            text += '.'
            changes.append("Added period at end")

        if text != original:
            changes.append("Fixed punctuation spacing")

        return text, changes

    @staticmethod
    def _clean_artifacts(text: str) -> Tuple[str, List[str]]:
        """Remove common model artifacts and noise."""
        changes = []
        original = text

        text = re.sub(r'[_]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        text = re.sub(r'\buh+\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bum+\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\ber+\b', '', text, flags=re.IGNORECASE)

        text = re.sub(r'\s+', ' ', text).strip()

        if text != original:
            changes.append("Cleaned artifacts")

        return text, changes

    def _grammar_check(self, text: str) -> Tuple[str, List[str]]:
        """Run grammar checking using LanguageTool."""
        if not self._grammar_tool:
            return text, []

        changes = []
        try:
            matches = self._grammar_tool.check(text)
            corrected = text

            for match in matches[:10]:
                if match.replacements:
                    old_text = corrected[match.offset:match.offset + match.length]
                    new_text = match.replacements[0]
                    corrected = corrected[:match.offset] + new_text + corrected[match.offset + match.length:]
                    changes.append(f"Grammar: '{old_text}' -> '{new_text}'")

            return corrected, changes
        except Exception as e:
            logger.warning(f"Grammar check failed: {e}")
            return text, []

    def _apply_context(self, text: str, context: str) -> Tuple[str, List[str]]:
        """Apply domain-specific corrections based on context."""
        changes = []
        context_lower = context.lower()

        corrections = {
            "medical": {"hear": "heart", "piece": "peace", "dose": "doze"},
            "technical": {"for": "four", "scene": "seen", "write": "right"},
            "general": {"would of": "would have", "could of": "could have", "should of": "should have"},
        }

        for domain, mapping in corrections.items():
            if domain in context_lower or domain == "general":
                for wrong, correct in mapping.items():
                    if wrong in text.lower():
                        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
                        new_text = pattern.sub(correct, text)
                        if new_text != text:
                            changes.append(f"Context ({domain}): '{wrong}' -> '{correct}'")
                            text = new_text

        return text, changes


def postprocess_transcription(
    raw_text: str,
    confidence_scores: Optional[List[float]] = None,
    context: Optional[str] = None,
    use_grammar: bool = False,
) -> Dict[str, Any]:
    """Convenience function for transcription postprocessing."""
    processor = TranscriptionPostprocessor(use_grammar_tool=use_grammar)
    return processor.refine_transcription(raw_text, confidence_scores, context)
