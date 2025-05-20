# mongo_setup.py

import os
from pymongo import MongoClient
import gridfs
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]
fs = gridfs.GridFS(db)
images_col = db["images"]
VALID_LABELS = {"ABL", "ALA", "ANG", "BAF", "BRE", "CHE", "HOT", "SIL"}

local_folder = "images_to_classify"

for fname in os.listdir(local_folder):
    if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    path = os.path.join(local_folder, fname)

    # ⬇️ Extraction automatique du label à partir du nom de fichier
    base_name = os.path.splitext(fname)[0]  # enlève l'extension
    parts = base_name.split("_")
    label_candidate = parts[0].upper()
    ground_truth = label_candidate if label_candidate in VALID_LABELS else None

    with open(path, "rb") as f:
        file_id = fs.put(f, filename=fname)

    doc = {
        "file_id": file_id,
        "filename": fname,
        "ground_truth": ground_truth,  # ✅ Défini automatiquement
        "validated": False,
        "annotations_count": 0
    }

    images_col.insert_one(doc)
    print(f"Uploadé {fname} → ground_truth={ground_truth}")