from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    avatar = db.Column(db.String(200), default='default_avatar.png')
    bio = db.Column(db.Text, default='')
    projects = db.relationship('Project', backref='owner', lazy=True)
    theme = db.Column(db.String(20), default='light')
    language = db.Column(db.String(10), default='en')
    city = db.Column(db.String(100), default='Penza')


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    logs = db.relationship('ProjectLog', backref='project', lazy=True)

    def is_member(self, user):
        return ProjectMember.query.filter_by(
            project_id=self.id, user_id=user.id).first() is not None

    def can_access(self, user):
        return self.user_id == user.id or self.is_member(user)


class ProjectLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id'),
        nullable=False)


class ProjectJoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id'),
        nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project = db.relationship('Project', backref='join_requests')
    user = db.relationship('User', backref='project_requests')


class ProjectMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer,
        db.ForeignKey('project.id'),
        nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            'project_id',
            'user_id',
            name='unique_project_member'),
    )
    project = db.relationship('Project', backref='members')
    user = db.relationship('User', backref='project_memberships')
