from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User

class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Это имя уже занято.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Этот email уже используется.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')

class PreferencesForm(FlaskForm):
    # Жанры (предопределённый список для демо)
    genres = SelectMultipleField(
        'Любимые жанры',
        choices=[
            ('pop', 'Поп'),
            ('rock', 'Рок'),
            ('hiphop', 'Хип-хоп'),
            ('electronic', 'Электроника'),
            ('jazz', 'Джаз'),
            ('classical', 'Классика'),
            ('indie', 'Инди'),
            ('r&b', 'R&B')
        ],
        validators=[DataRequired(message='Выберите хотя бы один жанр')]
    )
    artists = TextAreaField('Любимые исполнители (через запятую)', validators=[DataRequired()])
    submit = SubmitField('Сохранить предпочтения')

class PlaylistForm(FlaskForm):
    name = StringField('Название плейлиста', validators=[DataRequired()])
    is_public = BooleanField('Сделать общедоступным')
    submit = SubmitField('Создать плейлист')
