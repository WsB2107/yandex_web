import os, json, random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import timedelta
import requests


# LM Studio API
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"

#  Инициализация
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
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
    id = db.Column(db.Integer, primary_key=True)  # первичный ключ
    username = db.Column(db.String(50), unique=True, nullable=False)  # уникальный логин
    password = db.Column(db.String(255), nullable=False)  # хэш пароля
    genres = db.Column(db.String(200))  # музыкальные вкусы, заполняются после регистрации на странице
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


# обложки
def get_track_cover(artist, title):
    # Ищем трек с такими же исполнителем и названием в таблице Track
    existing = Track.query.filter_by(artist=artist, title=title).first()

    # Если трек уже есть в базе и у него сохранён cover_url, сразу возвращаем его
    if existing and existing.cover_url:
        return existing.cover_url

    try:
        # очищаем строку запроса: убираем всё после ';' или '(', заменяем пробелы на '+'
        clean = f"{artist} {title}".split(';')[0].split('(')[0].replace(" ", "+")

        # Формируем URL запрос поиска по песням и берем 1 результат
        resp = http_session.get(
            f"https://itunes.apple.com/search?term={clean}&entity=song&limit=1",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('resultCount', 0) > 0:
                return data['results'][0]['artworkUrl100'].replace('100x100', '600x600')
    except Exception as e:
        print(f"Ошибка iTunes: {e}")

    # заглушка, если обложка не найдена
    return "/static/img/error_image.png"


# маршруты
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
            login_user(user, remember=True)
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
    # проверка показанных треков, работает ли все корректно
    shown = session.get('shown_tracks', [])
    print(f" currently shown ({len(shown)}): {shown}")

    # ограничиваем историю 30 последними, чтобы не росла бесконечно
    if len(shown) > 30:
        shown = shown[-15:]
        session['shown_tracks'] = shown

    suggestion = get_ai_suggestion(current_user, extra_exclude=shown)
    print(f" '{suggestion}'")

    # ответ пустой или не соответствует ожидаемому формату
    if not suggestion or " - " not in suggestion:
        fallback_pool = [
            "Massive Attack - Teardrop"]
        # первый трек, которого нет в shown
        chosen = None
        for fb in fallback_pool:
            if fb not in shown:
                chosen = fb
                break
        if chosen is None:
            # треки, которые уже были – очищаем историю и берём первый
            shown = []
            chosen = fallback_pool[0]
        suggestion = chosen
        print(f"Chosen: {suggestion}")

    # новый трек в историю и сохраняем в сессию
    shown.append(suggestion)
    session['shown_tracks'] = shown

    # артист и название
    artist, title = suggestion.split(" - ", 1)
    cover = get_track_cover(artist.strip(), title.strip())
    return jsonify({"artist": artist.strip(), "title": title.strip(), "cover": cover})


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


# Запуск
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)
