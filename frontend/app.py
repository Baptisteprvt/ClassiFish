import os
import sys
import types

# Patch pour éviter les erreurs torch.classes
sys.modules["torch.classes"] = types.ModuleType("torch.classes")
import torch._classes

import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import base64

# --- Configuration ---
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# --- Page setup ---
st.set_page_config(page_title="Classification Poissons", layout="centered")
st.title("🎣 Science participative : identifiez des poissons")

# --- Initialisation des variables de session ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'img_to_display' not in st.session_state:
    st.session_state.img_to_display = None
if 'img_id' not in st.session_state:
    st.session_state.img_id = None
if 'test_results' not in st.session_state:
    st.session_state.test_results = []
if 'user_accuracy' not in st.session_state:
    st.session_state.user_accuracy = None
if 'is_test' not in st.session_state:
    st.session_state.is_test = False
if 'expected_label' not in st.session_state:
    st.session_state.expected_label = None


# --- Fonction : récupérer une nouvelle image ---
def fetch_new_image():
    user_id = st.session_state.user_id
    if not user_id:
        st.warning("Identifiant utilisateur manquant.")
        return

    try:
        res = requests.get(f"{BACKEND_URL}/image?user_id={user_id}")
        res.raise_for_status()
        data = res.json()

        img_b64 = data["image"]
        img = Image.open(BytesIO(base64.b64decode(img_b64)))
        st.session_state.img_to_display = img
        st.session_state.img_id = data["image_id"]
        st.session_state.is_test = data.get("is_test", False)
        st.session_state.expected_label = data.get("expected_label")

    except requests.exceptions.HTTPError as e:
        st.session_state.img_to_display = None
        st.session_state.img_id = None
        if res.status_code == 404:
            st.info("🎉 Toutes les images ont été annotées ! Merci pour votre participation.")
        else:
            st.error(f"Erreur serveur : {res.text}")
    except Exception as e:
        st.error(f"Erreur inattendue : {str(e)}")


# --- Fonction : charger les stats utilisateur ---
def get_user_details(user_id):
    try:
        res = requests.get(f"{BACKEND_URL}/user_details/{user_id}", timeout=5)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        st.warning("⚠️ Impossible de charger les stats utilisateur.")
        return None


# --- Écran d’authentification ---
if not st.session_state.authenticated:
    with st.form("login_form"):
        st.subheader("🔐 Connexion")
        user_id = st.text_input("Identifiant utilisateur")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter / S'inscrire")

        if submit:
            with st.spinner("Connexion en cours..."):
                try:
                    res = requests.post(
                        f"{BACKEND_URL}/login-or-register",
                        json={"user_id": user_id, "password": password}
                    )
                    res.raise_for_status()
                    data = res.json()

                    st.session_state.authenticated = True
                    st.session_state.user_id = user_id

                    if data["exists"]:
                        st.success("✅ Connecté !")
                    else:
                        st.success("🆕 Bienvenue ! Compte créé.")

                    fetch_new_image()
                    st.rerun()

                except requests.exceptions.HTTPError as e:
                    if res.status_code == 401:
                        st.error("❌ Mot de passe incorrect.")
                    elif res.status_code == 400:
                        st.error("⚠️ Données manquantes.")
                    else:
                        st.error(f"❌ Échec : {res.text}")

                except requests.exceptions.ConnectionError:
                    st.error("🔌 Serveur inaccessible. Lancez le backend.")

                except Exception as e:
                    st.error(f"🌐 Erreur réseau : {str(e)}")


# --- Interface principale ---
else:
    user_id = st.session_state.user_id
    st.sidebar.header(f"👤 {user_id}")

    # Charger les stats utilisateur si pas encore fait
    if 'user_initialized' not in st.session_state:
        details = get_user_details(user_id)
        if details:
            test_annotations = details.get("test_annotations", 0)
            test_correct = details.get("test_correct", 0)
            accuracy = details.get("test_accuracy", 0.0)

            if test_annotations > 0:
                st.session_state.test_results = [True] * test_correct + [False] * (test_annotations - test_correct)
                st.session_state.user_accuracy = accuracy

        st.session_state.user_initialized = True

    # Affichage du score utilisateur
    if st.session_state.user_accuracy is not None:
        accuracy_percent = int(st.session_state.user_accuracy * 100)
        st.sidebar.info(f"📊 Fiabilité actuelle : {accuracy_percent}%")

    # Stats utilisateurs
    try:
        stats = requests.get(f"{BACKEND_URL}/stats?user_id={user_id}").json()
        remaining = stats.get("remaining_images", "?")
    except:
        remaining = "?"

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**📷 Images restantes : `{remaining}`**")

    # Affichage de l'image
    if st.session_state.img_to_display is not None:
        st.image(st.session_state.img_to_display, caption="Image à annoter", use_container_width=True)

        chosen = st.selectbox("Espèce :", ["ABL", "ALA", "ANG", "BRE", "CHE", "HOT", "SIL"])

        if not st.session_state.is_test:
            if st.button("⏭️ Passer cette image", use_container_width=True):
                # Passe direct à la suivante sans sauvegarder
                fetch_new_image()
                st.rerun()

        if st.button("✅ Soumettre annotation", use_container_width=True):
            payload = {
                "image_id": st.session_state.img_id,
                "user_id": user_id,
                "label": chosen,
                "is_test": st.session_state.is_test,
                "expected_label": st.session_state.expected_label
            }

            r = requests.post(f"{BACKEND_URL}/annotations", json=payload)
            if r.ok:
                st.success("Annotation enregistrée !")

                if st.session_state.is_test:
                    correct = chosen == st.session_state.expected_label
                    st.session_state.test_results.append(correct)
                    accuracy = sum(st.session_state.test_results) / len(st.session_state.test_results)
                    st.session_state.user_accuracy = accuracy
                    st.info(f"{'✅ Bonne réponse' if correct else '❌ Mauvaise réponse'} | Score actuel : {int(accuracy * 100)}%")

                # 🔁 Appel à vote_annotation uniquement si ce n'est pas une image test
                if not st.session_state.is_test:
                    try:
                        res_vote = requests.post(f"{BACKEND_URL}/vote_annotation", json={
                            "image_id": st.session_state.img_id,
                            "user_id": user_id,
                            "label": chosen
                        })

                        if res_vote.status_code == 403:
                            st.warning("⚠️ Votre fiabilité < 75%, votre vote n’a pas été compté.")
                        elif res_vote.status_code == 400:
                            pass  # Image déjà validée ou erreur
                        elif res_vote.ok:
                            vote_data = res_vote.json()
                            if "ground_truth" in vote_data:
                                st.balloons()
                                st.success(f"🎉 Cette image vient d'être validée comme : {vote_data['ground_truth']}")

                    except Exception as e:
                        st.warning("⚠️ Impossible d'enregistrer votre vote.")

                fetch_new_image()
                st.rerun()
            else:
                st.error(f"Erreur lors de l'annotation : {r.text}")
    
    else:
        if remaining == 0 :
            st.balloons()
            st.info("Merci pour votre participation !")
        else :
            st.info("Identifiez vous pour commencer.")