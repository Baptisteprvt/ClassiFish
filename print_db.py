# print_db.py

from pymongo import MongoClient
import os
from dotenv import load_dotenv
from pprint import pprint

# Charger les variables d'environnement
load_dotenv()

# Connexion à MongoDB
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

users_col = db["users"]
images_col = db["images"]
annotations_col = db["annotations"]
votes_col = db["votes"]

def print_users():
    print("\n=== 🧑 UTILISATEURS ===\n")
    users = list(users_col.find())
    if not users:
        print("Aucun utilisateur trouvé.")
        return

    for user in users:
        print(f"🔹 ID : {user['user_id']}")
        print(f"   Fiabilité globale : {user.get('accuracy', 0.0) * 100:.2f}%")
        print(f"   Précision sur tests : {user.get('test_accuracy', 0.0) * 100:.2f}%")
        print(f"   Annotations totales : {user.get('annotations_total', 0)}")
        print(f"   Tests annotés : {user.get('test_annotations', 0)}")
        print("-" * 40)

def print_images():
    print("\n=== 📷 IMAGES ===\n")
    images = list(images_col.find())
    if not images:
        print("Aucune image trouvée.")
        return

    for img in images:
        print(f"🖼️ ID : {img['_id']}")
        print(f"   Fichier : {img.get('filename')}")
        print(f"   Validée : {'✅' if img.get('validated') else '❌'}")
        print(f"   Ground Truth : {img.get('ground_truth', '❌ Non validée')}")
        print(f"   Votes reçus : {img.get('votes', 0)}")
        print(f"   Annotations : {img.get('annotations_count', 0)}")
        print("-" * 40)

# def print_annotations():
#     print("\n=== 📝 ANNOTATIONS ===\n")
#     annotations = list(annotations_col.find())
#     if not annotations:
#         print("Aucune annotation trouvée.")
#         return

#     for ann in annotations:
#         print(f"📝 Utilisateur : {ann['user_id']} | Image : {ann['image']}")
#         print(f"   Espèce choisie : {ann['label']}")
#         is_test = ann.get("is_test", False)
#         print(f"   Type : {'🧪 Test' if is_test else '📌 Normale'}")
#         if is_test:
#             expected = ann.get("expected_label", "??")
#             correct = ann["label"] == expected
#             print(f"   Attendu : {expected} | {'✅ Correct' if correct else '❌ Incorrect'}")
#         print(f"   Date : {ann.get('timestamp', 'N/A')}")
#         print("-" * 40)

def print_votes():
    print("\n=== ⚖️ VOTES (POUR IMAGES NON VALIDÉES) ===\n")
    votes = list(votes_col.find())
    if not votes:
        print("Aucun vote trouvé.")
        return

    from collections import defaultdict

    image_votes = defaultdict(list)

    for v in votes:
        image_votes[v["image_id"]].append({
            "user": v["user_id"],
            "label": v["label"],
            "poids": f"{v['weight'] * 100:.1f}%",
            "date": v.get("timestamp", "N/A")
        })

    for image_id, vote_list in image_votes.items():
        print(f"📌 Image ID : {image_id}")
        print("   └── Votes :")
        for v in vote_list:
            print(f"      - [{v['user']}] ➤ '{v['label']}' | Poids : {v['poids']} | Date : {v['date']}")
        print("-" * 40)

def print_ai_predictions():
    print("\n=== 🤖 PRÉDICTIONS DE L'IA ===\n")
    ai_predictions_col = db["ai_predictions"]
    predictions = list(ai_predictions_col.find())
    
    if not predictions:
        print("Aucune prédiction IA trouvée.")
        return

    for pred in predictions:
        print(f"🧠 Prédiction par l'IA :")
        print(f"   Image ID : {pred.get('image_id')}")
        print(f"   Utilisateur : {pred.get('user_id')}")
        print(f"   Étiquette prédite : {pred.get('predicted_label')}")
        print(f"   Date de prédiction : {pred.get('timestamp', 'N/A')}")
        print("-" * 40)


if __name__ == "__main__":
    print("🔍 CONNECTÉ À LA BASE DE DONNÉES 🔍")
    print("Nom de la base :", db.name)
    print("=" * 60)

    print_users()
    # print_ai_predictions()
    # print_images()
    # print_votes()

    print("\n✅ FIN DE L’AFFICHAGE\n")