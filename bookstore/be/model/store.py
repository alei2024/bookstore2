import logging
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError
import pymongo
from sqlalchemy import text
import bson
import threading

class Store:
    database: str

    def __init__(self):
        self.engine = create_engine('postgresql://postgres:Tp123123@127.0.0.1:5432/bookstore') # 本地服务器
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.init_tables()

    def init_tables(self):
        try:
            conn = self.get_db_conn()

            # Create tables for users, user_store, store_book, orders, order_book
            conn.execute(
                text("CREATE TABLE IF NOT EXISTS users ("
                     "user_id TEXT PRIMARY KEY, password TEXT NOT NULL, "
                     "balance INTEGER NOT NULL DEFAULT 0, token TEXT, terminal TEXT);")
            )

            conn.execute(
                text("CREATE TABLE IF NOT EXISTS user_store ("
                     "user_id TEXT, store_id TEXT PRIMARY KEY, "
                     "FOREIGN KEY (user_id) REFERENCES users(user_id));")
            )

            conn.execute(
                text("CREATE TABLE IF NOT EXISTS store_book ("
                     "store_id TEXT, book_id TEXT, stock_level INTEGER, price INTEGER, "
                     "PRIMARY KEY(store_id, book_id), "
                     "FOREIGN KEY (store_id) REFERENCES user_store(store_id), "
                     "FOREIGN KEY (book_id) REFERENCES book(id));")
            )

            conn.execute(
                text("CREATE TABLE IF NOT EXISTS orders ("
                     "order_id TEXT PRIMARY KEY, user_id TEXT, store_id TEXT, "
                     "status INTEGER DEFAULT 1, total_price INTEGER, created_at INTEGER, "
                     "paid_at INTEGER, shipped_at INTEGER, received_at INTEGER, "
                     "FOREIGN KEY (user_id) REFERENCES users(user_id), "
                     "FOREIGN KEY (store_id) REFERENCES user_store(store_id));")
            )

            conn.execute(
                text("CREATE TABLE IF NOT EXISTS order_book ("
                     "order_id TEXT, book_id TEXT, count INTEGER, "
                     "PRIMARY KEY(order_id, book_id), "
                     "FOREIGN KEY (order_id) REFERENCES orders(order_id), "
                     "FOREIGN KEY (book_id) REFERENCES book(id));")
            )

            conn.commit()

            # Initialize MongoDB collections
            mongo_db = self.client["bookstore"]
            self.book_details_collection = mongo_db["book_details"]
            self.book_details_collection.create_index([("book_id", 1)], unique=True)

        except SQLAlchemyError as e:
            logging.error(e)
            conn.rollback()

    def get_db_conn(self):
        self.Base = declarative_base()
        self.metadata = MetaData()
        self.DBSession = sessionmaker(bind=self.engine)
        self.conn = self.DBSession()
        return self.conn

    def get_db_mongo(self):
        return self.client["bookstore"]

# database_instance: Store = Store()
database_instance: Store = None
# global variable for database sync
init_completed_event = threading.Event()

def init_database():
    global database_instance
    database_instance = Store()

def get_db_conn():
    global database_instance
    return database_instance.get_db_conn()

def get_db_mongo():
    global database_instance
    return database_instance.get_db_mongo()
