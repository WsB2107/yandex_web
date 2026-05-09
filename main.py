import os, random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify,session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

#  Инициализация
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///melodist.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Таблица для дизлайков
disliked_tracks = db.Table('disliked_tracks',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('track_id', db.Integer, db.ForeignKey('track.id'))
)

# Модели
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True) #первичный ключ
    username = db.Column(db.String(50), unique=True, nullable=False)#уникальный логин
    password = db.Column(db.String(255), nullable=False)#хэш пароля
    genres = db.Column(db.String(200)) #музыкальные вкусы, заполняются после регистрации на странице
    artists = db.Column(db.String(200))
    playlists = db.relationship('Playlist', backref='owner', lazy=True)
    dislikes = db.relationship('Track', secondary=disliked_tracks, backref='disliked_by')

class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    artist = db.Column(db.String(100))
    cover_url = db.Column(db.String(500))
    genre = db.Column(db.String(100))

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tracks = db.relationship('Track', secondary='playlist_track', lazy='subquery',
                             backref=db.backref('playlists', lazy=True))

playlist_track = db.Table('playlist_track',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlist.id'), primary_key=True),
    db.Column('track_id', db.Integer, db.ForeignKey('track.id'), primary_key=True)
)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
