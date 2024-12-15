from flask import Blueprint
from flask import request
from flask import jsonify
from be.model.buyer import Buyer

bp_buyer = Blueprint("buyer", __name__, url_prefix="/buyer")


@bp_buyer.route("/new_order", methods=["POST"])
def new_order():
    user_id: str = request.json.get("user_id")
    store_id: str = request.json.get("store_id")
    books: [] = request.json.get("books")
    id_and_count = []
    for book in books:
        book_id = book.get("id")
        count = book.get("count")
        id_and_count.append((book_id, count))

    b = Buyer()
    code, message, order_id = b.new_order(user_id, store_id, id_and_count)
    return jsonify({"message": message, "order_id": order_id}), code


@bp_buyer.route("/payment", methods=["POST"])
def payment():
    user_id: str = request.json.get("user_id")
    order_id: str = request.json.get("order_id")
    password: str = request.json.get("password")
    b = Buyer()
    code, message = b.payment(user_id, password, order_id)
    return jsonify({"message": message}), code


@bp_buyer.route("/add_funds", methods=["POST"])
def add_funds():
    user_id = request.json.get("user_id")
    password = request.json.get("password")
    add_value = request.json.get("add_value")
    b = Buyer()
    code, message = b.add_funds(user_id, password, add_value)
    return jsonify({"message": message}), code

# 收货
@bp_buyer.route("/receive_books", methods=["POST"])
def receive_books():
    user_id: str = request.json.get("user_id")
    order_id: str = request.json.get("order_id")
    password: str = request.json.get("password")
    b = Buyer()
    code, message = b.receive_books(user_id, password, order_id)

    return jsonify({"message": message}), code



# 用户主动取消订单路由
@bp_buyer.route("/user_cancel_order", methods=["POST"])
def user_cancel_order():
    user_id = request.json.get("user_id")
    order_id = request.json.get("order_id")
    b = Buyer()
    code, message = b.user_cancel_order(user_id, order_id)
    return jsonify({"message": message}), code

# 自动取消订单路由
@bp_buyer.route("/auto_cancel_order", methods=["POST"])
def auto_cancel_order():
    user_id = request.json.get("user_id")
    order_id = request.json.get("order_id")
    b = Buyer()
    code, message = b.auto_cancel_order(user_id, order_id)
    return jsonify({"message": message}), code

# 查询历史订单路由
@bp_buyer.route("/get_orders", methods=["POST"])
def get_orders():
    user_id = request.json.get("user_id")
    b = Buyer()
    code, result = b.get_orders(user_id)
    return jsonify({"orders": result if code == 200 else [], "message": result if code != 200 else "ok"}), code