# import streamlit as st
# from PIL import Image
# from pathlib import Path
# from ultralytics import YOLO

# # Chemin du modèle YOLOv5
# MODEL_PATH = "Model/best.pt"

# # Espèces détectables par le modèle
# FISH_CLASSES = ["ABL", "ALA", "ANG", "BRE", "CHE", "HOT", "SIL"]

# # Dossier contenant les images à classer
# IMAGE_FOLDER = Path("images_to_classify")  # à adapter

# # Charger le modèle YOLO
# @st.cache_resource
# def load_model():
#     return YOLO(MODEL_PATH)

# model = load_model()

# # Liste des images à classer
# @st.cache_data
# def get_image_list():
#     return sorted([p for p in IMAGE_FOLDER.glob("*.png")])

# # Interface principale
# def main():
#     st.title("🎣 Classification participative des poissons")

#     images = get_image_list()
#     if not images:
#         st.warning("Aucune image à classer.")
#         return

#     # Sélection d'une image (simple pour le moment, 1ère de la liste)
#     index = st.session_state.get("image_index", 0)
#     if index >= len(images):
#         st.success("Toutes les images ont été classées !")
#         return

#     image_path = images[index]
#     img = Image.open(image_path)
#     st.image(img, caption=image_path.name, use_container_width=True)

#     # Prédiction IA
#     st.subheader("🔍 Prédiction IA")
#     results = model.predict(source=image_path, imgsz=640, verbose=False)
#     pred_df = results[0]

#     # Obtenir l'ID de la classe prédite
#     pred_class_id = int(pred_df.probs.top1)

#     # Mapper l'ID de la classe au nom de la classe
#     pred_class_name = model.names[pred_class_id]

#     st.write(f"Espèce détectée : {pred_class_name}")

#     # Annotation humaine
#     st.subheader("🧑‍🔬 Votre classification")
#     selected_class = st.radio("Quelle est l'espèce de ce poisson ?", FISH_CLASSES)

#     if st.button("✅ Soumettre"):
#         # TODO : Sauvegarder dans un fichier ou une DB locale
#         st.success(f"Annotation enregistrée : {selected_class}")
#         st.session_state.image_index = index + 1
#         st.rerun()

#     # Navigation manuelle
#     if st.button("⏭ Passer à l'image suivante"):
#         st.session_state.image_index = index + 1
#         st.rerun()

# if __name__ == "__main__":
#     main()


# """

# """
import sys
import types

# Patch pour éviter l'inspection de torch.classes
sys.modules["torch.classes"] = types.ModuleType("torch.classes")
import torch._classes
import os
import streamlit as st
import requests
import base64
from io import BytesIO
from PIL import Image
from ultralytics import YOLO
from dotenv import load_dotenv

# Chargement .env (pour backend_url si besoin)
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Classification Poissons", layout="centered")
st.title("🎣 Science participative : classifiez des poissons")

# Identifiant utilisateur
user_id = st.sidebar.text_input("Votre identifiant utilisateur")

# Charger modèle YOLO local
@st.cache_resource
def load_model():
    return YOLO("frontend/Model/best.pt")
model = load_model()

# Bouton nouvelle image
if st.button("Nouvelle image à annoter"):
    res = requests.get(f"{BACKEND_URL}/image")
    if res.status_code == 200:
        data = res.json()
        st.session_state.img_id = data["image_id"]
        st.session_state.img_b64 = data["image"]
    else:
        st.error("Aucune image disponible.")

# Afficher si image chargée
if "img_b64" in st.session_state:
    img_bytes = base64.b64decode(st.session_state.img_b64)
    st.image(img_bytes, caption="Image à annoter", use_container_width=True)
    img_pil = Image.open(BytesIO(img_bytes))

    # Prédiction IA locale
    st.subheader("🔍 Prédiction IA (YOLO)")
    results = model(img_pil)
    if results and results[0].boxes.cls is not None:
        pred_ids = results[0].boxes.cls.cpu().numpy().astype(int)
        pred_names = [results[0].names[i] for i in pred_ids]
        pred_label = pred_names[0]
    else:
        pred_label = "Aucune détectée"
    st.write(f"**Prédiction IA:** {pred_label}")

    # Sélection humain
    st.subheader("🧑‍🔬 Votre classification")
    chosen = st.selectbox("Espèce :", ["ABL","ALA","ANG","BRE","CHE","HOT","SIL"])

    # Soumettre annotation
    if st.button("✅ Soumettre annotation"):
        if not user_id:
            st.warning("Entrez un identifiant utilisateur.")
        else:
            payload = {
                "image_id": st.session_state.img_id,
                "user_id": user_id,
                "label": chosen,
                "prediction_ia": pred_label
            }
            r = requests.post(f"{BACKEND_URL}/annotations", json=payload)
            if r.ok:
                st.success("Annotation enregistrée !")
            else:
                st.error(f"Erreur: {r.text}")

    # Vote IA
    agree = st.checkbox("La prédiction de l'IA est correcte")
    if agree and user_id:
        rv = requests.post(f"{BACKEND_URL}/vote", json={
            "image_id": st.session_state.img_id,
            "user_id": user_id,
            "vote": True
        })
        if rv.ok:
            st.info("Vote enregistré.")
        else:
            st.error("Erreur vote.")