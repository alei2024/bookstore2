import logging
from be.model.store import init_database, get_db_conn, get_db_mongo
from sqlalchemy import text

# 设置日志级别
logging.basicConfig(level=logging.INFO)

def test_create_tables():
    try:
        # 初始化数据库
        #db_path = "test_db"  # 这里可以指定一个虚拟路径，或者直接使用默认的 PostgreSQL 数据库
        init_database()

        # 获取数据库连接
        conn = get_db_conn()

        # 检查 PostgreSQL 表是否存在

        result = conn.execute(
    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
)
        tables = [row[0] for row in result]
        
        # 打印所有创建的表
        logging.info("Tables in PostgreSQL: %s", tables)
        
        # 验证表的创建
        expected_tables = ['users', 'user_store', 'store_book', 'orders', 'order_book']
        for table in expected_tables:
            if table not in tables:
                logging.error(f"Table {table} not created!")
                return False
            else:
                logging.info(f"Table {table} exists!")

        # 检查 MongoDB 集合是否创建
        mongo_db = get_db_mongo()
        collections = mongo_db.list_collection_names()
        logging.info("Collections in MongoDB: %s", collections)
        if "book_details" not in collections:
            logging.error("book_details collection not found!")
            return False
        else:
            logging.info("book_details collection exists in MongoDB!")

        # 如果一切正常
        logging.info("All tables and collections have been created successfully!")
        return True

    except Exception as e:
        logging.error("Error during testing: %s", str(e))
        return False

if __name__ == "__main__":
    success = test_create_tables()
    if success:
        logging.info("Database setup is successful!")
    else:
        logging.error("Database setup failed!")
