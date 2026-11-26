from flask import Blueprint


root_bp = Blueprint("root", __name__)


@root_bp.get("/")
def index():
    return {"message": "Welcome to Payment Endpoint API!"}, 200