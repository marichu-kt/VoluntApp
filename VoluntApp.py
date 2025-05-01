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
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.lib.enums import TA_LEFT
from werkzeug.utils import secure_filename
from reportlab.platypus import KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF

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


# ---------------------------------------------------------------
#  TEMPLATES PROFESIONALES 100 % RESPONSIVE
#  (render_template_string)
# ---------------------------------------------------------------
html_base = '''
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>VoluntApp · Plataforma de Voluntariado</title>

  <!-- Bootstrap 5 (CSS & JS) -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
        rel="stylesheet" crossorigin="anonymous">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
          defer crossorigin="anonymous"></script>

  <!-- Inter font -->
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap"
        rel="stylesheet">

  <style>
    :root{
      --va-primary: #0d6efd;   /* Azul Bootstrap */
      --va-accent : #17c1e8;   /* Turquesa */
      --va-dark   : #0f172a;   /* Gris casi negro */
    }

    html,body{height:100%;}
    body{
      font-family:"Inter",system-ui,sans-serif;
      background:#f8fafc;
      display:flex;
      flex-direction:column;
    }

    /* NAVBAR */
    .navbar-brand{font-weight:700;}
    .nav-link.active{color:var(--va-accent)!important;}

    /* CARD COMÚN */
    .va-card{
      background:#fff;
      border-radius:1rem;
      box-shadow:0 0 1.25rem rgba(0,0,0,.05);
      padding:2rem 2.5rem;
    }

    /* MAPA */
    .map{width:100%;min-height:520px;border-radius:1rem;overflow:hidden;}

    /* FOOTER */
    footer{
      background:var(--va-dark);
      color:#e2e8f0;
      margin-top:auto;
    }
  </style>
</head>
<body>

  <!-- NAVBAR FIJA -->
  <nav class="navbar navbar-expand-lg navbar-light bg-white border-bottom sticky-top shadow-sm">
    <div class="container-xxl">
      <a class="navbar-brand" href="{{ url_for('index') }}">VoluntApp</a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navLinks">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div id="navLinks" class="collapse navbar-collapse justify-content-center">
        <ul class="navbar-nav gap-2">
          <li class="nav-item"><a class="nav-link {% if request.endpoint=='index' %}active{% endif %}"
                                  href="{{ url_for('index') }}">Inicio</a></li>
          {% if current_user.is_authenticated %}
            <li class="nav-item"><a class="nav-link {% if request.endpoint=='mapa' %}active{% endif %}"
                                    href="{{ url_for('mapa') }}">Mapa</a></li>
            <li class="nav-item"><a class="nav-link {% if request.endpoint=='actividades' %}active{% endif %}"
                                    href="{{ url_for('actividades') }}">Actividades</a></li>
            <li class="nav-item"><a class="nav-link {% if request.endpoint=='perfil' %}active{% endif %}"
                                    href="{{ url_for('perfil') }}">Perfil</a></li>
            <li class="nav-item"><a class="nav-link" href="{{ url_for('logout') }}">Cerrar&nbsp;sesión</a></li>
          {% else %}
            <li class="nav-item"><a class="nav-link {% if request.endpoint=='login' %}active{% endif %}"
                                    href="{{ url_for('login') }}">Iniciar&nbsp;sesión</a></li>
            <li class="nav-item"><a class="nav-link {% if request.endpoint=='register' %}active{% endif %}"
                                    href="{{ url_for('register') }}">Registrarse</a></li>
          {% endif %}
        </ul>
      </div>
    </div>
  </nav>

  <!-- FLASHES -->
  <div class="container-xxl my-4">
    {% with messages=get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category,msg in messages %}
          <div class="alert alert-{{'success' if category=='success' else 'danger'}} alert-dismissible fade show"
               role="alert">
            {{ msg }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}
  </div>

  <!-- CONTENIDO -->
  <main class="container-xxl py-3 d-flex justify-content-center">
    {{ body|safe }}
  </main>

  <!-- FOOTER -->
  <footer class="py-4 text-center">
    <small>© 2025 · VoluntApp · Madrid, España</small>
  </footer>
</body>
</html>
'''

# ---------------- INDICE / HERO ----------------
html_index = '''
{% block body %}
<section class="text-center va-card w-100" style="max-width:820px;">
  <h2 class="fw-bold mb-3">Bienvenido/a a VoluntApp&nbsp;🌍</h2>
  <p class="lead mb-4">
    Conecta con organizaciones solidarias, participa en actividades y lleva un seguimiento
    de tus horas de voluntariado desde un solo lugar.
  </p>
  {% if not current_user.is_authenticated %}
    <a class="btn btn-lg btn-primary px-5 me-2" href="{{ url_for('register') }}">Crear cuenta</a>
    <a class="btn btn-lg btn-outline-secondary px-5" href="{{ url_for('login') }}">Ya tengo cuenta</a>
  {% else %}
    <a class="btn btn-lg btn-primary px-5" href="{{ url_for('mapa') }}">Explorar oportunidades</a>
  {% endif %}
</section>
{% endblock %}
'''

# ---------------- LOGIN ----------------
html_login = '''
{% block body %}
<div class="va-card w-100" style="max-width:480px;">
  <h2 class="fw-bold text-center mb-4">Iniciar sesión</h2>
  <form method="POST" novalidate>
    {{ form.csrf_token }}
    <div class="mb-3">
      {{ form.email.label(class="form-label") }}
      {{ form.email(class="form-control") }}
    </div>
    <div class="mb-3">
      {{ form.password.label(class="form-label") }}
      {{ form.password(class="form-control") }}
    </div>
    <div class="d-grid">
      {{ form.submit(class="btn btn-primary") }}
    </div>
  </form>
</div>
{% endblock %}
'''

# ---------------- REGISTRO ----------------
html_register = '''
{% block body %}
<div class="va-card w-100" style="max-width:520px;">
  <h2 class="fw-bold text-center mb-4">Crea tu cuenta</h2>
  <form method="POST" novalidate>
    {{ form.csrf_token }}
    <div class="row g-3">
      <div class="col-md-6">
        {{ form.nombre.label(class="form-label") }}
        {{ form.nombre(class="form-control") }}
      </div>
      <div class="col-md-6">
        {{ form.email.label(class="form-label") }}
        {{ form.email(class="form-control") }}
      </div>
      <div class="col-md-6">
        {{ form.password.label(class="form-label") }}
        {{ form.password(class="form-control") }}
      </div>
      <div class="col-md-6">
        {{ form.confirm.label(class="form-label") }}
        {{ form.confirm(class="form-control") }}
      </div>
    </div>
    <div class="d-grid mt-4">
      {{ form.submit(class="btn btn-primary btn-lg") }}
    </div>
  </form>
</div>
{% endblock %}
'''

# ---------------- MAPA ----------------
html_mapa = '''
{% block body %}
<section class="va-card w-100">
  <h2 class="fw-bold text-center mb-4">Oportunidades en Madrid</h2>
  <div class="map">{{ mapa_html|safe }}</div>
</section>
{% endblock %}
'''

# ---------------- ACTIVIDADES ----------------
html_actividades = '''
{% block body %}
<section class="va-card w-100">
  <h2 class="fw-bold text-center mb-4">Actividades de voluntariado</h2>

  {% if current_user.rol in ['organizacion','admin'] %}
    <button class="btn btn-outline-primary mb-3" type="button" data-bs-toggle="collapse"
            data-bs-target="#formActividad">+ Nueva actividad</button>
    <div class="collapse" id="formActividad">
      <form method="POST" class="row g-3 mb-4">
        {{ form.csrf_token }}
        <div class="col-md-6">
          {{ form.titulo.label(class="form-label") }}
          {{ form.titulo(class="form-control") }}
        </div>
        <div class="col-md-6">
          {{ form.fecha.label(class="form-label") }}
          {{ form.fecha(class="form-control") }}
        </div>
        <div class="col-12">
          {{ form.descripcion.label(class="form-label") }}
          {{ form.descripcion(class="form-control", rows=3) }}
        </div>
        {{ form.org_id }}
        <div class="col-12 d-grid">
          {{ form.submit(class="btn btn-success") }}
        </div>
      </form>
    </div>
  {% endif %}

  <ul class="list-group">
    {% for act in actividades %}
      <li class="list-group-item d-flex justify-content-between align-items-start flex-column flex-md-row">
        <div class="me-auto">
          <div class="fw-semibold">{{ act.titulo }}</div>
          <small class="text-muted">{{ act.fecha }}</small>
          <p class="mb-1 mt-2">{{ act.descripcion }}</p>
        </div>
        <div class="ms-md-3 mt-3 mt-md-0">
          {% if current_user in act.inscritos %}
            <span class="badge bg-success rounded-pill py-2 px-3">Inscrito</span>
          {% else %}
            <a class="btn btn-outline-primary btn-sm"
               href="{{ url_for('inscribirse_actividad', actividad_id=act.id) }}">Inscribirse</a>
          {% endif %}
        </div>
      </li>
    {% else %}
      <li class="list-group-item text-center">No hay actividades disponibles por ahora.</li>
    {% endfor %}
  </ul>
</section>
{% endblock %}
'''

# ---------------- PERFIL ----------------
html_perfil = '''
{% block body %}
<section class="va-card w-100" style="max-width:880px;">
  <h2 class="fw-bold text-center mb-4">Mi perfil</h2>

  <div class="row g-5">
    <div class="col-md-5">
      <h5 class="fw-semibold mb-3">Información personal</h5>
      <ul class="list-group list-group-flush">
        <li class="list-group-item"><strong>Nombre:</strong> {{ current_user.nombre }}</li>
        <li class="list-group-item"><strong>Correo:</strong> {{ current_user.email }}</li>
        <li class="list-group-item"><strong>Rol:</strong> {{ current_user.rol }}</li>
        <li class="list-group-item"><strong>Horas:</strong> {{ current_user.horas_voluntariado }}</li>
      </ul>
      <a href="{{ url_for('generar_reporte_pdf') }}"
         class="btn btn-outline-secondary btn-sm mt-3 w-100">Descargar reporte (PDF)</a>
    </div>

    <div class="col-md-7">
      <h5 class="fw-semibold mb-3">Actividades inscritas</h5>
      <ul class="list-group">
        {% for act in current_user.actividades %}
          <li class="list-group-item d-flex justify-content-between align-items-center">
            {{ act.titulo }}
            <span class="badge bg-primary">{{ act.fecha }}</span>
          </li>
        {% else %}
          <li class="list-group-item text-center">Aún no te has inscrito en ninguna actividad.</li>
        {% endfor %}
      </ul>
    </div>
  </div>
</section>
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


# ───────────────────────────────────────────────────────────────
#  RUTA PDF COMPLETA
# ───────────────────────────────────────────────────────────────
@app.route('/generar_reporte_pdf')
@login_required
def generar_reporte_pdf():
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=3*cm, bottomMargin=3*cm
    )

    # ── estilos ──
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleBlue", parent=styles["Title"],
                              textColor=colors.HexColor("#0d6efd"), alignment=1))
    styles.add(ParagraphStyle("Heading", parent=styles["Heading3"],
                              textColor=colors.HexColor("#17c1e8")))
    styles.add(ParagraphStyle("Cell", fontSize=9, leading=11,
                              alignment=TA_LEFT, spaceBefore=0, spaceAfter=0))

    # ── CARNÉ DE VOLUNTARIO (12 cm ancho, márgenes ajustados) ──
    badge_w, badge_h = 12*cm, 7.5*cm
    badge = Drawing(badge_w, badge_h)
    badge.hAlign = "CENTER"

    corner_r = 8
    badge.add(Rect(0, 0, badge_w, badge_h,
                  rx=corner_r, ry=corner_r,
                  fillColor=colors.HexColor("#ffd600"), strokeColor=None))

    # ranura superior
    slot_w, slot_h = 2.4*cm, 0.35*cm
    badge.add(Rect((badge_w-slot_w)/2, badge_h-1.2*cm,
                  slot_w, slot_h, rx=2, ry=2,
                  fillColor=colors.whitesmoke, strokeColor=None))

    # título desplazado un poco más abajo
    badge.add(String(badge_w/2, badge_h-2.4*cm,        # ↓ antes -2.1 cm
                    "VoluntApp",
                    fontName="Helvetica-Bold", fontSize=20,
                    textAnchor="middle"))

    # caja blanca
    data_y = 1.1*cm
    data_h = badge_h - 4.1*cm
    badge.add(Rect(1*cm, data_y, badge_w-2*cm, data_h,
                  fillColor=colors.white, strokeColor=None))

    # ── textos dentro de la caja ──
    top_margin    = 1.0*cm     # margen arriba
    bottom_margin = 0.6*cm     # margen abajo reducido

    top_y    = data_y + data_h - top_margin
    bottom_y = data_y + bottom_margin
    mid_y    = (top_y + bottom_y) / 2

    badge.add(String(badge_w/2, top_y,
                    current_user.nombre,
                    fontName="Helvetica-Bold", fontSize=11,
                    textAnchor="middle"))

    badge.add(String(badge_w/2, mid_y,
                    current_user.email,
                    fontName="Helvetica", fontSize=9.5,
                    textAnchor="middle"))

    badge.add(String(badge_w/2, bottom_y,
                    f"Horas: {current_user.horas_voluntariado}",
                    fontName="Helvetica-Oblique", fontSize=9.5,
                    textAnchor="middle"))

    # ── contenido ──
    story = [
        Paragraph(f"Reporte de voluntariado de {current_user.nombre}", styles["TitleBlue"]),
        Spacer(1, 16),
        badge,
        Spacer(1, 26),
        Paragraph("Actividades inscritas", styles["Heading"]),
    ]

    datos = [["Actividad", "Descripción", "Fecha"]] + [
        [
            Paragraph(act.titulo, styles["Cell"]),
            Paragraph(act.descripcion, styles["Cell"]),
            Paragraph(act.fecha if isinstance(act.fecha, str)
                      else act.fecha.strftime("%d/%m/%Y"), styles["Cell"])
        ]
        for act in current_user.actividades
    ] or [["Sin actividades", "—", "—"]]

    tbl = Table(datos, colWidths=[4.5*cm, 9.5*cm, 3*cm], hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",     (0, 1), (-1, -1), "TOP"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.whitesmoke, colors.HexColor("#f1f5ff")]),
    ]))
    story.append(tbl)

    # ── generar PDF ──
    doc.build(story, onFirstPage=_add_header_footer, onLaterPages=_add_header_footer)

    pdf = buffer.getvalue()
    buffer.close()

    user_slug = secure_filename(current_user.nombre.replace(" ", "_"))
    filename = f"reporte_voluntariado_{user_slug}.pdf"

    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return resp


# ───────────────────────────────────────────────────────────────
#  CABECERA · PIE · MARCA DE AGUA · FIRMA
# ───────────────────────────────────────────────────────────────
def _add_header_footer(canvas, doc):
    canvas.saveState()

    # Marca de agua
    page_w, page_h = map(int, A4)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(colors.HexColor("#0d6efd"))
    if hasattr(canvas, "setFillAlpha"):
        canvas.setFillAlpha(0.10)

    step = 120
    for x in range(-page_w, int(page_w*1.4), step):
        for y in range(-page_h, int(page_h*1.4), step):
            canvas.saveState()
            canvas.translate(x, y)
            canvas.rotate(45)
            canvas.drawString(0, 0, "VoluntApp")
            canvas.restoreState()

    if hasattr(canvas, "setFillAlpha"):
        canvas.setFillAlpha(1)

    # Cabecera (solo portada)
    logo = os.path.join(app.root_path, "images", "voluntapp-banner.png")
    if os.path.exists(logo) and doc.page == 1:
        canvas.drawImage(logo, 2*cm, page_h-3*cm, width=5*cm,
                         preserveAspectRatio=True, mask='auto')

    # Pie
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1.7*cm,
                      f"Generado: {datetime.now():%d/%m/%Y %H:%M}")
    canvas.drawRightString(page_w-2*cm, 1.7*cm, f"Pág. {doc.page}")

    # sello centrado
    if os.path.exists(logo):
        sello_w = 5*cm
        sello_h = sello_w*0.25
        canvas.drawImage(logo, (page_w-sello_w)/2, 1*cm,
                         width=sello_w, height=sello_h,
                         preserveAspectRatio=True, mask='auto')

    canvas.restoreState()



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
                password=generate_password_hash('admin', method='pbkdf2:sha256'),
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

            org_data3 = Organizacion(
                nombre='Refood Tetuán',
                lat=40.4600,
                lon=-3.6988,
                descripcion='Proyecto de recuperación y redistribución de alimentos en el barrio de Tetuán.'
            )
            db.session.add(org_data3)

            org_data4 = Organizacion(
                nombre='Voluntariado UFV - Avanza',
                lat=40.4038,
                lon=-3.9691,
                descripcion='Programa de voluntariado de la Universidad Francisco de Vitoria.'
            )
            db.session.add(org_data4)

            db.session.commit()

    # Una vez todo está inicializado, corremos la app
    app.run(debug=True)
