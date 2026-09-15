from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from config import config_map

# ---------------------------------------------------------------------------
# Extensions — instantiated here, initialized inside create_app()
# ---------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"          # redirect target for @login_required
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


def create_app(config_name: str = "development") -> Flask:
    """
    Application factory.

    Args:
        config_name: one of 'development', 'testing', 'production'

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_map[config_name])

    # ------------------------------------------------------------------
    # Initialize extensions
    # ------------------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)

    # ------------------------------------------------------------------
    # Import models — MUST happen after db.init_app() so that:
    #   1. The @login_manager.user_loader decorator is registered.
    #   2. db.create_all() / seed.py can see all model classes.
    # ------------------------------------------------------------------
    with app.app_context():
        from app import models  # noqa: F401

    # ------------------------------------------------------------------
    # Register blueprints
    # ------------------------------------------------------------------
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.products.routes import products_bp
    app.register_blueprint(products_bp)

    from app.cart.routes import cart_bp
    app.register_blueprint(cart_bp)

    from app.checkout.routes import checkout_bp
    app.register_blueprint(checkout_bp)

    from app.profile.routes import profile_bp
    app.register_blueprint(profile_bp)

    # ------------------------------------------------------------------
    # Context processor — injects cart_count into every template
    # Reads from session; no DB call needed.
    # ------------------------------------------------------------------
    @app.context_processor
    def inject_globals():
        from flask import session
        cart = session.get("cart", {})
        cart_count = sum(cart.values())
        return {"cart_count": cart_count}

    # ------------------------------------------------------------------
    # Main index route
    # ------------------------------------------------------------------
    from flask import render_template

    @app.route("/")
    def index():
        from app.models import Product
        featured = Product.query.limit(4).all()
        return render_template("index.html", featured=featured)

    return app
