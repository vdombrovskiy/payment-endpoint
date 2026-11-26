from flask import Flask

from app.config import Settings
from app.extensions import db, migrate


def create_app(config_overrides=None):
    app = Flask(__name__)

    settings = Settings()

    app.config.from_mapping(
        SECRET_KEY=settings.secret_key,
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=settings.debug,
    )

    if config_overrides:
        app.config.update(config_overrides)

    from app import models

    db.init_app(app)
    migrate.init_app(app, db)

    from app.api.root import root_bp
    from app.api.payments import payments_bp

    app.register_blueprint(root_bp)
    app.register_blueprint(payments_bp)

    return app

