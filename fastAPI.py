from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os

# --- Charger .env ---
load_dotenv()
ATLAS_URI = os.getenv("ATLAS_URI")
DB_NAME = os.getenv("DB_NAME")

if not ATLAS_URI or not DB_NAME:
    raise RuntimeError("Définir ATLAS_URI et DB_NAME dans .env")

# --- Connexion MongoDB ---
client = MongoClient(ATLAS_URI)
db = client[DB_NAME]
images_col = db["images"]
annotations_col = db["annotations"]

# --- Paramètre utilisateur ---
user_id = "ea"

# --- Images annotées par l'utilisateur ---
annotated_ids = annotations_col.distinct("image", {"user_id": user_id})
nb_annotated = len(annotated_ids)

# --- Images encore à annoter pour l'utilisateur ---
nb_remaining = images_col.count_documents({
    "validated": False,
    "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
})

# --- Total d’images dans la base ---
total_images = images_col.count_documents({})

# --- Images marquées comme non reconnaissables ---
nb_unrecognizable = annotations_col.count_documents({
    "user_id": user_id,
    "label": "UNRECOGNIZABLE"
})

# --- Affichage ---
print(f"📊 Statistiques pour l'utilisateur '{user_id}'")
print(f"🔢 Total d'images dans la base : {total_images}")
print(f"✍️  Images annotées par {user_id} : {nb_annotated}")
print(f"📛 Dont 'non reconnaissables' : {nb_unrecognizable}")
print(f"📷 Images restantes à annoter : {nb_remaining}")
