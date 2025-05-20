# clean_db.py

from pymongo import MongoClient
import gridfs
from dotenv import load_dotenv
import os

load_dotenv()

# Connexion à la base de données
client = MongoClient(os.getenv("ATLAS_URI"))
db_name = os.getenv("DB_NAME")
if not db_name:
    raise ValueError("DB_NAME non défini dans .env")

db = client[db_name]

# Suppression des collections standard
collections = ["images", "annotations", "users", "ai_predictions", "votes"]
for col in collections:
    if col in db.list_collection_names():
        db.drop_collection(col)
        print(f"🗑️ Collection '{col}' supprimée.")

# Suppression des fichiers GridFS (fs.files & fs.chunks)
fs = gridfs.GridFS(db)
fs_files = db["fs.files"]
fs_chunks = db["fs.chunks"]

# Supprime les chunks en premier
if "fs.chunks" in db.list_collection_names():
    db.drop_collection("fs.chunks")
    print("🗑️ Collection 'fs.chunks' supprimée.")

# Puis les fichiers
if "fs.files" in db.list_collection_names():
    db.drop_collection("fs.files")
    print("🗑️ Collection 'fs.files' supprimée.")

print("✅ Base de données nettoyée avec succès.")
# from pymongo import MongoClient
# from dotenv import load_dotenv
# import os

# load_dotenv()
# print("🔍 Chargement du .env")
# print("ATLAS_URI =", os.getenv("ATLAS_URI"))
# print("DB_NAME =", os.getenv("DB_NAME"))

# uri = os.getenv("ATLAS_URI")
# client = MongoClient(uri)

# # Tester la connexion
# try:
#     client.admin.command('ping')
#     print("✅ Connexion réussie !")
# except Exception as e:
#     print("❌ Erreur de connexion :", e)