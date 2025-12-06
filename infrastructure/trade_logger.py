import pandas as pd
import os
import shutil
from datetime import datetime

class TradeLogger:
    def __init__(self):
        # 1. Configuration des dossiers
        self.base_log_dir = "logs"
        self.archive_dir = os.path.join(self.base_log_dir, "archives_charts")
        self.csv_path = os.path.join(self.base_log_dir, "journal_trading.csv")
        
        # Création de l'arborescence
        if not os.path.exists(self.base_log_dir):
            os.makedirs(self.base_log_dir)
        if not os.path.exists(self.archive_dir):
            os.makedirs(self.archive_dir)
            
        # 2. Création du CSV avec colonnes images
        if not os.path.exists(self.csv_path):
            df = pd.DataFrame(columns=[
                "Date", "Symbol", "Action", "Confidence", 
                "Price", "SL", "TP", "Lot", "Reason", "ATR_Used",
                "Chart_W1", "Chart_D1", "Chart_H4" # Liens vers les archives
            ])
            df.to_csv(self.csv_path, index=False)

    def _archive_images(self, symbol, original_paths):
        """
        Déplace les images du buffer vers l'archive avec un Timestamp unique.
        Retourne les nouveaux chemins.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_names = []

        for path in original_paths:
            if os.path.exists(path):
                # Ex: charts_buffer/EURUSD_H4_Tactical.png
                filename = os.path.basename(path)
                # Nouveau nom : EURUSD_H4_Tactical_20231130_120000.png
                name_part, ext = os.path.splitext(filename)
                new_name = f"{name_part}_{timestamp}{ext}"
                dest_path = os.path.join(self.archive_dir, new_name)
                
                # Déplacement (Move) : Vide le buffer automatiquement
                shutil.move(path, dest_path)
                archived_names.append(new_name)
            else:
                archived_names.append("Missing")
        
        # On s'assure d'avoir 3 entrées (W1, D1, H4) même si erreur
        while len(archived_names) < 3:
            archived_names.append("N/A")
            
        return archived_names

    def log_decision(self, symbol, decision_json, price, sl, tp, lot, execution_msg, image_paths_buffer):
        """Enregistre tout : Décision + Déplacement Images + CSV"""
        
        # 1. Archivage des images
        archived_files = self._archive_images(symbol, image_paths_buffer)
        
        # 2. Préparation de la ligne CSV
        new_row = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Symbol": symbol,
            "Action": decision_json.get('decision'),
            "Confidence": decision_json.get('confidence'),
            "Price": price,
            "SL": sl,
            "TP": tp,
            "Lot": lot,
            "Reason": f"{execution_msg} | {decision_json.get('reason')}",
            "ATR_Used": decision_json.get("atr_value", 0),
            "Chart_W1": archived_files[0],
            "Chart_D1": archived_files[1],
            "Chart_H4": archived_files[2]
        }
        
        # 3. Écriture
        df = pd.DataFrame([new_row])
        # On gère l'en-tête pour ne pas le réécrire
        header = not os.path.exists(self.csv_path)
        df.to_csv(self.csv_path, mode='a', header=header, index=False)
        
        print(f"📝 Log & Archives sauvegardés pour {symbol}")