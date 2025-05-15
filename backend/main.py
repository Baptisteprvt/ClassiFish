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
import streamlit as st

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
votes_col = db["votes"]  # ✅ Nouvelle collection
fs = gridfs.GridFS(db)

# --- Indexes ---
images_col.create_index("validated")
annotations_col.create_index([("image", 1), ("user_id", 1)])
users_col.create_index("user_id", unique=True)
votes_col.create_index([("image_id", 1), ("user_id", 1)])

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

app = FastAPI()

# --- Routes ---

import random

@app.get("/image")
def get_image(user_id: str):
    """
    Récupère :
    1. Si < 30 tests : priorité aux tests disponibles
    2. Sinon : 1 chance sur 10 d'avoir un test → sinon image normale
    """

    max_test = 5
    test_chance = 0.1  # 10% de chance d'avoir un test après les 30 premiers

    annotated_ids = [
        ann["image"] for ann in annotations_col.find({"user_id": user_id}, {"image": 1})
    ]

    # Compte combien d'annotations sont des tests
    test_annotations = list(annotations_col.find({
        "user_id": user_id,
        "is_test": True
    }))
    nb_test_done = len(test_annotations)

    # --- CAS : Utilisateur n'a pas encore fait ses 30 tests ---
    if nb_test_done < max_test:
        # Cherche une image test non annotée
        pipeline = [
            {"$match": {
                "ground_truth": {"$ne": None},
                "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
            }},
            {"$sample": {"size": 1}}
        ]
        test_img = list(images_col.aggregate(pipeline))
        if test_img:
            img_doc = test_img[0]
            st.session_state.is_test = True
        else:
            # Pas d'image test dispo → image normale
            pipeline = [
                {"$match": {
                    "validated": False,
                    "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
                }},
                {"$sample": {"size": 1}}
            ]
            normal_img = list(images_col.aggregate(pipeline))
            if not normal_img:
                raise HTTPException(404, "Aucune image disponible.")
            img_doc = normal_img[0]

    # --- CAS : Utilisateur a déjà fait 30 tests → rarement un test ---
    else:
        # Tirage au sort : 1/10 chance de recevoir un test
        if random.random() <= test_chance:
            pipeline = [
                {"$match": {
                    "ground_truth": {"$ne": None},
                    "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
                }},
                {"$sample": {"size": 1}}
            ]
            test_img = list(images_col.aggregate(pipeline))
            if test_img:
                img_doc = test_img[0]
                st.session_state.is_test = True
            else:
                # Aucun test dispo → image normale
                pipeline = [
                    {"$match": {
                        "validated": False,
                        "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
                    }},
                    {"$sample": {"size": 1}}
                ]
                normal_img = list(images_col.aggregate(pipeline))
                if not normal_img:
                    raise HTTPException(404, "Aucune image disponible.")
                img_doc = normal_img[0]

        # 9/10 du temps → image normale
        else:
            pipeline = [
                {"$match": {
                    "validated": False,
                    "_id": {"$nin": [ObjectId(i) for i in annotated_ids]}
                }},
                {"$sample": {"size": 1}}
            ]
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

    return {
        "image_id": str(img_doc["_id"]),
        "image": base64.b64encode(img_b).decode("utf-8"),
        "is_test": bool(img_doc.get("ground_truth")) and (
            nb_test_done < max_test or random.random() <= test_chance
        ),
        "expected_label": img_doc.get("ground_truth")
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