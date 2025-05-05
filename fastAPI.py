from fastapi import FastAPI, HTTPException
from mongo_setup import add_annotation, get_pending_image

app = FastAPI()

@app.get("/next_image")
async def next_image():
    img = get_pending_image()
    if not img:
        raise HTTPException(404, "Aucune image disponible")
    return {"image": img["image"], "url": f"/images/{img['image']}"}

@app.post("/annotate")
async def annotate(payload: dict):
    res = add_annotation(
        image=payload["image"],
        user_id=payload["user_id"],
        user_label=payload["label"],
        prediction_ia=payload.get("prediction_ia"),
        timestamp=payload.get("timestamp")
    )
    return {"inserted_id": str(res.inserted_id)}
