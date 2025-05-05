import os
import base64
from io import BytesIO
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()
ATLAS_URI = os.getenv("ATLAS_URI")
DB_NAME   = os.getenv("DB_NAME")
if not ATLAS_URI or not DB_NAME:
    raise RuntimeError("Définir ATLAS_URI et DB_NAME dans .env")

# Connexion à MongoDB Atlas
client = MongoClient(ATLAS_URI, serverSelectionTimeoutMS=5000)
try:
    client.server_info()
except Exception as e:
    raise RuntimeError(f"Échec connexion MongoDB : {e}")

db = client[DB_NAME]
images_col      = db["images"]
annotations_col = db["annotations"]
users_col       = db["users"]

# Création d'index
images_col.create_index("validated")
annotations_col.create_index([("image", 1), ("user_id", 1)])
users_col.create_index("user_id", unique=True)

# Schémas Pydantic
class AnnotationRequest(BaseModel):
    image_id: str
    user_id: str
    label: str
    prediction_ia: str

class VoteRequest(BaseModel):
    image_id: str
    user_id: str
    vote: bool

class UserStats(BaseModel):
    user_id: str
    annotations_total: int
    annotations_correct: int
    accuracy: float

app = FastAPI()

@app.get("/image")
def get_image():
    """Récupère une image non validée (Base64)."""
    img_doc = images_col.find_one({"validated": False})
    if not img_doc:
        raise HTTPException(404, "Pas d'image disponible")
    path = img_doc["image"]
    try:
        with open(path, "rb") as f:
            img_b = f.read()
    except FileNotFoundError:
        raise HTTPException(404, "Fichier image introuvable")
    img_b64 = base64.b64encode(img_b).decode("utf-8")
    return {"image_id": str(img_doc["_id"]), "image": img_b64}

@app.post("/annotations")
def save_annotation(ann: AnnotationRequest):
    """Enregistre une annotation et met à jour stats image & user."""
    img_oid = ObjectId(ann.image_id)
    img_doc = images_col.find_one({"_id": img_oid})
    if not img_doc:
        raise HTTPException(404, "Image introuvable")
    # insérer annotation
    ann_doc = {
        "image": ann.image_id,
        "user_id": ann.user_id,
        "label": ann.label,
        "prediction_ia": ann.prediction_ia,
        "timestamp": datetime.utcnow()
    }
    annotations_col.insert_one(ann_doc)
    # mettre à jour compteur image
    images_col.update_one({"_id": img_oid}, {"$inc": {"annotations_count": 1}})
    # mettre à jour stats user
    gt = img_doc.get("ground_truth")
    correct = (gt == ann.label) if gt else False
    user = users_col.find_one({"user_id": ann.user_id})
    if user:
        total = user.get("annotations_total", 0) + 1
        correct_count = user.get("annotations_correct", 0) + (1 if correct else 0)
    else:
        total = 1
        correct_count = 1 if correct else 0
    accuracy = (correct_count / total) * 100
    users_col.update_one(
        {"user_id": ann.user_id},
        {"$set": {
            "annotations_total": total,
            "annotations_correct": correct_count,
            "accuracy": accuracy
        }},
        upsert=True
    )
    return {"message": "Annotation enregistrée"}

@app.post("/vote")
def record_vote(v: VoteRequest):
    """Enregistre un vote de confirmation IA."""
    img_oid = ObjectId(v.image_id)
    if not images_col.find_one({"_id": img_oid}):
        raise HTTPException(404, "Image introuvable")
    if v.vote:
        images_col.update_one({"_id": img_oid}, {"$inc": {"votes": 1}})
    return {"message": "Vote enregistré"}

@app.get("/user_stats/{user_id}", response_model=UserStats)
def get_user_stats(user_id: str):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    return UserStats(
        user_id=user["user_id"],
        annotations_total=user.get("annotations_total", 0),
        annotations_correct=user.get("annotations_correct", 0),
        accuracy=user.get("accuracy", 0.0)
    )