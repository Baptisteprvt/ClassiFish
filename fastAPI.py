from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("ATLAS_URI"))
db = client[os.getenv("DB_NAME")]
print(db.images.find_one())
