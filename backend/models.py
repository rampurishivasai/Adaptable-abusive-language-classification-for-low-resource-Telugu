# backend/models.py

from pymongo import MongoClient
from bson.objectid import ObjectId
 
client = MongoClient('localhost', 27017)
db = client.flask_app

users_collection = db.users
photos_collection = db.photos
comments_collection = db.comments

def create_user(username, password):
    if users_collection.find_one({"username": username}):
        return False, "User already exists"
    users_collection.insert_one({"username": username, "password": password})
    return True, "Signup successful"

def authenticate_user(username, password):
    user = users_collection.find_one({"username": username, "password": password})
    return user is not None

def add_photo(url, description, username):
    photo_id = photos_collection.insert_one({"url": url, "description": description, "username": username}).inserted_id
    return str(photo_id)

def get_photos():
    return list(photos_collection.find())

def get_photo(photo_id):
    return photos_collection.find_one({"_id": ObjectId(photo_id)})

def add_comment(photo_id, username, text):
    comment_id = comments_collection.insert_one({"photo_id": ObjectId(photo_id), "username": username, "text": text}).inserted_id
    return str(comment_id)

def get_comments(photo_id):
    return list(comments_collection.find({"photo_id": ObjectId(photo_id)}))

def delete_comment(comment_id, username):
    comment = comments_collection.find_one({"_id": ObjectId(comment_id), "username": username})
    if comment:
        comments_collection.delete_one({"_id": ObjectId(comment_id)})
        return True
    return False
