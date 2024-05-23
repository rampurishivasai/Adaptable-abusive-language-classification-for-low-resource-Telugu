
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from model import load_svm_model, classify_text
classifier=load_svm_model("model.pkl")

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configure MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['flask_app']
users_collection = db['users']
photos_collection = db['photos']
comments_collection = db['comments']

# Configure file upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup_route():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users_collection.find_one({'username': username}):
            flash('User already exists')
        else:
            hash_password = generate_password_hash(password)
            users_collection.insert_one({'username': username, 'password': hash_password})
            flash('Signup successful')
            return redirect(url_for('login_route'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Login successful')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        username = session['username']
        photos = list(photos_collection.find())
        for photo in photos:
            photo['uploader'] = users_collection.find_one({'username': photo['user']})['username']
        return render_template('dashboard.html', username=username, photos=photos)
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/photo/<photo_id>')
def photo(photo_id):
    if 'username' in session:
        photo = photos_collection.find_one({'_id': ObjectId(photo_id)})
        comments = comments_collection.find({'photo_id': photo_id})
        return render_template('photo.html', photo=photo, comments=comments)
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' in session:
        comment_text = request.form['comment']
        result=classify_text(comment_text,classifier)
        abusive_comment=''
        photo_id = request.form['photo_id']
        username = session['username']
        if result==0:
            abusive_comment=comment_text
            comment_text="This comment is abusive"
        comments_collection.insert_one({'photo_id': photo_id, 'username': username, 'comment': comment_text, 'abusive': abusive_comment})
        return redirect(url_for('photo', photo_id=photo_id))
        # else:
        #     flash('Comment is abusive')
        #     return redirect(url_for('photo', photo_id=photo_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/delete_comment/<comment_id>/<photo_id>')
def delete_comment(comment_id, photo_id):
    if 'username' in session:
        comments_collection.delete_one({'_id': ObjectId(comment_id), 'username': session['username']})
        return redirect(url_for('photo', photo_id=photo_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))


from PIL import Image

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' in session:
        if 'photo' not in request.files:
            flash('No file part')
            return redirect(url_for('dashboard'))
        file = request.files['photo']
        if file.filename == '':
            flash('No selected file')
            return redirect(url_for('dashboard'))
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Resize the image
            resized_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resized_' + filename)
            with Image.open(file_path) as img:
                img.thumbnail((800, 600))  # Set the maximum dimensions
                img.save(resized_path)
            
            # Save photo with dimensions
            photos_collection.insert_one({
                'user': session['username'],
                'title': request.form['title'],
                'filename': f'uploads/resized_{filename}'  # Save the resized image path
            })
            return redirect(url_for('dashboard'))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))
    
@app.route('/delete_photo/<photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if 'username' in session:
        photo = photos_collection.find_one({'_id': ObjectId(photo_id)})
        if photo and photo['user'] == session['username']:
            # Delete the photo from the database
            photos_collection.delete_one({'_id': ObjectId(photo_id)})
            # Also, delete the corresponding file from the file system if needed
            # You may need to adjust this part based on how you store your photos
            # os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo['filename']))
        return redirect(url_for('dashboard'))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
