# # mongo_setup.py

# import os
# from pymongo import MongoClient
# import gridfs
# from dotenv import load_dotenv

# load_dotenv()

# client = MongoClient(os.getenv("ATLAS_URI"))
# db = client[os.getenv("DB_NAME")]
# fs = gridfs.GridFS(db)
# images_col = db["images"]
# VALID_LABELS = {"ABL", "ALA", "ANG", "BAF", "BRE", "CHE", "HOT", "SIL"}

# local_folder = "images_to_classify"

# for fname in os.listdir(local_folder):
#     if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
#         continue

#     path = os.path.join(local_folder, fname)

#     # ⬇️ Extraction automatique du label à partir du nom de fichier
#     base_name = os.path.splitext(fname)[0]  # enlève l'extension
#     parts = base_name.split("_")
#     label_candidate = parts[0].upper()
#     ground_truth = label_candidate if label_candidate in VALID_LABELS else None

#     with open(path, "rb") as f:
#         file_id = fs.put(f, filename=fname)

#     doc = {
#         "file_id": file_id,
#         "filename": fname,
#         "ground_truth": ground_truth,  # ✅ Défini automatiquement
#         "validated": False,
#         "annotations_count": 0
#     }

#     images_col.insert_one(doc)
#     print(f"Uploadé {fname} → ground_truth={ground_truth}")

from pymongo import MongoClient
from ultralytics import YOLO
from PIL import Image
from io import BytesIO
import gridfs
import base64
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]
fs = gridfs.GridFS(db)
model = YOLO(r"backend/best.pt")

images_col = db["images"]
ai_predictions_col = db["ai_predictions"]

for img_doc in images_col.find():
    if ai_predictions_col.find_one({"image_id": str(img_doc["_id"])}):
        continue  # Skip si déjà traité

    try:
        img_data = fs.get(img_doc["file_id"]).read()
        img = Image.open(BytesIO(img_data))
        result = model(img, verbose=False)[0]
        if result.probs:
            predicted_label = result.names[result.probs.top1]
            ai_predictions_col.insert_one({
                "image_id": str(img_doc["_id"]),
                "predicted_label": predicted_label
            })
    except Exception as e:
        print(f"Erreur image {img_doc['_id']}: {e}")
