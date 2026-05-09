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

#  login manager
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Сессия для запросов(защита от сбоев в программе)
http_session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
http_session.mount('https://', HTTPAdapter(max_retries=retries))

# LM Studio API
LM_STUDIO_URL = "http://26.44.241.237:1234/v1/chat/completions"

# запрос в LLM
def get_ai_suggestion(user, extra_exclude=None):

    # список исключаемых треков
    if extra_exclude is None:
        extra_exclude = []

    # модификаторы для разнообразия промптов
    viewed_tracks = list(extra_exclude)
    """Возвращает строку 'Artist - Title' или fallback."""
    moods = [
        "энергичное для тренировки", "меланхоличное для дождя",
        "летнее для вечеринки", "глубокое для раздумий",
        "лоу-фай для учебы", "агрессивное для драйва",
        "уютное для вечера дома", "ностальгическое"
    ]
    decades = ["1970-х", "1980-х", "1990-х", "2000-х", "2010-х", "современную"]
    roles = [
        "музыкальный критик Rolling Stone",
        "диджей из андеграундного клуба",
        "опытный меломан со стажем 40 лет",
        "эксперт по поиску скрытых талантов",
        "нейросеть из будущего, знающая все хиты"
    ]

    # один модификатор каждого типа случайным образом
    current_mood = random.choice(moods)
    current_decade = random.choice(decades)
    current_role = random.choice(roles)

    # сбор истории треков для исключения повторов
    fav_playlist = Playlist.query.filter_by(user_id=user.id, name="Любимое").first()
    if fav_playlist:
        viewed_tracks += [f"{t.artist} - {t.title}" for t in fav_playlist.tracks]
    viewed_tracks += [f"{t.artist} - {t.title}" for t in user.dislikes]

    #  последние 15 треков, чтобы промпт не был слишком длинным
    exclude_str = ", ".join(viewed_tracks[-15:]) if viewed_tracks else "None"

    # музыкальные предпочтения пользователя
    user_genres = user.genres if user.genres and user.genres != "None" else "Pop, Rock, Electronic"
    user_artists = user.artists if user.artists and user.artists != "None" else "Famous artists"


    # неожиданный трек вне стандартных вкусов
    neogid = random.random() < 0.2
    target_instruction = (
        f"Забудь на миг о стандартах. Предложи что-то совершенно необычное (Wildcard), но что может зацепить фаната {user_genres}."
        if neogid
        else f"Ориентируйся на вкусы: {user_genres} и {user_artists}. Учти эпоху: {current_decade}."
    )

    #  полный текст промта
    prompt = f"""
    {target_instruction}
    Настроение трека: {current_mood}.

    КРИТИЧЕСКОЕ ПРАВИЛО: Не предлагай ничего из этого списка: [{exclude_str}].
    Найди 'Hidden Gem' (редкий или очень качественный трек), избегай самого мейнстрима.

    Ответь ТОЛЬКО в формате: Исполнитель - Название
    """

    # отправка запроса к LM Studio
    payload = {
        "messages": [
            {"role": "system",
             "content": f"Ты — {current_role}. Твоя задача — находить редкую и крутую музыку. Отвечай только строкой 'Artist - Title'."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.85,
        "max_tokens": 150,
        "stop": ["\n", "Исполнитель", "Название"]  # принудительно стоп
    }

    try:

        # запрос к локальному серверу LM Studio
        response = http_session.post(LM_STUDIO_URL, json=payload, timeout=12)

        # если сервер ответил ошибкой, сразу возвращаем запасной трек
        if response.status_code != 200:
            print(f"Ошибка API: {response.status_code}")
            return "Massive Attack - Teardrop"

        raw_content = response.json()['choices'][0]['message']['content'].strip()
        print(f"\n- {raw_content}")

        # очистка ответа
        content = raw_content.split('\n')[0].split(';')[0].split(',')[0].strip()
        clean = content.replace('"', '').replace("'", "").strip()

        if " - " not in clean:
            return "Massive Attack - Teardrop"
        return clean

    # ошибка с LLM
    except Exception as e:
        print(f" Ошибка с ИИ: {e}")
        return "Air - All I Need"