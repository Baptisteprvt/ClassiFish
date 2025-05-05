from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()  # charge .env

client = MongoClient(os.getenv("ATLAS_URI"))
db_name = os.getenv("DB_NAME")
if not db_name:
    raise ValueError("DB_NAME is not set in .env")
db = client[db_name]

# Suppression des anciennes images (facultatif si tu veux une base propre)
db.images.delete_many({})

# Ajout des nouvelles
image_dir = "frontend/images_to_classify"
for img in os.listdir(image_dir):
    db.images.insert_one({
        "image": f"{image_dir}/{img}",
        "ground_truth": None,
        "validated": False,
        "annotations_count": 0,
        "votes": 0
    })
