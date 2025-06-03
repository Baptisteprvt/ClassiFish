from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

# Connexion à MongoDB
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

# Collection des utilisateurs
users_col = db["users"]  # Adapte si ta collection a un autre nom

# Mise à jour de la confiance à 101% pour Aude
result = users_col.update_one(
    {"user_id": "Aude"},  # critère de recherche
    {"$set": {"test_accuracy": 1.01}}  # modification
)

if result.matched_count == 0:
    print("❌ Utilisateur 'Aude' introuvable.")
else:
    print("✅ test_accuracy mis à jour à 101% pour Aude.")
