"""
GeminiClient - Client Gemini avec ROTATION DE CLES API.

Utilise le nouveau SDK officiel `google.genai` (google-genai), non deprecie.
Repli automatique sur l'ancien `google.generativeai` si le nouveau n'est pas installe
(robustesse: le bot marche dans tous les cas).

Plusieurs cles -> sur quota (429) on bascule immediatement sur la suivante
(round-robin), sans attente bloquante. Renonce seulement apres epuisement des cles.
"""

import time
from config import settings
from PIL import Image

# Detection du SDK disponible : nouveau google.genai (prefere) ou ancien (repli)
try:
    from google import genai as _genai_new
    try:
        from google.genai import types as _genai_types
    except Exception:
        _genai_types = None
    _USE_NEW_SDK = True
except Exception:
    try:
        import google.generativeai as _genai_old
        _USE_NEW_SDK = False
    except Exception as e:
        raise RuntimeError(
            "Ni google-genai ni google-generativeai n'est installe.\n"
            "Installe le nouveau SDK: pip install google-genai"
        ) from e


def _is_quota_error(msg):
    m = str(msg)
    return ("429" in m or "Quota" in m or "quota" in m
            or "RESOURCE_EXHAUSTED" in m or "resource_exhausted" in m)


class GeminiClient:
    def __init__(self, keys=None):
        self.keys = keys or settings.GEMINI_API_KEYS
        if not self.keys:
            raise RuntimeError(
                "Aucune cle API Gemini. Renseigne GEMINI_API_KEYS (ou GEMINI_API_KEY).")
        self._idx = 0
        self._init_backend()

    # --------------------------------------------------------
    # Backends : nouveau SDK (genai.Client) ou ancien (GenerativeModel)
    # --------------------------------------------------------
    def _init_backend(self):
        self._client = None
        self._model = None
        if _USE_NEW_SDK:
            # Une instance genai.Client par cle (la cle est portee par le client)
            self._client = _genai_new.Client(api_key=self._current_key())
        else:
            _genai_old.configure(api_key=self._current_key())
            self._model = _genai_old.GenerativeModel(settings.MODEL_NAME)

    def _current_key(self):
        return self.keys[self._idx]

    def _rotate(self):
        self._idx = (self._idx + 1) % len(self.keys)
        self._init_backend()
        return self._idx != 0 or len(self.keys) == 1

    # --------------------------------------------------------
    # Appel multimodal (Texte + Images)
    # --------------------------------------------------------
    def send_multimodal_prompt(self, text_prompt, image_paths):
        # 1. Chargement des images
        images_payload = []
        for path in image_paths:
            try:
                images_payload.append(Image.open(path))
            except Exception as e:
                print(f"⚠️ Image illisible {path}: {e}")
        if not images_payload:
            print("❌ Aucune image valide à envoyer.")
            return None

        max_per_key = 2
        total_attempts = max_per_key * len(self.keys) + 2
        attempts = 0
        consecutive_quota = 0

        while attempts < total_attempts:
            attempts += 1
            try:
                if _USE_NEW_SDK:
                    response = self._client.models.generate_content(
                        model=settings.MODEL_NAME,
                        contents=[text_prompt] + images_payload,
                    )
                else:
                    response = self._model.generate_content([text_prompt] + images_payload)
                return self._extract_text(response)
            except Exception as e:
                msg = str(e)
                if _is_quota_error(msg):
                    consecutive_quota += 1
                    if len(self.keys) > 1:
                        nxt = (self._idx + 1) % len(self.keys)
                        print(f"⏳ Quota sur clé #{self._idx+1}. Bascule sur clé #{nxt+1}...")
                        self._rotate()
                        continue
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
        print("❌ Abandon après épuisement des clés/tentatives.")
        return None

    @staticmethod
    def _extract_text(response):
        """Recupere le texte de la reponse (robuste aux deux SDK)."""
        try:
            txt = response.text
            if txt:
                return txt
        except Exception:
            pass
        # Repli: extraire les parts texte des candidats (nouveau SDK)
        try:
            cands = response.candidates
            if cands:
                parts = cands[0].content.parts
                return "".join(p.text for p in parts if getattr(p, "text", None))
        except Exception:
            pass
        return None
