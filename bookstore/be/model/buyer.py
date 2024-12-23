import uuid
import logging
import time
from be.model import db_conn
from be.model import error
from sqlalchemy.exc import SQLAlchemyError
from pymongo.errors import PyMongoError
from sqlalchemy.sql import text
from be.model.times import get_time_stamp
#from be.model.order import Order
from be.model.encrypt import encrypt
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine, text
from pymongo import MongoClient

class Buyer(db_conn.DBConn):
    def __init__(self):
        db_conn.DBConn.__init__(self)
        self.page_size = 20
        

    # 用户下单；减少库存
    def new_order(self, user_id: str, store_id: str, id_and_count: [(str, int)]) -> (int, str, str):
        order_id = ""
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                if not self.user_id_exist(user_id):  # 判断用户是否存在
                    return error.error_non_exist_user_id(user_id) + (order_id,)
                if not self.store_id_exist(store_id):  # 判断店铺是否存在
                    return error.error_non_exist_store_id(store_id) + (order_id,)

                # 生成唯一的订单ID
                uid = "{}_{}_{}".format(user_id, store_id, str(uuid.uuid1()))
                total_price = 0
                
                # 先插入初始数据到 orders 表
                self.conn.execute(
                    text(
                        "INSERT INTO orders (order_id, store_id, user_id, status, total_price, created_at) "
                        "VALUES (:uid, :store_id, :user_id, :status, :total_price, :created_at)"
                    ),
                    {"uid": uid, "store_id": store_id, "user_id": user_id, "status": 1, "total_price": 0, "created_at": get_time_stamp()}
                )

                # 遍历书籍ID和数量，更新库存并插入 order_book 表
                for book_id, count in id_and_count:
                    cursor = self.conn.execute(
                        text(
                            "UPDATE store_book SET stock_level = stock_level - :count "
                            "WHERE store_id = :store_id AND book_id = :book_id AND stock_level >= :count "
                            "RETURNING price"
                        ),
                        {"count": count, "store_id": store_id, "book_id": book_id}
                    )
                    
                    if cursor.rowcount == 0:
                        return error.error_stock_level_low(book_id) + (order_id,)

                    # 获取价格并计算总价
                    row = cursor.fetchone()
                    price = row[0]
                    total_price += count * price

                    # 插入 order_book 表中的订单信息
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
                
                order_id = uid  # 保存生成的订单ID

            # 如果事务成功，自动提交
            return 200, "ok", order_id

        except SQLAlchemyError as e:
            logging.error(f"SQLAlchemyError occurred: {str(e)}")  # 错误日志
            return 528, "{}".format(str(e)), ""

        except BaseException as e:
            logging.error(f"BaseException occurred: {str(e)}")  # 错误日志
            return 530, "{}".format(str(e)), ""

 

    # 买家付钱；付款后减少买家余额
    def payment(self, user_id: str, password: str, order_id: str) -> (int, str):
        conn = self.conn
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
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

                if buyer_id != user_id:
                    return error.error_authorization_fail()
                if status != 1:
                    return error.error_invalid_order_status()

                cursor = conn.execute(text("SELECT balance, password FROM users WHERE user_id = :buyer_id;"),
                                    {"buyer_id": buyer_id})
                row = cursor.fetchone()
                if row is None:
                    return error.error_non_exist_user_id(buyer_id)
                balance = row[0]
                if encrypt(password) != row[1]:
                    return error.error_authorization_fail()
                if balance < total_price:
                    return error.error_not_sufficient_funds(order_id)

                # 付款后减少买家余额
                cursor = conn.execute(text("UPDATE users SET balance = balance - :total_price1 "
                                        "WHERE user_id = :buyer_id AND balance >= :total_price2"),
                                    {"total_price1": total_price, "buyer_id": buyer_id, "total_price2": total_price})
                if cursor.rowcount == 0:
                    return error.error_unknown("update_user_error")

                # 更新订单状态为已付款
                self.conn.execute(
                    text("UPDATE orders SET status = 2, paid_at = :current_time WHERE order_id = :order_id;"),
                    {"order_id": order_id, "current_time": get_time_stamp()}
                )

                # 事务成功时，自动提交
                self.conn.commit()


            return 200, "ok"

        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred: {str(e)}")  # For debugging
            return 528, "{}".format(str(e))

        except BaseException as e:
            print(f"BaseException occurred: {str(e)}")  # For debugging
            return 530, "{}".format(str(e))



    def add_funds(self, user_id, password, add_value) -> (int, str):  
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                cursor = self.conn.execute(text("SELECT password from users where user_id = :user_id"), {"user_id": user_id})
                row = cursor.fetchone()
                if row is None:
                    return error.error_authorization_fail()

                if row[0] != encrypt(password):
                    #if row[0] != password:
                    return error.error_authorization_fail()

                cursor = self.conn.execute(
                    text("UPDATE users SET balance = balance + :add_value WHERE user_id = :user_id"),
                    {"add_value": add_value, "user_id": user_id})
                if cursor.rowcount == 0:
                    return error.error_non_exist_user_id(user_id)

                # 事务成功时，自动提交
                self.conn.commit()

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"


    
    #手动收货; 修改订单状态，增加卖家收入
    def receive_books(self, user_id: str, password: str, order_id: str) -> (int, str):
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)
                if not self.order_id_exist(order_id):  
                    return error.error_invalid_order_id(order_id)

                cursor = self.conn.execute(text("SELECT order_id, user_id, store_id, total_price, status FROM orders WHERE order_id = :order_id"),
                                            {"order_id": order_id, })
                row = cursor.fetchone()

                if row is None:
                    return error.error_invalid_order_id(order_id)

                order_id = row[0]
                buyer_id = row[1]
                store_id = row[2]
                total_price = row[3]  # 总价
                status = row[4]

                if buyer_id != user_id:
                    return error.error_authorization_fail()
                if status != 3:
                    return error.error_invalid_order_status(order_id)

                cursor = self.conn.execute(text("SELECT store_id, user_id FROM user_store WHERE store_id = :store_id;"),
                                            {"store_id": store_id, })
                row = cursor.fetchone()
                if row is None:
                    return error.error_non_exist_store_id(store_id)

                seller_id = row[1]

                if not self.user_id_exist(seller_id):
                    return error.error_non_exist_user_id(seller_id)

                cursor = self.conn.execute(text("UPDATE users set balance = balance + :total_price "
                                                "WHERE user_id = :seller_id"),
                                            {"total_price": total_price, "seller_id": seller_id})

                if cursor.rowcount == 0:
                    return error.error_non_exist_user_id(buyer_id)

                self.conn.execute(
                    text("UPDATE orders SET status = 4, received_at = :current_time WHERE order_id = :order_id;"),
                    {"order_id": order_id, "current_time": get_time_stamp()}
                )

                # 事务成功时，自动提交
                self.conn.commit()

        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred: {str(e)}")  # For debugging
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"




    # 买家手动取消订单
    def user_cancel_order(self, buyer_id, order_id) -> (int, str):
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                if not self.user_id_exist(buyer_id):
                    return error.error_non_exist_user_id(buyer_id)
                if not self.order_id_exist(order_id):
                    return error.error_invalid_order_id(order_id)

                cursor = self.conn.execute(text("SELECT status FROM orders WHERE order_id = :order_id AND user_id=:user_id;"),
                                        {"order_id": order_id, "user_id": buyer_id })
                if not cursor.fetchone():
                    return error.error_authorization_fail()

                cursor = self.conn.execute(text("SELECT status, store_id, total_price FROM orders WHERE order_id = :order_id;"),
                                        {"order_id": order_id, })
                row = cursor.fetchone()

                if row[0] != 1 and row[0] != 2:  # 错误状态的订单不能被取消
                    return error.error_invalid_order_status(order_id)

                # 通过 order_id 查询 order_book 中的所有记录
                cursor = self.conn.execute(text("SELECT book_id, count FROM order_book WHERE order_id = :order_id;"),
                                            {"order_id": order_id, })
                order_books = cursor.fetchall()

                # 还原库存
                for book in order_books:
                    book_id, count = book
                    store_id = row[1]  # 获取订单中的 store_id
                    # 更新 store_book 表的 stock_level
                    self.conn.execute(text(
                        "UPDATE store_book SET stock_level = stock_level + :count WHERE store_id = :store_id AND book_id = :book_id;"),
                        {"store_id": store_id, "book_id": book_id, "count": count})

                # 如果用户已付款，还原用户支付金额
                if row[0] == 2:
                    self.conn.execute(text(
                        "UPDATE users SET balance = balance + :money WHERE user_id = :user_id;"),
                        {"money": row[2], "user_id": buyer_id})

                # 更新订单状态为 "cancelled"
                self.conn.execute(text(
                    "UPDATE orders SET status = 0 WHERE order_id = :order_id;"), {"order_id": order_id})

                # 事务成功时，自动提交
                self.conn.commit()

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

        return 200, "ok"

    

    def auto_cancel_order(self, user_id: str, order_id: str) -> (int, str):
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                # 检查用户是否存在
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)
                if not self.order_id_exist(order_id):
                    return error.error_invalid_order_id(order_id)

                cursor = self.conn.execute(text("SELECT status, store_id, created_at FROM orders WHERE order_id = :order_id;"),
                                            {"order_id": order_id, })
                row = cursor.fetchone()
                if row[0] != 1:  # 错误状态的订单不能被取消
                    return error.error_invalid_order_status(order_id)

                # 检查订单创建时间是否超过1分钟(为了方便测试)
                created_at = row[2]
                created_at = datetime.fromtimestamp(created_at, timezone.utc)  # 将时间戳转为datetime对象

                # 如果订单创建时间超过1分钟，则自动取消订单
                current_time = datetime.now(timezone.utc)  # 获取当前 UTC 时间
                if current_time - created_at > timedelta(minutes=1):
                    # 更新订单状态为 "cancelled"
                    self.conn.execute(text(
                        "UPDATE orders SET status = 0 WHERE order_id = :order_id;"), {"order_id": order_id})

                    # 事务成功时，自动提交
                    self.conn.commit()

                    return 200, "auto cancelled successfully"
                else:
                    return 403, "created time less than limit"

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))



    #查看历史订单
    def get_orders(self, user_id: str) -> (int, list):
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                # 检查用户是否存在
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)

                # 查询用户的所有历史订单，状态为 0 或 4
                result = self.conn.execute(text(
                    "SELECT order_id FROM orders WHERE user_id = :user_id AND status IN (0, 4);"
                ), {"user_id": user_id}).fetchall()

                # 提取订单号
                order_list = [order[0] for order in result]

                # 返回状态码和订单号列表
                return 200, order_list

            # 事务成功时，自动提交

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))




    def search_books(self, search_key, store_id=None, page=1):
        try:
            # 计算分页偏移量
            offset = (page - 1) * self.page_size

            # 处理搜索关键词（去掉不必要的空格或特殊字符）
            search_key = search_key.strip()

            # 基础 PostgreSQL 查询
            base_query = """
                SELECT id, title, tags 
                FROM book 
                WHERE search_vector @@ to_tsquery(:search_key)
            """

            if store_id:
                base_query += " AND id IN (SELECT book_id FROM store_book WHERE store_id = :store_id)"
            base_query += " ORDER BY id LIMIT :limit OFFSET :offset"

            # 执行 PostgreSQL 查询
            with self.conn as conn:
                result = conn.execute(
                    text(base_query),
                    {
                        "search_key": search_key,
                        "store_id": store_id,
                        "limit": self.page_size,
                        "offset": offset,
                    },
                ).fetchall()

            print(search_key)
            
            # 整理 PostgreSQL 查询结果
            books = [
                {
                    "id": row[0],
                    "title": row[1],
                    "tags": row[2],
                }
                for row in result
            ]

            # 从 MongoDB 查询书籍详细信息
            book_ids = [book["id"] for book in books]
            mongo_details = list(self.mongo.book_details.find({"book_id": {"$in": book_ids}}, {"_id": 0}))

            # 合并 PostgreSQL 和 MongoDB 的结果
            for book in books:
                details = next((item for item in mongo_details if item["book_id"] == book["id"]), {})
                book.update(details)
            
            return 200, "ok", books

        except SQLAlchemyError as e:
            print(f"SQLAlchemyError occurred: {str(e)}")  # For debugging
            #error_details = format_Sexc()  # 获取完整的堆栈信息
            logging.error(f"PostgreSQL Error: {str(e)}\nDetails: {error_details}")
            return 528, f"PostgreSQL Error: {str(e)}", []
        except PyMongoError as e:
            logging.error(f"MongoDB Error: {str(e)}")
            return 529, f"MongoDB Error: {str(e)}", []
        except Exception as e:
            logging.error(f"Unknown Error: {str(e)}")
            return 530, f"Unknown Error: {str(e)}", []

