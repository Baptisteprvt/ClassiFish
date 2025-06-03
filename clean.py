# clear_db.py

from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

# Connexion à MongoDB
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

def list_collections():
    return db.list_collection_names()

def clear_collection(col_name):
    confirmation = input(f"⚠️ Confirmer suppression de TOUS les documents dans '{col_name}' ? (oui/non) : ").strip().lower()
    if confirmation == "oui":
        result = db[col_name].delete_many({})
        print(f"✅ {result.deleted_count} documents supprimés dans '{col_name}'.")
    else:
        print("❌ Suppression annulée.")

def clear_database():
    collections = list_collections()
    print("\n📁 Collections trouvées :", ", ".join(collections))
    
    confirmation = input("\n⚠️ Confirmer suppression TOTALE de TOUTES les données ? (oui/non) : ").strip().lower()
    if confirmation != "oui":
        print("❌ Suppression annulée.")
        return

    for col in collections:
        deleted = db[col].delete_many({})
        print(f"🗑️ {col} : {deleted.deleted_count} documents supprimés.")

    print("\n✅ Base vidée avec succès.")

if __name__ == "__main__":
    print("=== 🧼 NETTOYAGE DE LA BASE DE DONNÉES ===")
    print(f"Base : {db.name}")
    mode = input("\n🔘 Choisir le mode :\n 1 - Vider toute la base\n 2 - Vider une collection spécifique\nVotre choix (1/2) : ").strip()

    if mode == "1":
        clear_database()
    elif mode == "2":
        collections = list_collections()
        print("\n📂 Collections disponibles :")
        for i, name in enumerate(collections):
            print(f"  {i+1}. {name}")
        choix = input("Entrez le nom exact de la collection à nettoyer : ").strip()
        if choix in collections:
            clear_collection(choix)
        else:
            print("❌ Collection non trouvée.")
    else:
        print("❌ Choix invalide.")
