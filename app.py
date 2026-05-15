import os, json, random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify,session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import requests

#
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

#  login manager

# Сессия для запросов(защита от сбоев в программе)
http_session = requests.Session()
retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
http_session.mount('https://', HTTPAdapter(max_retries=retries))

# LM Studio API



# запрос в LLM


# обложки

#маршруты



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

#Запуск
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080, debug=True)