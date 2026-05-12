from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Project, ProjectLog
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workshop.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Auth Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
            
        new_user = User(username=username, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- API Эндпоинт (REST) ---
@app.route('/api/v1/projects', methods=['GET'])
def get_projects_api():
    projects = Project.query.all()
    return jsonify([{'id': p.id, 'title': p.title} for p in projects])

# --- Веб-страницы ---
@app.route('/')
@login_required
def index():
    user_projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', projects=user_projects)

@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    title = request.form.get('title')
    description = request.form.get('description')
    
    if not title:
        flash('Project title is required!')
        return redirect(url_for('index'))
        
    new_project = Project(title=title, description=description, user_id=current_user.id)
    db.session.add(new_project)
    db.session.commit()
    
    flash(f'Project "{title}" created successfully!')
    return redirect(url_for('index'))

from werkzeug.utils import secure_filename
from flask import send_from_directory

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    return render_template('project.html', project=project)

@app.route('/project/<int:project_id>/add_log', methods=['POST'])
@login_required
def add_log(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
        
    content = request.form.get('content', '')
    
    file_path = None
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_path, exist_ok=True)
            file.save(os.path.join(upload_path, filename))
            file_path = filename
            
    if not file_path and not content.strip():
        flash('Log cannot be empty if no file is uploaded.')
        return redirect(url_for('view_project', project_id=project.id))
        
    if not content.strip():
        content = "Uploaded a file"
        
    new_log = ProjectLog(content=content, image_path=file_path, project_id=project.id)
    db.session.add(new_log)
    db.session.commit()
    
    flash('Log and file added successfully!')
    return redirect(url_for('view_project', project_id=project.id))

@app.route('/uploads/<name>')
@login_required
def download_file(name):
    return send_from_directory(os.path.join(app.root_path, app.config['UPLOAD_FOLDER']), name)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
