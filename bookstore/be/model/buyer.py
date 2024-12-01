import uuid
import logging
from be.model import db_conn
from be.model import error
from sqlalchemy.exc import SQLAlchemyError
from pymongo.errors import PyMongoError
from sqlalchemy.sql import text
from be.model.times import add_unpaid_order, delete_unpaid_order, check_order_time, get_time_stamp
#from be.model.order import Order
#from be.model.nlp import encrypt

class Buyer(db_conn.DBConn):
    def __init__(self):
        db_conn.DBConn.__init__(self)
        self.page_size = 3

    # 用户下单 买家用户ID,商铺ID,书籍购买列表(书籍购买列表,购买数量)
    def new_order(self, user_id: str, store_id: str, id_and_count: [(str, int)]) -> (int, str, str):
        order_id = ""
        try:
            if not self.user_id_exist(user_id):  # 判断user存在否
                return error.error_non_exist_user_id(user_id) + (order_id,)
            if not self.store_id_exist(store_id):  # 判断store存在否
                return error.error_non_exist_store_id(store_id) + (order_id,)
            
            uid = "{}_{}_{}".format(user_id, store_id, str(uuid.uuid1()))#保证唯一性
            total_price = 0
            #先插入初始数据到orders
            self.conn.execute(
                text(
                    "INSERT INTO orders (order_id, store_id, user_id, total_price, created_at) "
                    "VALUES (:uid, :store_id, :user_id, :total_price, :created_at)"
                ),
                {"uid": uid, "store_id": store_id, "user_id": user_id, "total_price": 0, "created_at": get_time_stamp()}
            )
            print("\n5555555555555\n")
            for book_id, count in id_and_count:
                # 使用 text() 包裹 SQL 查询
                cursor = self.conn.execute(
                    text(
                        "UPDATE store_book SET stock_level = stock_level - :count "
                        "WHERE store_id = :store_id AND book_id = :book_id AND stock_level >= :count "
                        "RETURNING price"
                    ),
                    {"count": count, "store_id": store_id, "book_id": book_id}
                )
                if cursor.rowcount == 0:
                    self.conn.rollback()
                    return error.error_stock_level_low(book_id) + (order_id,)
                row = cursor.fetchone()
                price = row[0]
                # 计算总价
                total_price += count * price

                # 创建新订单信息, 使用 order_book 表
                self.conn.execute(
                    text(
                        "INSERT INTO order_book (order_id, book_id, count) "
                        "VALUES (:uid, :book_id, :count)"
                    ),
                    {"uid": uid, "book_id": book_id, "count": count}
                )

            # 更新 orders 表中的 total_price
            self.conn.execute(
                text(
                    "UPDATE orders SET total_price = :total_price WHERE order_id = :uid"
                ),
                {"uid": uid, "total_price": total_price}
            )
            self.conn.commit()
            order_id = uid

            # 增加订单到未支付订单数组
            #add_unpaid_order(order_id)
        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred: {str(e)}")  # For debugging
            #logging.info("528, {}".format(str(e)))
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            print(f"BaseException occurred: {str(e)}")  # For debugging
            #logging.info("530, {}".format(str(e)))
            return 530, "{}".format(str(e)), ""

        return 200, "ok", order_id

    # 买家付钱
    def payment(self, user_id: str, password: str, order_id: str) -> (int, str):
        conn = self.conn
        try:
            print("\n00000000000000\n")
            cursor = conn.execute(text("SELECT * FROM orders WHERE order_id = :order_id"),
                                  {"order_id": order_id})
            row = cursor.fetchone()
            if row is None:
                return error.error_invalid_order_id(order_id)

            order_id = row[0]
            buyer_id = row[1]
            store_id = row[2]
            total_price = row[4]  # 总价
            order_time = row[5]
            status = row[3]

            print("\n11111111111111111\n")

            if buyer_id != user_id:
                return error.error_authorization_fail()
            if status != 1:
                return error.error_invalid_order_status()
            '''
            if check_order_time(order_time) is False:
                self.conn.commit()
                delete_unpaid_order(order_id)
                o = Order()
                o.cancel_order(order_id)
                return error.error_invalid_order_id()
            '''
            print("\n222222222222\n")
            cursor = conn.execute(text("SELECT balance, password FROM users WHERE user_id = :buyer_id;"),
                                  {"buyer_id": buyer_id})
            row = cursor.fetchone()
            if row is None:
                return error.error_non_exist_user_id(buyer_id)
            balance = row[0]
            #if encrypt(password) != row[1]:
            if password != row[1]:
                return error.error_authorization_fail()
            if balance < total_price:
                return error.error_not_sufficient_funds(order_id)

            # 付款后减少买家余额
            cursor = conn.execute(text("UPDATE users SET balance = balance - :total_price1 "
                                       "WHERE user_id = :buyer_id AND balance >= :total_price2"),
                                  {"total_price1": total_price, "buyer_id": buyer_id, "total_price2": total_price})
            if cursor.rowcount == 0:
                return error.error_unknown("update_user_error")

            self.conn.execute(
                text("UPDATE orders SET status = 2, paid_at = :current_time WHERE order_id = :order_id;"),
                {"order_id": order_id, "current_time": get_time_stamp()}
            )
            
            #增加卖家的余额
            cursor = conn.execute(text("SELECT store_id, user_id FROM user_store WHERE store_id = :store_id;"),
                {"store_id":store_id},
            )
            row = cursor.fetchone()
            if row is None:
                return error.error_non_exist_store_id(store_id)

            seller_id = row[1]

            cursor = conn.execute(text("SELECT balance FROM users WHERE user_id = :seller_id;"),
                              {"seller_id": seller_id})  
            seller_row = cursor.fetchone()
            if seller_row is None:
                return error.error_non_exist_user_id(seller_id)
            
            seller_balance = seller_row[0]
            new_seller_balance = seller_balance + total_price

            cursor = conn.execute(text("UPDATE users SET balance = :new_balance WHERE user_id = :seller_id;"),
                                {"new_balance": new_seller_balance, "seller_id": seller_id})
            if cursor.rowcount == 0:
                return error.error_unknown("update_seller_balance_error")

            self.conn.commit()

            # 从未支付订单数组中删除
            #delete_unpaid_order(order_id)

        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred: {str(e)}")  # For debugging
            return 528, "{}".format(str(e))
        except BaseException as e:
            print(f"BaseException occurred: {str(e)}")  # For debugging
            return 530, "{}".format(str(e))

        return 200, "ok"
    
   # 买家充值 
    def add_funds(self, user_id, password, add_value) -> (int, str):  
        try:
            cursor = self.conn.execute(text("SELECT password from users where user_id = :user_id"), {"user_id": user_id})
            row = cursor.fetchone()
            if row is None:
                return error.error_authorization_fail()

            #if row[0] != encrypt(password):
            if row[0] != password:
                return error.error_authorization_fail()

            cursor = self.conn.execute(
                text("UPDATE users SET balance = balance + :add_value WHERE user_id = :user_id"),
                {"add_value": add_value, "user_id": user_id})
            if cursor.rowcount == 0:
                return error.error_non_exist_user_id(user_id)

            self.conn.commit()
        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"

   

'''
class Buyer(db_conn.DBConn):
    def __init__(self):
        db_conn.DBConn.__init__(self)

    def new_order(
        self, user_id: str, store_id: str, id_and_count: [(str, int)]
    ) -> (int, str, str):
        order_id = ""
        try:
            if not self.user_id_exist(user_id):
                return error.error_non_exist_user_id(user_id) + (order_id,)
            if not self.store_id_exist(store_id):
                return error.error_non_exist_store_id(store_id) + (order_id,)
            uid = "{}_{}_{}".format(user_id, store_id, str(uuid.uuid1()))

            for book_id, count in id_and_count:
                cursor = self.conn.execute(
                    "SELECT book_id, stock_level, book_info FROM store "
                    "WHERE store_id = ? AND book_id = ?;",
                    (store_id, book_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return error.error_non_exist_book_id(book_id) + (order_id,)

                stock_level = row[1]
                book_info = row[2]
                book_info_json = json.loads(book_info)
                price = book_info_json.get("price")

                if stock_level < count:
                    return error.error_stock_level_low(book_id) + (order_id,)

                cursor = self.conn.execute(
                    "UPDATE store set stock_level = stock_level - ? "
                    "WHERE store_id = ? and book_id = ? and stock_level >= ?; ",
                    (count, store_id, book_id, count),
                )
                if cursor.rowcount == 0:
                    return error.error_stock_level_low(book_id) + (order_id,)

                self.conn.execute(
                    "INSERT INTO new_order_detail(order_id, book_id, count, price) "
                    "VALUES(?, ?, ?, ?);",
                    (uid, book_id, count, price),
                )

            self.conn.execute(
                "INSERT INTO new_order(order_id, store_id, user_id) "
                "VALUES(?, ?, ?);",
                (uid, store_id, user_id),
            )
            self.conn.commit()
            order_id = uid
        except sqlite.Error as e:
            logging.info("528, {}".format(str(e)))
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            logging.info("530, {}".format(str(e)))
            return 530, "{}".format(str(e)), ""

        return 200, "ok", order_id

    def payment(self, user_id: str, password: str, order_id: str) -> (int, str):
        conn = self.conn
        try:
            cursor = conn.execute(
                "SELECT order_id, user_id, store_id FROM new_order WHERE order_id = ?",
                (order_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return error.error_invalid_order_id(order_id)

            order_id = row[0]
            buyer_id = row[1]
            store_id = row[2]

            if buyer_id != user_id:
                return error.error_authorization_fail()

            cursor = conn.execute(
                "SELECT balance, password FROM user WHERE user_id = ?;", (buyer_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return error.error_non_exist_user_id(buyer_id)
            balance = row[0]
            if password != row[1]:
                return error.error_authorization_fail()

            cursor = conn.execute(
                "SELECT store_id, user_id FROM user_store WHERE store_id = ?;",
                (store_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return error.error_non_exist_store_id(store_id)

            seller_id = row[1]

            if not self.user_id_exist(seller_id):
                return error.error_non_exist_user_id(seller_id)

            cursor = conn.execute(
                "SELECT book_id, count, price FROM new_order_detail WHERE order_id = ?;",
                (order_id,),
            )
            total_price = 0
            for row in cursor:
                count = row[1]
                price = row[2]
                total_price = total_price + price * count

            if balance < total_price:
                return error.error_not_sufficient_funds(order_id)

            cursor = conn.execute(
                "UPDATE user set balance = balance - ?"
                "WHERE user_id = ? AND balance >= ?",
                (total_price, buyer_id, total_price),
            )
            if cursor.rowcount == 0:
                return error.error_not_sufficient_funds(order_id)

            cursor = conn.execute(
                "UPDATE user set balance = balance + ?" "WHERE user_id = ?",
                (total_price, seller_id),
            )

            if cursor.rowcount == 0:
                return error.error_non_exist_user_id(seller_id)

            cursor = conn.execute(
                "DELETE FROM new_order WHERE order_id = ?", (order_id,)
            )
            if cursor.rowcount == 0:
                return error.error_invalid_order_id(order_id)

            cursor = conn.execute(
                "DELETE FROM new_order_detail where order_id = ?", (order_id,)
            )
            if cursor.rowcount == 0:
                return error.error_invalid_order_id(order_id)

            conn.commit()

        except sqlite.Error as e:
            return 528, "{}".format(str(e))

        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"

    def add_funds(self, user_id, password, add_value) -> (int, str):
        try:
            cursor = self.conn.execute(
                "SELECT password  from user where user_id=?", (user_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return error.error_authorization_fail()

            if row[0] != password:
                return error.error_authorization_fail()

            cursor = self.conn.execute(
                "UPDATE user SET balance = balance + ? WHERE user_id = ?",
                (add_value, user_id),
            )
            if cursor.rowcount == 0:
                return error.error_non_exist_user_id(user_id)

            self.conn.commit()
        except sqlite.Error as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"
'''