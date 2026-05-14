import os, json, random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify,session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

# ------------------ Инициализация ------------------
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

# ------------------ Модели ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    genres = db.Column(db.String(200))
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

# ------------------ login manager ------------------
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # исправлено LegacyAPIWarning

# ------------------ Сессия для запросов ------------------
http_session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
http_session.mount('https://', HTTPAdapter(max_retries=retries))

# ------------------ LM Studio API ------------------
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"

def get_ai_suggestion_with_genre(user, extra_exclude=None):
    try:
        fallback_tracks = [
        {"artist": "The Beatles", "title": "Come Together", "genre": "Rock"},
        {"artist": "Daft Punk", "title": "Get Lucky", "genre": "Electronic"},
        {"artist": "Nirvana", "title": "Smells Like Teen Spirit", "genre": "Rock"},
        {"artist": "Adele", "title": "Rolling in the Deep", "genre": "Pop"},
        {"artist": "Massive Attack", "title": "Teardrop", "genre": "Trip-Hop"},
        {"artist": "Radiohead", "title": "Karma Police", "genre": "Alternative"},
        {"artist": "Tame Impala", "title": "Let It Happen", "genre": "Psychedelic"},
        {"artist": "Arctic Monkeys", "title": "Do I Wanna Know?", "genre": "Indie Rock"},
        {"artist": "Billie Eilish", "title": "bad guy", "genre": "Pop"},
        {"artist": "The Weeknd", "title": "Blinding Lights", "genre": "Synthwave"}
        ]
        # Исключаем показанные треки
        if extra_exclude:
            fallback_tracks = [t for t in fallback_tracks if f"{t['artist']} - {t['title']}" not in extra_exclude]
        if not fallback_tracks:
            fallback_tracks = [{"artist": "Massive Attack", "title": "Teardrop", "genre": "Trip-Hop"}]
        return random.choice(fallback_tracks)

    except Exception as e:
        print(f"🚨 Ошибка нейросети: {e}")
        return {"artist": "Air", "title": "All I Need", "genre": "Electronic"}

# ------------------ Обложки ------------------
def get_track_cover(artist, title):
    existing = Track.query.filter_by(artist=artist, title=title).first()
    if existing and existing.cover_url:
        return existing.cover_url
    try:
        clean = f"{artist} {title}".split(';')[0].split('(')[0].replace(" ", "+")
        resp = http_session.get(f"https://itunes.apple.com/search?term={clean}&entity=song&limit=1", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('resultCount', 0) > 0:
                return data['results'][0]['artworkUrl100'].replace('100x100', '600x600')
    except Exception as e:
        print(f"Ошибка iTunes: {e}")
    return "https://img.freepik.com/free-vector/warning-sign-concept-illustration_114360-15597.jpg"

# ------------------ Маршруты ------------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Это имя уже занято', 'danger')
            return redirect(url_for('register'))
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        user = User(username=username, password=hashed)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('onboarding'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('tinder'))
        flash("Неверный логин или пароль", 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    if request.method == 'POST':
        genres = request.form.getlist('genres')
        artists = request.form.get('artists', '')
        current_user.genres = ", ".join(genres)
        current_user.artists = artists
        db.session.commit()
        flash('Добро пожаловать в Melodist!', 'success')
        return redirect(url_for('tinder'))
    return render_template('onboarding.html')

@app.route('/tinder')
@login_required
def tinder():
    return render_template('tinder.html')


@app.route('/api/get_next_track')
@login_required
def api_get_next_track():
    shown = session.get('shown_tracks', [])
    if len(shown) > 30:
        shown = shown[-15:]
        session['shown_tracks'] = shown

    track_data = get_ai_suggestion_with_genre(current_user, extra_exclude=shown)

    # track_data уже словарь с ключами artist, title, genre
    artist = track_data["artist"]
    title = track_data["title"]
    genre = track_data.get("genre", "Unknown")

    suggestion_str = f"{artist} - {title}"
    shown.append(suggestion_str)
    session['shown_tracks'] = shown

    cover = get_track_cover(artist, title)
    return jsonify({"artist": artist, "title": title, "cover": cover, "genre": genre})

@app.route('/action', methods=['POST'])
@login_required
def handle_action():
    data = request.json
    artist = data.get('artist')
    title = data.get('title')
    action = data.get('action')
    cover = data.get('cover', '')
    genre = data.get('genre', '')



    track = Track.query.filter_by(title=title, artist=artist).first()
    if not track:
        track = Track(title=title, artist=artist, cover_url=cover, genre=genre)
        db.session.add(track)
        db.session.flush()
    else:
        # Если трек уже есть, но жанр не заполнен, обновим
        if not track.genre and genre:
            track.genre = genre
            db.session.commit()

    if action == 'like':
        fav = Playlist.query.filter_by(user_id=current_user.id, name='Любимое').first()
        if not fav:
            fav = Playlist(name='Любимое', user_id=current_user.id, is_public=False)
            db.session.add(fav)
        if track not in fav.tracks:
            fav.tracks.append(track)
    elif action == 'dislike':
        if track not in current_user.dislikes:
            current_user.dislikes.append(track)

    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/playlists')
@login_required
def playlists():
    my_playlists = Playlist.query.filter_by(user_id=current_user.id).all()
    return render_template('playlists.html', playlists=my_playlists)

@app.route('/playlist/create', methods=['POST'])
@login_required
def create_playlist():
    name = request.form['name']
    is_public = 'is_public' in request.form
    pl = Playlist(name=name, user_id=current_user.id, is_public=is_public)
    db.session.add(pl)
    db.session.commit()
    flash('Плейлист создан', 'success')
    return redirect(url_for('playlists'))

@app.route('/playlist/<int:playlist_id>')
@login_required
def playlist_detail(playlist_id):
    pl = Playlist.query.get_or_404(playlist_id)
    if not pl.is_public and pl.user_id != current_user.id:
        flash('Нет доступа', 'danger')
        return redirect(url_for('playlists'))
    return render_template('playlist_detail.html', playlist=pl)

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    results = {'tracks': [], 'users': [], 'playlists': []}
    if query:
        results['tracks'] = Track.query.filter(
            (Track.title.ilike(f'%{query}%')) | (Track.artist.ilike(f'%{query}%'))
        ).limit(10).all()
        results['users'] = User.query.filter(User.username.ilike(f'%{query}%')).limit(10).all()
        results['playlists'] = Playlist.query.filter(
            Playlist.name.ilike(f'%{query}%'), Playlist.is_public == True
        ).limit(10).all()
    return render_template('search.html', query=query, results=results)


@app.route('/add_to_first_playlist', methods=['POST'])
@login_required
def add_to_first_playlist():
    data = request.json
    artist = data.get('artist')
    title = data.get('title')
    cover = data.get('cover', '')

    # Находим или создаём трек
    track = Track.query.filter_by(title=title, artist=artist).first()
    if not track:
        track = Track(title=title, artist=artist, cover_url=cover)
        db.session.add(track)
        db.session.flush()

    # Находим самый старый плейлист пользователя (по id)
    first_playlist = Playlist.query.filter_by(user_id=current_user.id).order_by(Playlist.id.asc()).first()

    # Если плейлистов нет — создаём плейлист по умолчанию
    if not first_playlist:
        first_playlist = Playlist(name='Моя коллекция', user_id=current_user.id, is_public=False)
        db.session.add(first_playlist)
        db.session.flush()

    # Добавляем трек, если его ещё нет в плейлисте
    if track not in first_playlist.tracks:
        first_playlist.tracks.append(track)
        db.session.commit()
        return jsonify({"status": "added", "playlist": first_playlist.name})
    else:
        return jsonify({"status": "already_exists", "playlist": first_playlist.name})


@app.route('/playlist/<int:playlist_id>/remove_track/<int:track_id>', methods=['POST'])
@login_required
def remove_track_from_playlist(playlist_id, track_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    # Проверяем права: только владелец плейлиста может удалять треки
    if playlist.user_id != current_user.id:
        flash('Нет прав на изменение этого плейлиста', 'danger')
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

    track = Track.query.get_or_404(track_id)
    if track in playlist.tracks:
        playlist.tracks.remove(track)
        db.session.commit()
        flash(f'Трек "{track.title}" удалён из плейлиста', 'success')
    else:
        flash('Трека нет в этом плейлисте', 'warning')

    return redirect(url_for('playlist_detail', playlist_id=playlist_id))


@app.route('/playlist/<int:playlist_id>/delete', methods=['POST'])
@login_required
def delete_playlist(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash('Нет прав на удаление этого плейлиста', 'danger')
        return redirect(url_for('playlists'))

    db.session.delete(playlist)
    db.session.commit()
    flash(f'Плейлист "{playlist.name}" удалён', 'success')
    return redirect(url_for('playlists'))


@app.route('/playlist/<int:playlist_id>/toggle_public', methods=['POST'])
@login_required
def toggle_playlist_public(playlist_id):
    playlist = Playlist.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash('Нет прав на изменение этого плейлиста', 'danger')
        return redirect(url_for('playlist_detail', playlist_id=playlist_id))

    playlist.is_public = not playlist.is_public
    db.session.commit()
    status = 'открытый' if playlist.is_public else 'закрытый'
    flash(f'Плейлист теперь {status}', 'success')
    return redirect(url_for('playlist_detail', playlist_id=playlist_id))

# ------------------ Запуск ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)