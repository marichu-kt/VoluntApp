# VoluntApp Completo en Python
# Aplicación web (y prototipo móvil) con Flask, SQLite, Folium, Flask-Login y PDF
# Uso educativo como ejemplo de un proyecto 'super completo' integrando:
# - Registro/Iniciar sesión (usuarios voluntarios, organizaciones, admin)
# - Mapa interactivo (Folium) centrado en Madrid
# - Inscripción a actividades y registro de horas
# - Generación de reportes en PDF
# Este código usa una sola estructura de archivo para mayor simplicidad,
# pero lo recomendable es separarlo en varios módulos/ficheros.
#
# Para que funcione, necesitas instalar:
# pip install flask flask_sqlalchemy flask_login flask_wtf wtforms folium reportlab
#
# Ejecución:
# python voluntapp_completo.py
# Después, abrir http://127.0.0.1:5000 en tu navegador.
#
# ¡Recuerda: Este es un prototipo con fines didácticos!

from flask import Flask, render_template_string, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, HiddenField
from wtforms.validators import InputRequired, Length, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
import folium
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ClaveSecretaVoluntApp'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///voluntapp_completo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ----------------------------------------------------------------
# MODELOS DE BASE DE DATOS
# ----------------------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), default='voluntario')  # voluntario, organizacion, admin
    horas_voluntariado = db.Column(db.Integer, default=0)


class Organizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    lat = db.Column(db.Float, default=40.4168)
    lon = db.Column(db.Float, default=-3.7038)
    descripcion = db.Column(db.Text, default='Organización de voluntariado.')


class Actividad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    organizacion_id = db.Column(db.Integer, db.ForeignKey('organizacion.id'))
    fecha = db.Column(db.String(100))
    # Relacion muchos a muchos con usuarios (voluntarios)
    inscritos = db.relationship('User', secondary='usuario_actividad', backref='actividades', lazy='dynamic')

usuario_actividad = db.Table('usuario_actividad',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('actividad_id', db.Integer, db.ForeignKey('actividad.id'))
)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------------------------------------------------------
# FORMULARIOS WTForms
# ----------------------------------------------------------------
class RegisterForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[InputRequired(), Email(message='Formato de email inválido'), Length(max=150)])
    nombre = StringField('Nombre completo', validators=[InputRequired(), Length(min=2, max=100)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=150)])
    confirm = PasswordField('Repetir contraseña', validators=[InputRequired(), EqualTo('password', message='Las contraseñas deben coincidir')])
    submit = SubmitField('Registrarse')


class LoginForm(FlaskForm):
    email = StringField('Correo electrónico', validators=[InputRequired(), Email(message='Formato de email inválido'), Length(max=150)])
    password = PasswordField('Contraseña', validators=[InputRequired(), Length(min=4, max=150)])
    submit = SubmitField('Iniciar Sesión')


class ActividadForm(FlaskForm):
    titulo = StringField('Título de la Actividad', validators=[InputRequired(), Length(min=3, max=150)])
    descripcion = TextAreaField('Descripción', validators=[InputRequired()])
    fecha = StringField('Fecha', validators=[InputRequired(), Length(min=3, max=50)])
    org_id = HiddenField('ID Organización')
    submit = SubmitField('Crear Actividad')


# ----------------------------------------------------------------
# HTML TEMPLATES (Embed usando render_template_string para simplificar)
# En producción, se recomienda usar /templates/*.html con render_template.
# ----------------------------------------------------------------
html_base = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8" />
    <title>VoluntApp</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0; padding: 0;
            background: #f6f6f6;
        }
        header {
            background: #343a40;
            color: white;
            padding: 1rem;
            text-align: center;
        }
        nav {
            background: #ffffff;
            padding: 0.5rem;
            border-bottom: 1px solid #ccc;
            display: flex;
            justify-content: center;
            gap: 1rem;
        }
        a {
            text-decoration: none;
            color: #343a40;
            font-weight: bold;
        }
        a:hover {
            color: #007bff;
        }
        .container {
            width: 90%;
            max-width: 800px;
            margin: 1rem auto;
            background: #fff;
            padding: 1rem;
            box-shadow: 0 0 5px rgba(0,0,0,0.1);
        }
        footer {
            text-align: center;
            background: #343a40;
            color: #fff;
            padding: 1rem;
            margin-top: 2rem;
        }
        .map {
            width: 100%;
            height: 500px;
        }
        .alert {
            padding: 0.75rem;
            background: #ffdddd;
            color: #900;
            margin-bottom: 1rem;
            border-radius: 4px;
        }
        .success {
            background: #ddffdd;
            color: #090;
        }
    </style>
</head>
<body>
    <header>
        <h1>VoluntApp</h1>
    </header>
    <nav>
        <a href="{{ url_for('index') }}">Inicio</a>
        {% if current_user.is_authenticated %}
            <a href="{{ url_for('mapa') }}">Mapa</a>
            <a href="{{ url_for('actividades') }}">Actividades</a>
            <a href="{{ url_for('perfil') }}">Perfil</a>
            <a href="{{ url_for('logout') }}">Cerrar Sesión</a>
        {% else %}
            <a href="{{ url_for('login') }}">Iniciar Sesión</a>
            <a href="{{ url_for('register') }}">Registrarse</a>
        {% endif %}
    </nav>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, msg in messages %}
                <div class="alert {% if category == 'success' %}success{% endif %}">{{ msg }}</div>
            {% endfor %}
        {% endif %}
        {% endwith %}
        {{ body|safe }}
    </div>
    <footer>
        <p>VoluntApp - Proyecto de Voluntariado Social</p>
    </footer>
</body>
</html>
'''

html_index = '''
{% block body %}
<h2>Bienvenido/a a VoluntApp</h2>
<p>Encuentra oportunidades de voluntariado y contribuye a tu comunidad.</p>
{% endblock %}
'''

html_login = '''
{% block body %}
<h2>Iniciar Sesión</h2>
<form method="POST">
    {{ form.csrf_token }}
    <div>
        {{ form.email.label }}<br>
        {{ form.email }}
    </div>
    <br>
    <div>
        {{ form.password.label }}<br>
        {{ form.password }}
    </div>
    <br>
    <div>
        {{ form.submit }}
    </div>
</form>
{% endblock %}
'''

html_register = '''
{% block body %}
<h2>Registrarse</h2>
<form method="POST">
    {{ form.csrf_token }}
    <div>
        {{ form.email.label }}<br>
        {{ form.email }}
    </div>
    <div>
        {{ form.nombre.label }}<br>
        {{ form.nombre }}
    </div>
    <div>
        {{ form.password.label }}<br>
        {{ form.password }}
    </div>
    <div>
        {{ form.confirm.label }}<br>
        {{ form.confirm }}
    </div>
    <br>
    <div>
        {{ form.submit }}
    </div>
</form>
{% endblock %}
'''

html_mapa = '''
{% block body %}
<h2>Mapa de Oportunidades en Madrid</h2>
<div class="map">{{ mapa_html|safe }}</div>
{% endblock %}
'''

html_actividades = '''
{% block body %}
<h2>Actividades Disponibles</h2>

{% if current_user.rol == 'organizacion' or current_user.rol == 'admin' %}
<h3>Crear Nueva Actividad</h3>
<form method="POST">
    {{ form.csrf_token }}
    <div>
        {{ form.titulo.label }}<br>
        {{ form.titulo }}
    </div>
    <div>
        {{ form.descripcion.label }}<br>
        {{ form.descripcion }}
    </div>
    <div>
        {{ form.fecha.label }}<br>
        {{ form.fecha }}
    </div>
    <div>
        {{ form.org_id }}
        {{ form.submit }}
    </div>
</form>
<hr>
{% endif %}

<ul>
{% for act in actividades %}
    <li>
        <strong>{{ act.titulo }}</strong> - {{ act.fecha }} <br>
        {{ act.descripcion }}<br>
        {% if current_user in act.inscritos %}
            <em>Ya estás inscrito</em>
        {% else %}
            <a href="{{ url_for('inscribirse_actividad', actividad_id=act.id) }}">Inscribirse</a>
        {% endif %}
    </li>
    <br>
{% endfor %}
</ul>

{% endblock %}
'''

html_perfil = '''
{% block body %}
<h2>Mi Perfil</h2>
<p><strong>Nombre:</strong> {{ current_user.nombre }}</p>
<p><strong>Correo:</strong> {{ current_user.email }}</p>
<p><strong>Rol:</strong> {{ current_user.rol }}</p>
<p><strong>Horas de Voluntariado:</strong> {{ current_user.horas_voluntariado }}</p>

<h3>Mis Actividades Inscritas</h3>
<ul>
{% for act in current_user.actividades %}
    <li>{{ act.titulo }} - {{ act.fecha }}</li>
{% endfor %}
</ul>

<a href="{{ url_for('generar_reporte_pdf') }}">Generar reporte de horas (PDF)</a>
{% endblock %}
'''


# ----------------------------------------------------------------
# RUTAS
# ----------------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(html_base, body=render_template_string(html_index))

@app.route('/register', methods=['GET','POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        nuevo_user = User(
            email=form.email.data,
            password=hashed_pw,
            nombre=form.nombre.data
        )
        db.session.add(nuevo_user)
        db.session.commit()
        flash('Registro exitoso. ¡Ya puedes iniciar sesión!', 'success')
        return redirect(url_for('login'))
    return render_template_string(html_base, body=render_template_string(html_register, form=form))

@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                flash('Has iniciado sesión correctamente.', 'success')
                return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template_string(html_base, body=render_template_string(html_login, form=form))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada.', 'success')
    return redirect(url_for('index'))

@app.route('/mapa')
@login_required
def mapa():
    # Crear mapa centrado en Madrid
    mapa_obj = folium.Map(location=[40.4168, -3.7038], zoom_start=12)
    # Añadir marcadores de las organizaciones
    organizaciones = Organizacion.query.all()
    for org in organizaciones:
        folium.Marker(
            location=[org.lat, org.lon],
            popup=f"{org.nombre}",
            tooltip=f"{org.nombre}"
        ).add_to(mapa_obj)
    mapa_html = mapa_obj._repr_html_()
    return render_template_string(
        html_base,
        body=render_template_string(html_mapa, mapa_html=mapa_html)
    )

@app.route('/actividades', methods=['GET','POST'])
@login_required
def actividades():
    form = ActividadForm()
    if (current_user.rol == 'organizacion' or current_user.rol == 'admin') and form.validate_on_submit():
        # Crear nueva actividad
        nueva_act = Actividad(
            titulo=form.titulo.data,
            descripcion=form.descripcion.data,
            fecha=form.fecha.data,
            organizacion_id=current_user.id  # su ID no es lo ideal, habría que vincular con la Org real
        )
        db.session.add(nueva_act)
        db.session.commit()
        flash('Actividad creada correctamente.', 'success')
        return redirect(url_for('actividades'))

    # Listar actividades
    acts = Actividad.query.all()
    return render_template_string(
        html_base,
        body=render_template_string(html_actividades, form=form, actividades=acts)
    )

@app.route('/inscribirse/<int:actividad_id>')
@login_required
def inscribirse_actividad(actividad_id):
    actividad = Actividad.query.get_or_404(actividad_id)
    if current_user not in actividad.inscritos:
        actividad.inscritos.append(current_user)
        db.session.commit()
        flash('¡Te has inscrito en la actividad!', 'success')
    else:
        flash('Ya estás inscrito en esta actividad.', 'info')
    return redirect(url_for('actividades'))

@app.route('/perfil')
@login_required
def perfil():
    return render_template_string(
        html_base,
        body=render_template_string(html_perfil)
    )

@app.route('/generar_reporte_pdf')
@login_required
def generar_reporte_pdf():
    # Generar un PDF con las horas de voluntariado y las actividades inscritas
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.drawString(50, 800, f"Reporte de Voluntariado de {current_user.nombre}")
    c.drawString(50, 780, f"Email: {current_user.email}")
    c.drawString(50, 760, f"Horas Totales: {current_user.horas_voluntariado}")

    c.drawString(50, 730, "Actividades Inscritas:")
    y = 710
    for act in current_user.actividades:
        c.drawString(60, y, f"- {act.titulo} ({act.fecha})")
        y -= 20
    c.showPage()
    c.save()

    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=reporte_voluntariado.pdf'
    return response

# ----------------------------------------------------------------
# INICIALIZACIÓN DE BASE DE DATOS + EJECUCIÓN
# ----------------------------------------------------------------
if __name__ == '__main__':
    # Abrimos el contexto de la app antes de hacer queries
    with app.app_context():
        # Si deseas controlar la existencia del archivo, hazlo aquí:
        if not os.path.exists('voluntapp_completo.db'):
            db.create_all()
        else:
            # Incluso si existe, puedes asegurar que las tablas estén creadas
            db.create_all()

        # Si no hay org ni admin creados, crearlos a modo de ejemplo
        if not User.query.filter_by(email='admin@voluntapp.com').first():
            admin = User(
                email='admin@voluntapp.com',
                password=generate_password_hash('org123', method='pbkdf2:sha256'),
                nombre='Administrador',
                rol='admin'
            )
            db.session.add(admin)
            db.session.commit()

        if not User.query.filter_by(email='org@voluntapp.com').first():
            orguser = User(
                email='org@voluntapp.com',
                password=generate_password_hash('org123', method='pbkdf2:sha256'),
                nombre='OrgDemo',
                rol='organizacion'
            )
            db.session.add(orguser)
            db.session.commit()

        # Crear ejemplo de organizacion real en Madrid
        if not Organizacion.query.all():
            org_data = Organizacion(
                nombre='Banco de Alimentos de Madrid',
                lat=40.3627,
                lon=-3.7575,
                descripcion='Banco de Alimentos que recibe y distribuye comida a ONGs.'
            )
            db.session.add(org_data)

            org_data2 = Organizacion(
                nombre='Cruz Roja de Madrid',
                lat=40.4203,
                lon=-3.7044,
                descripcion='Organización humanitaria ofreciendo ayuda en diversas áreas.'
            )
            db.session.add(org_data2)
            db.session.commit()

    # Una vez todo está inicializado, corremos la app
    app.run(debug=True)
