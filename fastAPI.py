from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]

doc = db.images.find_one({"_id": ObjectId("6818c81b13f22e4251529f61")})
print(doc)
