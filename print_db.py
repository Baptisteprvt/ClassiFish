# print_db.py

from pymongo import MongoClient
from dotenv import load_dotenv
from pprint import pprint
import os

# Charger les variables d'environnement
load_dotenv()

# Connexion à MongoDB
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

def print_database_summary():
    print("🔍 CONNECTÉ À LA BASE DE DONNÉES 🔍")
    print("Nom de la base :", db.name)
    print("=" * 60)

    collections = db.list_collection_names()
    if not collections:
        print("❌ Aucune collection trouvée dans la base.")
        return

    for col_name in collections:
        collection = db[col_name]
        print(f"\n📁 COLLECTION : {col_name.upper()} ({collection.count_documents({})} documents)")
        print("-" * 60)

        cursor = collection.find().limit(5)
        for doc in cursor:
            pprint(doc)
            print("-" * 40)

if __name__ == "__main__":
    print_database_summary()
    print("\n✅ FIN DE L’AFFICHAGE\n")
