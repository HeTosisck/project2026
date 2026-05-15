import os
from dotenv import load_dotenv

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from models import db, User, Project, ProjectLog, ProjectJoinRequest, ProjectMember

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_dev_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workshop.db'

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)
with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.route('/api/v1/projects', methods=['GET'])
@login_required
def get_projects_api():
    projects = Project.query.all()
    return jsonify([{'id': p.id, 'title': p.title} for p in projects])

@app.route('/')
@login_required
def index():
    owned = Project.query.filter_by(user_id=current_user.id).all()
    member_projects = [m.project for m in ProjectMember.query.filter_by(user_id=current_user.id).all()]
    # объединяем без дубликатов
    all_projects = owned + [p for p in member_projects if p not in owned]
    return render_template('index.html', projects=all_projects)

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

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    is_owner = (project.user_id == current_user.id)
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None
    return render_template('project.html', project=project, is_owner=is_owner, is_member=is_member)


@app.route('/project/<int:project_id>/add_log', methods=['POST'])
@login_required
def add_log(project_id):
    project = Project.query.get_or_404(project_id)
    is_owner = (project.user_id == current_user.id)
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_member):
        flash('Access denied.')
        return redirect(url_for('index'))
        
    content = request.form.get('content', '')
    file_path = None
    
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            confirm_unsafe = request.form.get('confirm_unsafe') == '1'
            if not allowed_file(file.filename) and not confirm_unsafe:
                flash(f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}')
                return redirect(url_for('view_project', project_id=project.id))
            # Даже если расширение не разрешено, но confirm_unsafe == 1, продолжаем
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
    log = ProjectLog.query.filter_by(image_path=name).first()
    if not log:
        flash('File not found.')
        return redirect(url_for('index'))
    project = log.project
    is_owner = (project.user_id == current_user.id)
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_member):
        flash('Access denied.')
        return redirect(url_for('index'))
    return send_from_directory(os.path.join(app.root_path, app.config['UPLOAD_FOLDER']), name)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    
    for log in project.logs:
        if log.image_path:
            file_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], log.image_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(log)
        
    db.session.delete(project)
    db.session.commit()
    
    flash(f'Project "{project.title}" deleted.')
    return redirect(url_for('index'))

@app.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    log = ProjectLog.query.get_or_404(log_id)
    project = log.project
    is_owner = (project.user_id == current_user.id)
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_member):
        flash('Access denied.')
        return redirect(url_for('index'))
        
    if log.image_path:
        file_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], log.image_path)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    db.session.delete(log)
    db.session.commit()
    
    flash('Log deleted.')
    return redirect(url_for('view_project', project_id=project.id))

@app.route('/project/<int:project_id>/request_join', methods=['POST'])
@login_required
def request_join(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id == current_user.id:
        flash('You are the owner of this project.')
        return redirect(url_for('view_project', project_id=project.id))
    
    existing_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first()
    if existing_member:
        flash('You are already a member.')
        return redirect(url_for('view_project', project_id=project.id))
    
    pending = ProjectJoinRequest.query.filter_by(project_id=project.id, user_id=current_user.id, status='pending').first()
    if pending:
        flash('You already have a pending request.')
        return redirect(url_for('view_project', project_id=project.id))
    
    new_req = ProjectJoinRequest(project_id=project.id, user_id=current_user.id)
    db.session.add(new_req)
    db.session.commit()
    flash('Join request sent to project owner.')
    return redirect(url_for('view_project', project_id=project.id))

@app.route('/project/<int:project_id>/requests')
@login_required
def view_requests(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    pending_requests = ProjectJoinRequest.query.filter_by(project_id=project.id, status='pending').all()
    return render_template('requests.html', project=project, requests=pending_requests)

@app.route('/project/<int:project_id>/requests/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_request(project_id, request_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    req = ProjectJoinRequest.query.get_or_404(request_id)
    if req.project_id != project.id or req.status != 'pending':
        flash('Invalid request.')
        return redirect(url_for('view_requests', project_id=project.id))
    member = ProjectMember(project_id=project.id, user_id=req.user_id)
    db.session.add(member)
    req.status = 'approved'
    db.session.commit()
    flash(f'User {req.user.username} added to project.')
    return redirect(url_for('view_requests', project_id=project.id))

@app.route('/project/<int:project_id>/requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_request(project_id, request_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    req = ProjectJoinRequest.query.get_or_404(request_id)
    if req.project_id != project.id:
        flash('Invalid request.')
        return redirect(url_for('view_requests', project_id=project.id))
    req.status = 'rejected'
    db.session.commit()
    flash('Request rejected.')
    return redirect(url_for('view_requests', project_id=project.id))

@app.route('/project/<int:project_id>/members')
@login_required
def project_members(project_id):
    project = Project.query.get_or_404(project_id)
    is_owner = (project.user_id == current_user.id)
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=current_user.id).first() is not None
    if not (is_owner or is_member):
        flash('Access denied.')
        return redirect(url_for('index'))
    members = ProjectMember.query.filter_by(project_id=project.id).all()
    return render_template('members.html', project=project, members=members, is_owner=is_owner)

@app.route('/project/<int:project_id>/remove_member/<int:member_id>', methods=['POST'])
@login_required
def remove_member(project_id, member_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('index'))
    member = ProjectMember.query.get_or_404(member_id)
    if member.project_id != project.id:
        flash('Member does not belong to this project.')
        return redirect(url_for('project_members', project_id=project.id))
    db.session.delete(member)
    db.session.commit()
    flash('Member removed.')
    return redirect(url_for('project_members', project_id=project.id))

@app.route('/my_requests')
@login_required
def my_requests():
    requests = ProjectJoinRequest.query.filter_by(user_id=current_user.id).order_by(ProjectJoinRequest.created_at.desc()).all()
    return render_template('my_requests.html', requests=requests)

@app.route('/cancel_request/<int:request_id>', methods=['POST'])
@login_required
def cancel_request(request_id):
    req = ProjectJoinRequest.query.get_or_404(request_id)
    if req.user_id != current_user.id:
        flash('You cannot cancel this request.')
        return redirect(url_for('my_requests'))
    if req.status != 'pending':
        flash('Only pending requests can be cancelled.')
        return redirect(url_for('my_requests'))
    db.session.delete(req)
    db.session.commit()
    flash('Request cancelled.')
    return redirect(url_for('my_requests'))

if __name__ == '__main__':
    app.run(debug=True)
