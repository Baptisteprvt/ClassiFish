import os
from io import BytesIO
from datetime import datetime
from typing import Optional
import base64
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
import gridfs
from dotenv import load_dotenv
from collections import defaultdict
import random
from PIL import Image
import random
from ultralytics import YOLO

# --- Configuration ---
load_dotenv()
ATLAS_URI = os.getenv("ATLAS_URI")
DB_NAME = os.getenv("DB_NAME")
SEUIL_CONFIANCE_MIN = 0.75

if not ATLAS_URI or not DB_NAME:
    raise RuntimeError("Définir ATLAS_URI et DB_NAME dans .env")

# --- Connexion MongoDB ---
client = MongoClient(ATLAS_URI, serverSelectionTimeoutMS=5000)
try:
    client.server_info()
except Exception as e:
    raise RuntimeError(f"Échec connexion MongoDB : {e}")

db = client[DB_NAME]
images_col = db["images"]
annotations_col = db["annotations"]
users_col = db["users"]
votes_col = db["votes"]
fs = gridfs.GridFS(db)

# --- Nouvelle collection pour les prédictions IA ---
ai_predictions_col = db["ai_predictions"]

# --- Indexes ---
images_col.create_index("validated")
annotations_col.create_index([("image", 1), ("user_id", 1)])
users_col.create_index("user_id", unique=True)
votes_col.create_index([("image_id", 1), ("user_id", 1)])
ai_predictions_col.create_index([("image_id", 1), ("user_id", 1)])

# --- Schémas Pydantic ---
class AnnotationRequest(BaseModel):
    image_id: str
    user_id: str
    label: str
    is_test: bool = False
    expected_label: Optional[str] = None

class VoteRequest(BaseModel):
    image_id: str
    user_id: str
    vote: bool

class UserStats(BaseModel):
    user_id: str
    annotations_total: int
    annotations_correct: int
    accuracy: float

class UserDetails(UserStats):
    test_annotations: int
    test_correct: int
    test_accuracy: float

# --- Chargement du modèle IA ---
app = FastAPI()
model = YOLO("best.pt")
labels = ["ABL", "ALA", "ANG", "BAF", "BRE", "CHE", "HOT", "SIL"]

# --- Fonction de prédiction ---
def predict_image(img_pil: Image.Image):
    """
    Prédit l'espèce de poisson à partir d'une image PIL avec YOLOv8
    """
    results = model(img_pil, verbose=False)  # Désactive les logs verbeux
    for result in results:
        probs = result.probs  # Probabilités des classes
        if probs is not None:
            class_id = probs.top1  # Meilleure classe
            return labels[class_id]
    return None

# --- Routes ---

@app.get("/image")
def get_image(user_id: str):
    max_test = 8
    test_chance = 0.1

    annotated_ids = [ann["image"] for ann in annotations_col.find({"user_id": user_id}, {"image": 1})]
    nb_test_done = annotations_col.count_documents({"user_id": user_id, "is_test": True})

    if nb_test_done < max_test:
        pipeline = [
            {"$match": {
                "ground_truth": {"$ne": None,     # ≠ null / None
                                 "$ne": ""},

                "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
            }},
            {"$sample": {"size": 1}}
        ]
        test_img = list(images_col.aggregate(pipeline))
        if test_img:
            img_doc = test_img[0]
        else:
            pipeline = [{"$match": {"validated": False, "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}}}, {"$sample": {"size": 1}}]
            normal_img = list(images_col.aggregate(pipeline))
            if not normal_img:
                raise HTTPException(404, "Aucune image disponible.")
            img_doc = normal_img[0]
    else:
        if random.random() <= test_chance:
            pipeline = [
                {"$match": {
                    "ground_truth": {"$ne": None,     # ≠ null / None
                                     "$ne": ""},
                    "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
                }},
                {"$sample": {"size": 1}}
            ]
            test_img = list(images_col.aggregate(pipeline))
            if test_img:
                img_doc = test_img[0]
            else:
                pipeline = [{"$match": {"validated": False, "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}}}, {"$sample": {"size": 1}}]
                normal_img = list(images_col.aggregate(pipeline))
                if not normal_img:
                    raise HTTPException(404, "Aucune image disponible.")
                img_doc = normal_img[0]
        else:
            pipeline = [{"$match": {"validated": False, "ground_truth": {"$eq": None, "$eq" : ""}, "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}}}, {"$sample": {"size": 1}}]
            normal_img = list(images_col.aggregate(pipeline))
            if not normal_img:
                raise HTTPException(404, "Aucune image disponible.")
            img_doc = normal_img[0]

    try:
        grid_out = fs.get(img_doc["file_id"])
        img_b = grid_out.read()
    except gridfs.errors.NoFile:
        images_col.delete_one({"_id": img_doc["_id"]})
        raise HTTPException(500, "Fichier introuvable")

    is_test = bool(img_doc.get("ground_truth")) and (nb_test_done < max_test or random.random() <= test_chance)
    encoded_image = base64.b64encode(img_b).decode("utf-8")

    # Prédiction IA si c'est un test
    ai_prediction = None
    pil_image = Image.open(BytesIO(base64.b64decode(encoded_image)))
    ai_prediction = predict_image(pil_image)
    ai_predictions_col.update_one(
        {"image_id": str(img_doc["_id"]), "user_id": user_id},
        {"$setOnInsert": {
            "image_id": str(img_doc["_id"]),
            "user_id": user_id,
            "predicted_label": ai_prediction,
            "timestamp": datetime.utcnow()
        }},
        upsert=True
    )

    return {
        "image_id": str(img_doc["_id"]),
        "image": encoded_image,
        "is_test": is_test,
        "expected_label": img_doc.get("ground_truth"),
        "ai_prediction": ai_prediction  # Non transmis à l'utilisateur
    }


@app.post("/annotations")
def save_annotation(ann: AnnotationRequest):
    img_oid = ObjectId(ann.image_id)
    img_doc = images_col.find_one({"_id": img_oid})
    if not img_doc:
        raise HTTPException(404, "Image introuvable")

    annotations_col.insert_one({
        "image": ann.image_id,
        "user_id": ann.user_id,
        "label": ann.label,
        "timestamp": datetime.utcnow(),
        "is_test": getattr(ann, "is_test", False),
        "expected_label": getattr(ann, "expected_label", None)
    })

    user = users_col.find_one({"user_id": ann.user_id})
    if ann.is_test:
        if not user:
            user = {
                "user_id": ann.user_id,
                "test_annotations": 0,
                "test_correct": 0,
                "test_accuracy": 0.0
            }
        total = user.get("test_annotations", 0) + 1
        correct_count = user.get("test_correct", 0) + (1 if ann.label == ann.expected_label else 0)
        accuracy = correct_count / total if total > 0 else 0.0
        users_col.update_one(
            {"user_id": ann.user_id},
            {"$set": {
                "test_annotations": total,
                "test_correct": correct_count,
                "test_accuracy": accuracy
            }},
            upsert=True
        )

    images_col.update_one({"_id": img_oid}, {"$inc": {"annotations_count": 1}})
    return {"message": "Annotation enregistrée"}


@app.get("/ai-stats")
def get_ai_stats(user_id: str):
    user_tests = list(annotations_col.find({
        "user_id": user_id,
        "is_test": True
    }))

    if not user_tests:
        raise HTTPException(404, "Pas d'annotations test trouvées.")

    user_correct = 0
    ai_correct = 0

    for test in user_tests:
        expected = test.get("expected_label")
        user_label = test.get("label")
        pred = ai_predictions_col.find_one({
            "image_id": test["image"],
            "user_id": user_id
        })
        ai_label = pred.get("predicted_label") if pred else None

        if user_label == expected:
            user_correct += 1
        if ai_label == expected:
            ai_correct += 1

    total = len(user_tests)
    return {
        "user_score": user_correct / total,
        "ai_score": ai_correct / total,
        "total": total
    }


@app.post("/vote_annotation")
def vote_annotation(data: dict):
    """
    Un utilisateur vote pour une espèce → son vote est pesé par sa fiabilité.
    Si seuil atteint → validation automatique de l'image.
    """
    image_id = data.get("image_id")
    user_id = data.get("user_id")
    label = data.get("label")

    if not image_id or not user_id or not label:
        raise HTTPException(400, "Données incomplètes.")

    # Vérifie l'utilisateur
    user = users_col.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé.")

    reliability = user.get("test_accuracy", 0.0)
    if reliability < SEUIL_CONFIANCE_MIN:  # 🚫 Seuil minimum
        raise HTTPException(403, "Fiabilité insuffisante (<75%).")

    # Vérifie l'image
    image = images_col.find_one({"_id": ObjectId(image_id)})
    if not image:
        raise HTTPException(404, "Image introuvable.")

    # Enregistre le vote
    vote_doc = {
        "image_id": image_id,
        "user_id": user_id,
        "label": label,
        "timestamp": datetime.utcnow(),
        "weight": reliability
    }
    votes_col.insert_one(vote_doc)

    # Calcule les votes cumulés
    votes = list(votes_col.find({"image_id": image_id}))
    label_weights = defaultdict(float)

    for v in votes:
        label_weights[v["label"]] += v["weight"]

    total_weight = sum(label_weights.values())

    # Seuil : somme des poids ≥ 10 (ex: 15 votes * 0.8 > 10)
    if total_weight >= 10:
        best_label = max(label_weights, key=label_weights.get)
        best_score = label_weights[best_label]
        confidence = best_score / total_weight

        # Rafraîchissez l'étiquette si la certitude change significativement
        if confidence > 0.8:  # Seuil de certitude
            images_col.update_one(
                {"_id": ObjectId(image_id)},
                {"$set": {"ground_truth": best_label, "validated": True}}
            )
            return {
                "message": f"Image validée automatiquement : {best_label}",
                "ground_truth": best_label,
                "confidence_ratio": confidence
            }
        elif confidence < 0.6:  # Seuil de confiance bas
            images_col.update_one(
                {"_id": ObjectId(image_id)},
                {"$unset": {"ground_truth": ""}}
            )
            return {
                "message": f"Confiance insuffisante pour l'image : {best_label}",
                "ground_truth": None,
                "confidence_ratio": confidence
            }
        

    return {"message": "Vote enregistré.", "total_weight": total_weight}

@app.get("/user_details/{user_id}")
def get_user_details(user_id: str):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Utilisateur non trouvé")
    return UserDetails(
        user_id=user["user_id"],
        annotations_total=user.get("annotations_total", 0),
        annotations_correct=user.get("annotations_correct", 0),
        accuracy=user.get("accuracy", 0.0),
        test_annotations=user.get("test_annotations", 0),
        test_correct=user.get("test_correct", 0),
        test_accuracy=user.get("test_accuracy", 0.0)
    )

@app.get("/stats")
def get_stats(user_id: str):
    annotated_ids = [
        ann["image"] for ann in annotations_col.find({"user_id": user_id}, {"image": 1})
    ]
    remaining = images_col.count_documents({
        "validated": False,
        "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
    })
    return {"remaining_images": remaining}

@app.post("/login-or-register")
def login_or_register(data: dict):
    user_id = data.get("user_id")
    password = data.get("password")

    if not user_id or not password:
        raise HTTPException(400, "Nom d'utilisateur et mot de passe requis.")

    user = users_col.find_one({"user_id": user_id})

    if user:
        if user.get("password") != password:
            raise HTTPException(401, "Mot de passe incorrect.")
        return {"exists": True, "message": "Authentifié"}
    else:
        users_col.insert_one({
            "user_id": user_id,
            "password": password,
            "test_annotations": 0,
            "test_correct": 0,
            "test_accuracy": 0.0
        })
        return {"exists": False, "message": "Nouvel utilisateur créé"}
    
@app.get("/comparison")
def get_comparison(user_id: str):
    # Récupère toutes les annotations de test de l'utilisateur
    user_tests = list(annotations_col.find({
        "user_id": user_id
    }))

    if not user_tests:
        raise HTTPException(404, "Aucune annotation test trouvée.")

    comparisons = []
    for test in user_tests:
        image_id = test["image"]
        expected = test.get("expected_label")
        user_label = test.get("label")

        # Recherche la prédiction IA associée
        ai_pred = ai_predictions_col.find_one({
            "image_id": image_id,
            "user_id": user_id
        })

        ai_label = ai_pred.get("predicted_label") if ai_pred else None

        comparisons.append({
            "image_id": image_id,
            "attendu": expected,
            "utilisateur": user_label,
            "ia": ai_label,
            "correct_utilisateur": user_label == expected,
            "correct_ia": ai_label == expected if ai_label and expected else None
        })

    return {"results": comparisons}