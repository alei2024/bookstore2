from be.model import store
from sqlalchemy.sql import text

class DBConn:
    def __init__(self):
        self.conn = store.get_db_conn()
        self.mongo = store.get_db_mongo()

    def user_id_exist(self, user_id):

        cursor = self.conn.execute(text(
            "SELECT user_id FROM users WHERE user_id = :user_id;"), {"user_id":user_id}
        )
        row = cursor.fetchone()

        if row is None:
            return False
        else:
            return True

    def book_id_exist(self, book_id):
        cursor = self.conn.execute(text(
            "SELECT * FROM book WHERE book_id = :book_id;"),{"book_id":book_id}
        )
        row = cursor.fetchone()
        if row is None:
            return False
        else:
            return True

    def store_book_id_exist(self, store_id, book_id):
        cursor = self.conn.execute(text(
            "SELECT book_id FROM store_book WHERE store_id = :store_id AND book_id = :book_id;"),
            {"store_id":store_id, "book_id":book_id}
        )
        row = cursor.fetchone()
        if row is None:
            return False
        else:
            return True
        
    def store_id_exist(self, store_id):
        cursor = self.conn.execute(text(
            "SELECT store_id FROM user_store WHERE store_id = :store_id;"), {"store_id":store_id}
        )
        row = cursor.fetchone()
        if row is None:
            return False
        else:
            return True
    
    def order_id_exist(self, order_id):
        cursor = self.conn.execute(text("SELECT order_id FROM orders WHERE order_id = :order_id;"), {"order_id":order_id})
        row = cursor.fetchone()
        if row is None:
            return False
        else:
            return True
