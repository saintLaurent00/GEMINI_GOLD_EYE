# import os
# import shutil
# import pandas as pd
# from datetime import datetime

# class TradeLogger:
#     def __init__(self):
#         self.logs_dir = "logs"
#         self.archives_dir = "logs/archives"
#         self.excel_file = f"{self.logs_dir}/Journal_Trading_Gemini.xlsx"
        
#         # Création des dossiers
#         if not os.path.exists(self.logs_dir): os.makedirs(self.logs_dir)
#         if not os.path.exists(self.archives_dir): os.makedirs(self.archives_dir)
        
#         # Création du fichier Excel s'il n'existe pas
#         self._init_excel()

#     def _init_excel(self):
#         if not os.path.exists(self.excel_file):
#             # Création d'un DataFrame vide avec les colonnes
#             df = pd.DataFrame(columns=[
#                 "DATE", "SYMBOL", "DIRECTION", "CONFIANCE", 
#                 "PRIX_ENTREE", "STOP_LOSS", "TAKE_PROFIT", "LOTS", 
#                 "RESULTAT_EXEC", "RAISON_IA", "CHEMIN_PREUVES"
#             ])
#             df.to_excel(self.excel_file, index=False)

#     def log_trade(self, symbol, decision, entry, sl, tp, lot, status, reason, image_sources):
#         """
#         1. Écrit dans Excel.
#         2. Archive les images dans un dossier daté.
#         """
#         timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#         folder_name = f"{timestamp}_{symbol}_{decision}"
#         evidence_path = os.path.join(self.archives_dir, folder_name)
        
#         # A. ARCHIVAGE DES IMAGES
#         try:
#             os.makedirs(evidence_path, exist_ok=True)
#             for img_path in image_sources:
#                 if os.path.exists(img_path):
#                     # On copie l'image dans le dossier d'archive
#                     shutil.copy(img_path, evidence_path)
#         except Exception as e:
#             print(f"⚠️ Erreur archivage images: {e}")

#         # B. ÉCRITURE EXCEL
#         new_data = {
#             "DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#             "SYMBOL": symbol,
#             "DIRECTION": decision,
#             "CONFIANCE": f"{status.get('confidence', 0)}%",
#             "PRIX_ENTREE": entry,
#             "STOP_LOSS": sl,
#             "TAKE_PROFIT": tp,
#             "LOTS": lot,
#             "RESULTAT_EXEC": "SUCCES" if status.get('executed') else "ECHEC",
#             "RAISON_IA": reason,
#             "CHEMIN_PREUVES": evidence_path
#         }

#         try:
#             # Chargement de l'existant
#             df_existing = pd.read_excel(self.excel_file)
#             # Ajout de la nouvelle ligne (méthode moderne pandas)
#             df_new = pd.DataFrame([new_data])
#             df_final = pd.concat([df_existing, df_new], ignore_index=True)
            
#             # Sauvegarde
#             df_final.to_excel(self.excel_file, index=False)
#             print(f"📝 Trade enregistré dans Excel : {self.excel_file}")
#             print(f"📂 Preuves visuelles archivées dans : {evidence_path}")
            
#         except PermissionError:
#             print("❌ ERREUR CRITIQUE : FERMEZ LE FICHIER EXCEL S'IL VOUS PLAIT !")
#         except Exception as e:
#             print(f"❌ Erreur Excel : {e}")





import os
import shutil
import pandas as pd
from datetime import datetime
import warnings # <--- AJOUT

class TradeLogger:
    def __init__(self):
        # On ignore les warnings futurs de Pandas pour garder la console propre
        warnings.simplefilter(action='ignore', category=FutureWarning) # <--- AJOUT
        
        self.logs_dir = "logs"
        self.archives_dir = "logs/archives"
        self.excel_file = f"{self.logs_dir}/Journal_Trading_Gemini.xlsx"
        
        if not os.path.exists(self.logs_dir): os.makedirs(self.logs_dir)
        if not os.path.exists(self.archives_dir): os.makedirs(self.archives_dir)
        
        self._init_excel()

    def _init_excel(self):
        if not os.path.exists(self.excel_file):
            # On crée le fichier avec des données vides mais typées pour éviter le warning
            df = pd.DataFrame({
                "DATE": [], "SYMBOL": [], "DIRECTION": [], "CONFIANCE": [], 
                "PRIX_ENTREE": [], "STOP_LOSS": [], "TAKE_PROFIT": [], "LOTS": [], 
                "RESULTAT_EXEC": [], "RAISON_IA": [], "CHEMIN_PREUVES": []
            })
            df.to_excel(self.excel_file, index=False)

    # ... Le reste de la méthode log_trade ne change pas ...
    def log_trade(self, symbol, decision, entry, sl, tp, lot, status, reason, image_sources):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"{timestamp}_{symbol}_{decision}"
        evidence_path = os.path.join(self.archives_dir, folder_name)
        
        try:
            os.makedirs(evidence_path, exist_ok=True)
            for img_path in image_sources:
                if os.path.exists(img_path):
                    shutil.copy(img_path, evidence_path)
        except Exception as e:
            print(f"⚠️ Erreur archivage: {e}")

        new_data = {
            "DATE": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "SYMBOL": symbol,
            "DIRECTION": decision,
            "CONFIANCE": f"{status.get('confidence', 0)}%",
            "PRIX_ENTREE": entry,
            "STOP_LOSS": sl,
            "TAKE_PROFIT": tp,
            "LOTS": lot,
            "RESULTAT_EXEC": "SUCCES" if status.get('executed') else "ECHEC",
            "RAISON_IA": reason,
            "CHEMIN_PREUVES": evidence_path
        }

        try:
            # On charge l'existant
            if os.path.exists(self.excel_file):
                df_existing = pd.read_excel(self.excel_file)
            else:
                df_existing = pd.DataFrame()
            
            # On ajoute la nouvelle ligne
            df_new = pd.DataFrame([new_data])
            
            # Concaténation propre
            if not df_existing.empty:
                df_final = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_final = df_new
            
            df_final.to_excel(self.excel_file, index=False)
            print(f"📝 Trade enregistré dans Excel.")
            print(f"📂 Preuves archivées.")
            
        except PermissionError:
            print("❌ ERREUR : FERMEZ LE FICHIER EXCEL !")
        except Exception as e:
            print(f"❌ Erreur Excel : {e}")