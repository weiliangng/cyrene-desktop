"""Text output without speech generation; independent sound cues remain enabled."""
from .tts_interface import TTSInterface


class TTSEngine(TTSInterface):
    speech_enabled = False

    def generate_audio(self, text, file_name_no_ext=None):
        return None

    async def async_generate_audio(self, text, file_name_no_ext=None):
        return None
