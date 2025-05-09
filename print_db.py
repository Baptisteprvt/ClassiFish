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

def print_users():
    print("\n=== 🧑 UTILISATEURS ===\n")
    users = list(users_col.find())
    if not users:
        print("Aucun utilisateur trouvé.")
        return

    for user in users:
        print(f"🔹 ID : {user['user_id']}")
        print(f"   Annotations totales : {user.get('annotations_total', 0)}")
        print(f"   Annotations correctes : {user.get('annotations_correct', 0)}")
        accuracy = user.get("accuracy", 0.0)
        print(f"   Précision globale : {accuracy * 100:.2f}%")
        print(f"   Tests annotés : {user.get('test_annotations', 0)}")
        test_acc = user.get("test_accuracy", 0.0)
        print(f"   Précision sur tests : {test_acc * 100:.2f}%")
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
        print(f"   Ground Truth : {img.get('ground_truth', '❌ Aucune (image normale)')}")
        print(f"   Annotations : {img.get('annotations_count', 0)}")
        print("-" * 40)

def print_annotations():
    print("\n=== 📝 ANNOTATIONS ===\n")
    annotations = list(annotations_col.find())
    if not annotations:
        print("Aucune annotation trouvée.")
        return

    for ann in annotations:
        print(f"📝 Utilisateur : {ann['user_id']} | Image : {ann['image']}")
        print(f"   Espèce choisie : {ann['label']}")
        is_test = ann.get("is_test", False)
        print(f"   Type : {'🧪 Test' if is_test else '📌 Normale'}")
        if is_test:
            expected = ann.get("expected_label", "??")
            correct = ann["label"] == expected
            print(f"   Attendu : {expected} | {'✅ Correct' if correct else '❌ Incorrect'}")
        print(f"   Date : {ann.get('timestamp', 'N/A')}")
        print("-" * 40)

if __name__ == "__main__":
    print("🔍 CONNECTÉ À LA BASE DE DONNÉES 🔍")
    print("Nom de la base :", db.name)
    print("=" * 60)

    print_users()
    print_images()
    print_annotations()

    print("\n✅ FIN DE L’AFFICHAGE\n")