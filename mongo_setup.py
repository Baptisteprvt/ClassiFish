import os
from pymongo import MongoClient
import gridfs
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

fs = gridfs.GridFS(db)
images_col = db["images"]

local_folder = "images_to_classify"
for fname in os.listdir(local_folder):
    if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
        continue
    path = os.path.join(local_folder, fname)
    with open(path, "rb") as f:
        file_id = fs.put(f, filename=fname, contentType="image/jpeg")
    images_col.insert_one({
        "file_id": file_id,
        "filename": fname,
        "ground_truth": None,
        "validated": False,
        "annotations_count": 0,
        "votes": 0
    })
    print(f"Uploadé {fname} → file_id={file_id}")
