import os, sys, types
# 🛠 patch pour éviter torch.classes errors
sys.modules["torch.classes"] = types.ModuleType("torch.classes")
import torch._classes

import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from ultralytics import YOLO
from dotenv import load_dotenv
import base64

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Classification Poissons", layout="centered")
st.title("🎣 Science participative : identifiez des poissons")

user_id = st.sidebar.text_input("Votre identifiant utilisateur")

@st.cache_resource
def load_model():
    return YOLO(r"..\Model\best.pt")  # Assure-toi que Model/best.pt est présent
model = load_model()

if st.button("Nouvelle image à annoter"):
    res = requests.get(f"{BACKEND_URL}/image")
    if res.ok:
        data = res.json()
        st.session_state.img_id   = data["image_id"]
        img_b64 = data["image"]
        img = Image.open(BytesIO(base64.b64decode(img_b64)))
        st.session_state.img_to_display = img
    else:
        st.error("Aucune image disponible.")


if "img_to_display" in st.session_state:
    st.image(st.session_state.img_to_display, caption="Image à annoter", use_container_width=True)

    img_resp = requests.get(st.session_state.img_url)
    img = Image.open(BytesIO(img_resp.content))

    st.subheader("🔍 Prédiction IA (YOLO)")
    results = model(img)
    if results and results[0].boxes.cls is not None:
        ids = results[0].boxes.cls.cpu().numpy().astype(int)
        names = [results[0].names[i] for i in ids]
        pred = names[0]
    else:
        pred = "Aucune détectée"
    st.write(f"**Prédiction IA:** {pred}")

    st.subheader("🧑‍🔬 Votre classification")
    chosen = st.selectbox("Espèce :", ["ABL","ALA","ANG","BRE","CHE","HOT","SIL"])

    if st.button("✅ Soumettre annotation"):
        if not user_id:
            st.warning("Entrez un identifiant utilisateur.")
        else:
            payload = {
                "image_id": st.session_state.img_id,
                "user_id": user_id,
                "label": chosen,
                "prediction_ia": pred
            }
            r = requests.post(f"{BACKEND_URL}/annotations", json=payload)
            if r.ok:
                st.success("Annotation enregistrée !")
            else:
                st.error(f"Erreur: {r.text}")

    if st.checkbox("La prédiction de l'IA est correcte") and user_id:
        rv = requests.post(f"{BACKEND_URL}/vote", json={
            "image_id": st.session_state.img_id,
            "user_id": user_id,
            "vote": True
        })
        if rv.ok:
            st.info("Vote enregistré.")
        else:
            st.error("Erreur lors du vote.")
