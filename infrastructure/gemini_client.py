import google.generativeai as genai
import time
from config import settings
from PIL import Image


class GeminiClient:
    """
    Client Gemini avec ROTATION DE CLES API.

    Plusieurs cles -> en cas de quota (429) sur une cle, on bascule immediatement
    sur la suivante (round-robin). On ne renonce qu'apres avoir epuise TOUTES les cles.
    Retro-compatible : 1 seule cle -> comportement d'origine.
    """
    def __init__(self, keys=None):
        self.keys = keys or settings.GEMINI_API_KEYS
        if not self.keys:
            raise RuntimeError("Aucune cle API Gemini. Renseigne GEMINI_API_KEYS (ou GEMINI_API_KEY).")
        self._idx = 0                       # index de la cle courante
        self.model = self._build_model()

    def _current_key(self):
        return self.keys[self._idx]

    def _build_model(self):
        genai.configure(api_key=self._current_key())
        return genai.GenerativeModel(settings.MODEL_NAME)

    def _rotate(self):
        """Bascule sur la cle suivante. Retourne False si on a fait le tour complet."""
        self._idx = (self._idx + 1) % len(self.keys)
        self.model = self._build_model()
        return self._idx != 0 or len(self.keys) == 1

    def send_multimodal_prompt(self, text_prompt, image_paths):
        """Envoie Texte + Images. Rotation de cle sur quota 429."""
        # 1. Chargement des images
        images_payload = []
        for path in image_paths:
            try:
                images_payload.append(Image.open(path))
            except Exception as e:
                print(f"⚠️ Image illisible {path}: {e}")
        if not images_payload:
            print("❌ Aucune image valide a envoyer.")
            return None

        content = [text_prompt] + images_payload
        max_per_key = 2                      # retries par cle avant rotation
        total_attempts = max_per_key * len(self.keys) + 2  # marge

        attempts = 0
        consecutive_quota = 0
        while attempts < total_attempts:
            attempts += 1
            try:
                response = self.model.generate_content(content)
                return response.text
            except Exception as e:
                msg = str(e)
                if "429" in msg or "Quota" in msg or "quota" in msg or "RESOURCE_EXHAUSTED" in msg:
                    consecutive_quota += 1
                    # Rotation de cle si on en a plusieurs
                    if len(self.keys) > 1:
                        nxt = (self._idx + 1) % len(self.keys)
                        print(f"⏳ Quota sur cle #{self._idx+1}. Bascule sur cle #{nxt+1}...")
                        self._rotate()
                        continue
                    # 1 seule cle : on attend (ancien comportement)
                    wait = 30 * consecutive_quota
                    print(f"⏳ Quota Gemini. Pause {wait}s... ({consecutive_quota})")
                    time.sleep(wait)
                    if consecutive_quota >= 3:
                        print("❌ Quota persistant, abandon.")
                        return None
                elif "500" in msg or "503" in msg:
                    print("⚠️ Erreur serveur Google. Pause 5s...")
                    time.sleep(5)
                else:
                    print(f"❌ Erreur Gemini fatale : {e}")
                    return None
        print("❌ Abandon apres epuisement des cles/tentatives.")
        return None
