import google.generativeai as genai
import os
import sys

# Import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings

print("--- 🤖 LISTE DES MODÈLES GEMINI DISPONIBLES ---")

genai.configure(api_key=settings.GEMINI_API_KEY)

try:
    print(f"Clé utilisée : {settings.GEMINI_API_KEY[:5]}...{settings.GEMINI_API_KEY[-5:]}")
    
    print("\n🔎 Recherche des modèles compatibles 'generateContent'...")
    available_models = []
    
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"   ✅ Trouvé : {m.name}")
            available_models.append(m.name)

    if not available_models:
        print("\n❌ Aucun modèle trouvé ! Vérifie que ta clé API a bien accès à Gemini.")
    else:
        print("\n👉 COPIE UN DE CES NOMS EXACTS dans config/settings.py")

except Exception as e:
    print(f"\n❌ Erreur connexion Google : {e}")