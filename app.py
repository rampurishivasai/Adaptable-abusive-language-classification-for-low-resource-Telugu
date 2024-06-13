from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from model import load_svm_model, classify_text
from PIL import Image
import os
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Configure MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['flask_app']
users_collection = db['users']
posts_collection = db['posts']
comments_collection = db['comments']

# Configure file upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

classifier = load_svm_model("model.pkl")

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
        posts = list(posts_collection.find())
        for post in posts:
            post['uploader'] = users_collection.find_one({'username': post['user']})['username']
            post['reactions'] = post.get('reactions', {})  # Ensure 'reactions' field exists
        return render_template('dashboard.html', username=username, posts=posts)
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@app.route('/post/<post_id>')
def post(post_id):
    if 'username' in session:
        post = posts_collection.find_one({'_id': ObjectId(post_id)})
        comments = comments_collection.find({'post_id': post_id})
        return render_template('post.html', post=post, comments=comments)
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/add_comment', methods=['POST'])
def add_comment():
    if 'username' in session:
        comment_text = request.form['comment']
        result = classify_text(comment_text, classifier)
        abusive_comment = ''
        post_id = request.form['post_id']
        username = session['username']
        if result == 0:
            abusive_comment = comment_text
            comment_text = "This comment is abusive"
        comments_collection.insert_one({
            'post_id': post_id, 
            'username': username, 
            'comment': comment_text, 
            'abusive': abusive_comment, 
            'likes': 0, 
            'dislikes': 0,
            'reactions': {}  # Store reactions by user ID
        })
        return redirect(url_for('post', post_id=post_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/delete_comment/<comment_id>/<post_id>')
def delete_comment(comment_id, post_id):
    if 'username' in session:
        comments_collection.delete_one({'_id': ObjectId(comment_id), 'username': session['username']})
        return redirect(url_for('post', post_id=post_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' in session:
        title = request.form['title']
        text_content = request.form.get('text', '')

        # Check if any file or text content is provided
        file = request.files.get('photo') or request.files.get('video')
        if not file and not text_content:
            flash('No content provided')
            return redirect(url_for('dashboard'))

        type = None
        content = None

        if file and file.filename != '':
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                if file.mimetype.startswith('image'):
                    type = 'photo'
                    resized_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resized_' + filename)
                    with Image.open(file_path) as img:
                        img.thumbnail((800, 600))  # Set the maximum dimensions
                        img.save(resized_path)
                    content = 'uploads/resized_' + filename
                elif file.mimetype.startswith('video'):
                    type = 'video'
                    content = 'uploads/' + filename
            else:
                flash('File type not allowed')
                return redirect(url_for('dashboard'))
        elif text_content:
            type = 'text'
            content = text_content

        if type and content:
            posts_collection.insert_one({
                'user': session['username'],
                'title': title,
                'content': content,
                'type': type,
                'likes': 0,
                'dislikes': 0,
                'reactions': {}  # Initialize reactions as an empty dictionary
            })
            return redirect(url_for('dashboard'))
        else:
            flash('Error uploading content')
            return redirect(url_for('dashboard'))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'username' in session:
        post = posts_collection.find_one({'_id': ObjectId(post_id)})
        if post and post['user'] == session['username']:
            posts_collection.delete_one({'_id': ObjectId(post_id)})
        return redirect(url_for('dashboard'))
    else:
        flash('You are not logged in')
        return redirect(url_for('login'))

@app.route('/react_to_post/<post_id>', methods=['POST'])
def react_to_post(post_id):
    if 'username' in session:
        reaction = request.form['reaction']
        post = posts_collection.find_one({'_id': ObjectId(post_id)})
        if reaction == 'like':
            posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}})
        elif reaction == 'dislike':
            posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': 1}})
        return redirect(url_for('dashboard'))
@app.route('/react_to_comment/<comment_id>/<post_id>', methods=['POST'])
def react_to_comment(comment_id, post_id):
    if 'username' in session:
        reaction = request.form['reaction']
        user_id = session.get('user_id')
        comment = comments_collection.find_one({'_id': ObjectId(comment_id)})
        if comment:
            reactions = comment.get('reactions', {})
            if user_id not in reactions:
                if reaction == 'like':
                    comments_collection.update_one(
                        {'_id': ObjectId(comment_id)},
                        {'$inc': {'likes': 1}, '$set': {'reactions.' + user_id: reaction}}
                    )
                    if 'dislike' in reactions and reactions[user_id] == 'dislike':
                        comments_collection.update_one(
                            {'_id': ObjectId(comment_id)},
                            {'$inc': {'dislikes': -1}, '$unset': {'reactions.' + user_id: ''}}
                        )
                elif reaction == 'dislike':
                    comments_collection.update_one(
                        {'_id': ObjectId(comment_id)},
                        {'$inc': {'dislikes': 1}, '$set': {'reactions.' + user_id: reaction}}
                    )
                    if 'like' in reactions and reactions[user_id] == 'like':
                        comments_collection.update_one(
                            {'_id': ObjectId(comment_id)},
                            {'$inc': {'likes': -1}, '$unset': {'reactions.' + user_id: ''}}
                        )
            else:
                flash('You have already reacted to this comment.')
        else:
            flash('Comment not found.')
        
        return redirect(url_for('post', post_id=post_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)

