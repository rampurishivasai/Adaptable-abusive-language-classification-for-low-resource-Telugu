from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
# from flask import Flask
# from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from model import load_svm_model, classify_text
from PIL import Image
import os
app = Flask(__name__)
app.secret_key = 'supersecretkey'
# csrf = CSRFProtect(app)

# Configure MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['flask_app']
users_collection = db['users']
posts_collection = db['posts']
comments_collection = db['comments']
reactions_collection = db['post_reactions']
comment_reactions_collection = db['comment_reactions']


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

@app.route('/profile')
def profile():
    if 'username' in session:
        username = session['username']
        posts = list(posts_collection.find())
        for post in posts:
            post['uploader'] = users_collection.find_one({'username': post['user']})['username']
            post['reactions'] = post.get('reactions', {})  # Ensure 'reactions' field exists
        return render_template('profile.html', username=username, posts=posts)
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))

@app.route('/signup', methods=['GET', 'POST'])
def signup_route():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        firstname=request.form['firstname']
        lastname=request.form['lastname']
        email=request.form['email']
        phonenumber=request.form['phonenumber']
        if users_collection.find_one({'username': username}):
            flash('User already exists')
        else:
            hash_password = generate_password_hash(password)
            users_collection.insert_one({
                'firstname': firstname,
                'lastname': lastname, 
                'email': email,
                'username': username, 
                'password': hash_password, 
                'phonenumber': phonenumber 
                })
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

@app.route('/delete_comment/<comment_id>/<post_id>', methods=['POST'])


def delete_comment(comment_id, post_id):
    if 'username' in session:
        comments_collection.delete_one({'_id': ObjectId(comment_id), 'username': session['username']})
        flash('Comment deleted successfully')
        return redirect(url_for('post', post_id=post_id))
    else:
        flash('You are not logged in')
        return redirect(url_for('login_route'))
@app.route('/upload', methods=['POST'])

def upload_file():
    if 'username' in session:
        # Check if the post request has the file part
        if 'photo' not in request.files and 'video' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        # Get the file from the request
        file = request.files['photo'] if 'photo' in request.files else request.files['video']
        
        # If user does not select file, browser also submits an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        # If file is selected and allowed, save it
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Determine content type (photo or video)
            if file.content_type.startswith('image'):
                type = 'photo'
                resized_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resized_' + filename)
                with Image.open(file_path) as img:
                    img.thumbnail((800, 600))  # Resize if necessary
                    img.save(resized_path)
                content = 'uploads/resized_' + filename
            elif file.content_type.startswith('video'):
                type = 'video'
                content = 'uploads/' + filename
            else:
                flash('Invalid file type')
                return redirect(request.url)
            
            # Insert into database or perform other actions
            posts_collection.insert_one({
                'user': session['username'],
                'title': request.form['title'],
                'content': content,
                'type': type,
                'likes': 0,
                'dislikes': 0
            })
            
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
            # reactions_collection.delete_many({'post_id': post_id})
        return redirect(url_for('dashboard'))
    else:
        flash('You are not logged in')
        return redirect(url_for('login'))

@app.route('/react_to_post/<post_id>', methods=['POST'])
# def react_to_post(post_id):
#     if 'username' in session:
#         reaction = request.form['reaction']
#         post = posts_collection.find_one({'_id': ObjectId(post_id)})
#         if reaction == 'like':
#             posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}})
#         elif reaction == 'dislike':
#             posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': 1}})
#         return redirect(url_for('dashboard'))

def react_to_post(post_id):
    if 'username' in session:
        username = session['username']
        reaction = request.form['reaction']
        post = posts_collection.find_one({'_id': ObjectId(post_id)})

        # Update reactions in post_reactions collection
        existing_reaction = reactions_collection.find_one({'post_id': post_id, 'username': username})
        
        if reaction == 'like':
            # Update post likes and handle existing reaction
            if existing_reaction and existing_reaction['reaction'] == 'like':
                # User already liked, remove like
                posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': -1}})
                reactions_collection.delete_one({'post_id': post_id, 'username': username})
            else:
                # User disliked before, update to like
                # if existing_reaction and existing_reaction['reaction'] == 'dislike':
                #     posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': -1}})
                posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}})
                reactions_collection.update_one({'post_id': post_id, 'username': username}, {'$set': {'reaction': 'like'}}, upsert=True)

        # elif reaction == 'dislike':
        #     # Update post dislikes and handle existing reaction
        #     if existing_reaction and existing_reaction['reaction'] == 'dislike':
        #         # User already disliked, remove dislike
        #         posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': -1}})
        #         reactions_collection.delete_one({'post_id': post_id, 'username': username})
        #     else:
        #         # User liked before, update to dislike
        #         if existing_reaction and existing_reaction['reaction'] == 'like':
        #             posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': -1}})
        #         posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': 1}})
        #         reactions_collection.update_one({'post_id': post_id, 'username': username}, {'$set': {'reaction': 'dislike'}}, upsert=True)

    return redirect(url_for('dashboard'))


@app.route('/react_to_comment/<comment_id>/<post_id>', methods=['POST'])
def react_to_comment(comment_id, post_id):
    if 'username' in session:
        username = session['username']
        reaction = request.form['reaction']
        comment = comments_collection.find_one({'_id': ObjectId(comment_id)})
        print(reaction)

        # Update reactions in post_reactions collection
        existing_reaction = comment_reactions_collection.find_one({'comment_id': comment_id, 'post_id': post_id ,'username': username})
        
        if reaction == 'like':
            # Update post likes and handle existing reaction
            if existing_reaction and existing_reaction['reaction'] == 'like':
                # User already liked, remove like
                comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'likes': -1}})
                comment_reactions_collection.delete_one({'comment_id': comment_id, 'post_id': post_id,'username': username})
            else:
                # User disliked before, update to like
                # if existing_reaction and existing_reaction['reaction'] == 'dislike':
                #     comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'dislikes': -1}})
                comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'likes': 1}})
                comment_reactions_collection.update_one({'comment_id': comment_id,'post_id': post_id, 'username': username}, {'$set': {'reaction': 'like'}}, upsert=True)

        # elif reaction == 'dislike':
        #     # Update post dislikes and handle existing reaction
        #     if existing_reaction and existing_reaction['reaction'] == 'dislike':
        #         # User already disliked, remove dislike
        #         comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'dislikes': -1}})
        #         comment_reactions_collection.delete_one({'comment_id': comment_id, 'username': username})
        #     else:
        #         # User liked before, update to dislike
        #         if existing_reaction and existing_reaction['reaction'] == 'like':
        #             comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'likes': -1}})
        #         comments_collection.update_one({'_id': ObjectId(comment_id)}, {'$inc': {'dislikes': 1}})
        #         comment_reactions_collection.update_one({'comment_id': comment_id, 'username': username}, {'$set': {'reaction': 'dislike'}}, upsert=True)

    return redirect(url_for('post', post_id=post_id))


if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)

