import sqlite3
import psycopg2  # PostgreSQL
import bson  # For MongoDB Binary
from pymongo import MongoClient

# 数据库连接配置
postgres_conn_info = {
    'dbname': 'bookstore',
    'user': 'postgres',
    'password': 'Tp123123',
    'host': 'localhost',
    'port': '5432'
}

# 连接到SQLite数据库
sqlite_conn = sqlite3.connect('D:/2024.2/DB/Task2/cdms.xuan_zhou.2024fall.dase/project1/bookstore/fe/data/book.db')
sqlite_cursor = sqlite_conn.cursor()

# 创建PostgreSQL连接
postgres_conn = psycopg2.connect(**postgres_conn_info)
postgres_cursor = postgres_conn.cursor()

# 连接到MongoDB
mongo_conn_info = 'mongodb://localhost:27017/'
mongo_client = MongoClient(mongo_conn_info)
mongo_db = mongo_client['bookstore']    # 创建名为 bookstore 的数据库
mongo_collection = mongo_db['book_details']  # 创建名为 book_details 的数据集合
mongo_collection.create_index([("book_id", 1)], unique=True)  # 为 book_id 创建唯一索引

# 迁移数据的函数
def migrate_data():
    # 获取SQLite数据库中的所有数据
    sqlite_cursor.execute('SELECT * FROM book')
    rows = sqlite_cursor.fetchall()
    
    for row in rows:
        # 解析数据
        book_id, title, author, publisher, original_title, translator, pub_year, pages, price, currency_unit, binding, isbn, author_intro, book_intro, content, tags, picture = row
        
        # 将需要存储到MongoDB的数据组装成文档
        mongo_document = {
            "book_id": book_id,
            "author_intro": author_intro,
            "book_intro": book_intro,
            "content": content,
        }
        if picture:  # 如果图片存在，添加到文档
            mongo_document["picture"] = bson.Binary(picture)
        
        # 保存到MongoDB
        mongo_collection.update_one(
            {"book_id": book_id},
            {"$set": mongo_document},
            upsert=True
        )
        
        # 将需要存储到PostgreSQL的数据迁移
        postgres_cursor.execute("""
            INSERT INTO book (id, title, author, publisher, original_title, translator, pub_year, pages, price, currency_unit, binding, isbn, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (book_id, title, author, publisher, original_title, translator, pub_year, pages, price, currency_unit, binding, isbn, tags))
        
        # 提交PostgreSQL事务
        postgres_conn.commit()

    print("Data Migration Completed Successfully!")

# 运行迁移函数
migrate_data()

# 关闭连接
sqlite_conn.close()
postgres_cursor.close()
postgres_conn.close()
mongo_client.close()
