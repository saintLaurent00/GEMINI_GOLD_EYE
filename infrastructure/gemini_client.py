import google.generativeai as genai
import time
from config import settings
from PIL import Image

class GeminiClient:
    def __init__(self):
        # Configuration unique au démarrage
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.MODEL_NAME)

    def send_multimodal_prompt(self, text_prompt, image_paths):
        """
        Envoie une requête mixte (Texte + Liste d'images) à Gemini.
        Gère automatiquement les erreurs de quota (Wait & Retry).
        """
        # 1. Chargement des images
        images_payload = []
        for path in image_paths:
            try:
                img = Image.open(path)
                images_payload.append(img)
            except Exception as e:
                print(f"⚠️ Impossible de charger l'image {path}: {e}")

        if not images_payload:
            print("❌ Erreur: Aucune image valide à envoyer.")
            return None

        # 2. Construction du message (Prompt + Images)
        content = [text_prompt] + images_payload
        
        # 3. Envoi avec Retry Logic (Robustesse)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(content)
                return response.text
            
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Quota" in error_msg:
                    wait_time = 30 * (attempt + 1) # Attente progressive (30s, 60s...)
                    print(f"⏳ Quota Gemini atteint. Pause de {wait_time}s... ({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                elif "500" in error_msg or "503" in error_msg:
                    print(f"⚠️ Erreur Serveur Google. Pause de 5s...")
                    time.sleep(5)
                else:
                    print(f"❌ Erreur Gemini fatale : {e}")
                    return None
        
        print("❌ Abandon après 3 tentatives.")
        return None