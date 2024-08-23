import os
import json
import base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient

# Initialize Flask application
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.secret_key = 'your_secret_key'

# MongoDB setup
mongo_client = MongoClient('mongodb://localhost:27017/')
db_name = 'security_db'
mongo_db = mongo_client[db_name]
users_collection = mongo_db['users']
profiles_collection = mongo_db['profiles']
images_collection = mongo_db['images']

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def hash_password(password):
    return generate_password_hash(password)

def check_password(stored_password, provided_password):
    return check_password_hash(stored_password, provided_password)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        
        user = users_collection.find_one({"username": username, "email": email})
        
        if user and check_password(user['password'], password):
            session['username'] = username
            return redirect(url_for("profile_page", username=username))
        else:
            return render_template("login.html", error="Invalid username, email, or password")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]

        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            return render_template("register.html", error="Username already exists")

        existing_email = users_collection.find_one({"email": email})
        if existing_email:
            return render_template("register.html", error="Email already registered")

        hashed_password = hash_password(password)
        user = {
            "username": username,
            "email": email,
            "password": hashed_password
        }
        users_collection.insert_one(user)

        return redirect(url_for("login"))
    
    return render_template("register.html")

@app.route("/security", methods=["GET", "POST"])
def security():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    
    if request.method == "POST":
        profile_name = request.form["profile_name"]
        image_data_array = request.form.get("imageData")
        user = users_collection.find_one({'username': username})
        
        if user:
            profile = profiles_collection.find_one({'user_id': user['_id'], 'profile_name': profile_name})
            if not profile:
                profile_data = {
                    'profile_name': profile_name,
                    'user_id': user['_id'],
                    'images': []
                }
                profile_id = profiles_collection.insert_one(profile_data).inserted_id
            else:
                profile_id = profile['_id']
            
            profile_folder = os.path.join(app.config['UPLOAD_FOLDER'], profile_name)
            os.makedirs(profile_folder, exist_ok=True)
            
            image_data_array = json.loads(image_data_array)
            image_infos = []
            for idx, image_data in enumerate(image_data_array):
                header, encoded = image_data.split(",", 1)
                data = base64.b64decode(encoded)
                image_filename = f"{profile_name}_image_{idx + 1}.png"
                image_path = os.path.join(profile_folder, image_filename)
                
                with open(image_path, "wb") as file:
                    file.write(data)
                
                image_info = {
                    'filename': image_filename,
                    'profile_id': profile_id,
                    'timestamp': datetime.utcnow()
                }
                image_infos.append(image_info)
            
            profiles_collection.update_one(
                {'_id': profile_id},
                {'$push': {'images': {'$each': image_infos}}}
            )
            
            return redirect(url_for("profile_page", username=username))
    
    return render_template("security.html", username=username)

@app.route("/profile/<username>", methods=["GET", "POST"])
def profile_page(username):
    # Fetch the user by username
    user = users_collection.find_one({"username": username})
    
    # Ensure the user is logged in and the session username matches the URL username
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))

    if request.method == "POST":
        profile_name = request.form["profile_name"]
        
        # Check if the profile name already exists for the current user
        existing_profile = profiles_collection.find_one({'profile_name': profile_name, 'user_id': user['_id']})
        if existing_profile:
            # Fetch all profiles to display them along with the error message
            profiles = profiles_collection.find({'user_id': user['_id']})
            return render_template("profile.html", profiles=profiles, username=username, error="Profile name already exists")

        # Create and save the new profile
        new_profile = {
            'profile_name': profile_name,
            'user_id': user['_id'],
            'images': []
        }
        profiles_collection.insert_one(new_profile)
        
        return redirect(url_for("profile_page", username=username))

    # Fetch and display all profiles associated with the user
    profiles = profiles_collection.find({'user_id': user['_id']})
    return render_template("profile.html", profiles=profiles, username=username)

@app.route("/profile/<username>/<profile_name>/images", methods=["GET"])
def view_images(username, profile_name):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    
    user = users_collection.find_one({"username": username})
    
    if user:
        profile = profiles_collection.find_one({'user_id': user['_id'], 'profile_name': profile_name})
        if profile:
            image_infos = profile['images']
            image_data = []

            for image_info in image_infos:
                image_url = url_for('uploaded_file', filename=f"{profile_name}/{image_info['filename']}")
                image_data.append({
                    'url': image_url,
                    'timestamp': image_info['timestamp']
                })

            return render_template("view_images.html", username=username, profile_name=profile_name, images=image_data)
    return "Profile not found", 404

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == "__main__":
    app.run(debug=True)  # Run the Flask application in debug mode
