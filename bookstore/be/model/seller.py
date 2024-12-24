# import sys
# sys.path.append(r'D:\2024.2\DB\Task2\CDMS.Xuan_ZHOU.2024Fall.DaSE\project1\bookstore')

from be.model import error
from be.model import db_conn
import json
from sqlalchemy.exc import SQLAlchemyError
from pymongo.errors import PyMongoError
from sqlalchemy.sql import text
from be.model.times import get_time_stamp

class Seller(db_conn.DBConn):
    def __init__(self):
        db_conn.DBConn.__init__(self)

    def add_book(self, user_id: str, store_id: str, book_id: str, book_json_str: str, stock_level: int):
        try:
            # 启动事务
            with self.conn.begin():  # 使用事务上下文管理器
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)
                if not self.store_id_exist(store_id):
                    return error.error_non_exist_store_id(store_id)
                if self.store_book_id_exist(store_id, book_id):
                    return error.error_exist_book_id(book_id)

                # 尝试从 PostgreSQL 的 book 表中查找书籍
                cursor = self.conn.execute(text("SELECT * FROM book WHERE id = :book_id;"), {"book_id": book_id})
                row = cursor.fetchone()

                if row:  # 如果书籍已存在于 book 表
                    # 提取书籍的价格
                    price = row[8]  # Assuming 'price' is at index 8 in the book table

                    # 插入书籍信息到 store_book 表
                    self.conn.execute(
                        text("INSERT INTO store_book (store_id, book_id, stock_level, price) "
                            "VALUES (:store_id, :book_id, :stock_level, :price);"),
                        {"store_id": store_id, "book_id": book_id, "stock_level": stock_level, "price": price}
                    )
                    
                else:  # 如果书籍不存在于 book 表
                    # 解析传入的 JSON 格式的书籍信息
                    book_info_json = json.loads(book_json_str)
                    # 提取价格
                    price = book_info_json.get("price")
                    # 将书籍信息插入到 PostgreSQL 的 book 表
                    self.conn.execute(
                        text("INSERT INTO book (id, title, author, publisher, original_title, translator, pub_year, "
                            "pages, price, currency_unit, binding, isbn, tags) "
                            "VALUES (:id, :title, :author, :publisher, :original_title, :translator, :pub_year, :pages, "
                            ":price, :currency_unit, :binding, :isbn, :tags);"),
                        {
                            "id": book_info_json["id"],
                            "title": book_info_json["title"],
                            "author": book_info_json["author"],
                            "publisher": book_info_json["publisher"],
                            "original_title": book_info_json.get("original_title", ""),
                            "translator": book_info_json.get("translator", ""),
                            "pub_year": book_info_json.get("pub_year", ""),
                            "pages": book_info_json.get("pages", 0),
                            "price": price,
                            "currency_unit": book_info_json.get("currency_unit", ""),
                            "binding": book_info_json.get("binding", ""),
                            "isbn": book_info_json.get("isbn", ""),
                            "tags": book_info_json.get("tags", "")
                        }
                    )

                    # 将书籍的详细信息插入 MongoDB 的 book_details 数据集合
                    book_details = {
                        "book_id": book_id,
                        "author_intro": book_info_json.get("author_intro", ""),
                        "book_intro": book_info_json.get("book_intro", ""),
                        "content": book_info_json.get("content", ""),
                        "pictures": book_info_json.get("picture", None)  # Assuming it's in BLOB format
                    }
                    self.mongo['bookstore']['book_details'].insert_one(book_details)

                    # 将书籍信息插入到 store_book 表
                    self.conn.execute(
                        text("INSERT INTO store_book (store_id, book_id, stock_level, price) "
                            "VALUES (:store_id, :book_id, :stock_level, :price);"),
                        {"store_id": store_id, "book_id": book_id, "stock_level": stock_level, "price": price}
                    )

            # 事务成功时，自动提交
            return 200, "ok"

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except PyMongoError as e:
            return 529, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def add_stock_level(self, user_id: str, store_id: str, book_id: str, add_stock_level: int):
        try:
            # 启动事务
            with self.conn.begin():
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)
                if not self.store_id_exist(store_id):
                    return error.error_non_exist_store_id(store_id)
                if not self.store_book_id_exist(store_id, book_id):
                    return error.error_non_exist_book_id(book_id)

                self.conn.execute(text("UPDATE store_book SET stock_level = stock_level + :asl  WHERE store_id = :sid AND book_id = :bid"),
                                {'asl': add_stock_level, 'sid': store_id, 'bid': book_id})

            # 事务成功时，自动提交
            return 200, "ok"

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def create_store(self, user_id: str, store_id: str) -> (int, str):
        try:
            # 启动事务
            with self.conn.begin():
                if not self.user_id_exist(user_id):
                    return error.error_non_exist_user_id(user_id)
                if self.store_id_exist(store_id):
                    return error.error_exist_store_id(store_id)
                
                self.conn.execute(text("INSERT into user_store (store_id, user_id) VALUES (:sid, :uid)"), {'sid': store_id, 'uid': user_id})

            # 事务成功时，自动提交
            return 200, "ok"

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

    def send_books(self, store_id, order_id):
        try:
            # 启动事务
            with self.conn.begin():
                if not self.store_id_exist(store_id):
                    return error.error_non_exist_store_id(store_id)
                if not self.order_id_exist(order_id):   #增加order_id不存在的错误处理
                    return error.error_invalid_order_id(order_id)
                
                cursor = self.conn.execute(text(
                    "SELECT status FROM orders where order_id = :order_id"), {"order_id": order_id})
                row = cursor.fetchone()
                status = row[0]
                if status != 2:
                    return error.error_invalid_order_status(order_id)

                self.conn.execute(text(
                    "UPDATE orders set status=3, shipped_at = :current_time where order_id = :order_id ;"), 
                    {"order_id": order_id, "current_time": get_time_stamp()})

            # 事务成功时，自动提交
            return 200, "ok"

        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))

 
    