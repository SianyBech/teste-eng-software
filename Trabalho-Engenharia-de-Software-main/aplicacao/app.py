import sys
from pathlib import Path

sys.dont_write_bytecode = True

from sqlalchemy import inspect, text

from flask import Flask
from flask_login import LoginManager

from controller.inicioController import inicio_bp
from controller.pecaController import pecas_bp
from controller.authController import auth_bp
from controller.agendamentoController import agendamentos_bp
from model.models import db
from model.usuario import Usuario

ROOT_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = ROOT_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def create_app(config=None):
    app = Flask(
        __name__,
        template_folder="view",
        instance_path=str(INSTANCE_DIR),
    )
    app.config.from_mapping(
        SECRET_KEY="chave-de-desenvolvimento",
        SQLALCHEMY_DATABASE_URI="sqlite:///teatro.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=str(INSTANCE_DIR / "uploads"),
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )
    if config:
        app.config.update(config)

    db.init_app(app)

    # Configuração do Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Acesso restrito ao Gestor. Faça login para continuar."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # Registros dos Blueprints
    app.register_blueprint(inicio_bp)   #aqui
    app.register_blueprint(pecas_bp)
    app.register_blueprint(agendamentos_bp)
    app.register_blueprint(auth_bp)  
    with app.app_context():
        db.create_all()
        Usuario.criar_gestor_padrao(username="admin", senha="123")
        colunas_peca = {
            coluna["name"] for coluna in inspect(db.engine).get_columns("peca")
        }
        if "poster_filename" not in colunas_peca:
            db.session.execute(
                text("ALTER TABLE peca ADD COLUMN poster_filename VARCHAR(255)")
            )
            db.session.commit()
        if "ficha_tecnica" not in colunas_peca:
            db.session.execute(
                text(
                    "ALTER TABLE peca ADD COLUMN ficha_tecnica TEXT "
                    "NOT NULL DEFAULT ''"
                )
            )
            db.session.commit()
        if "mes" not in colunas_peca:
            db.session.execute(
                text(
                    "ALTER TABLE peca ADD COLUMN mes VARCHAR(20) "
                    "NOT NULL DEFAULT ''"
                )
            )
            db.session.commit()
    return app
   
               

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
