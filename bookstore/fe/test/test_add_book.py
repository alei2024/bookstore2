import pytest
import json
from fe import conf
from fe.access.new_seller import register_new_seller
from fe.access import book
import uuid


class TestAddBook:
    @pytest.fixture(autouse=True)
    def pre_run_initialization(self):
        # do before test
        self.seller_id = "test_add_books_seller_id_{}".format(str(uuid.uuid1()))
        self.store_id = "test_add_books_store_id_{}".format(str(uuid.uuid1()))
        self.password = self.seller_id
        self.seller = register_new_seller(self.seller_id, self.password)

        code = self.seller.create_store(self.store_id)
        assert code == 200
        book_db = book.BookDB(conf.Use_Large_DB)
        self.books = book_db.get_book_info(0, 2)
        yield
        # do after test

    def test_ok(self):
        for b in self.books:
            code = self.seller.add_book(self.store_id, 0, b)
            assert code == 200

    def test_error_non_exist_store_id(self):
        for b in self.books:
            # non exist store id
            code = self.seller.add_book(self.store_id + "x", 0, b)
            assert code != 200

    def test_error_exist_book_id(self):
        for b in self.books:
            code = self.seller.add_book(self.store_id, 0, b)
            assert code == 200
        for b in self.books:
            # exist book id
            code = self.seller.add_book(self.store_id, 0, b)
            assert code != 200

    def test_error_non_exist_user_id(self):
        for b in self.books:
            # non exist user id
            self.seller.seller_id = self.seller.seller_id + "_x"
            code = self.seller.add_book(self.store_id, 0, b)
            assert code != 200

    def test_add_book_with_new_book(self):
        new_book_info = {
            "id": "new_book_123",
            "title": "新书标题",
            "author": "新作者",
            "publisher": "新出版社",
            "price": 100,
            "currency_unit": "CNY",
            "binding": "硬壳",
            "isbn": "1234567890",
            "tags": "小说"
        }

        # 创建 Book 实例并手动赋值
        new_book = book.Book()
        new_book.id = new_book_info["id"]
        new_book.title = new_book_info["title"]
        new_book.author = new_book_info["author"]
        new_book.publisher = new_book_info["publisher"]
        new_book.price = new_book_info["price"]
        new_book.currency_unit = new_book_info["currency_unit"]
        new_book.binding = new_book_info["binding"]
        new_book.isbn = new_book_info["isbn"]
        
        # 处理 tags 字段
        new_book.tags = new_book_info["tags"].split(",")  # 根据实际情况修改

        # 将 new_book 转换为字典并生成 JSON 字符串
        # book_json_str = json.dumps(new_book.__dict__)  # 不需要这个转换了

        print(f"self.seller_id: {self.seller_id}\n")
        print(f"self.store_id: {self.store_id}\n")
        print(f"new_book.id: {new_book.id}\n")
        print(f"stock_level: 10\n")

        # 调用 add_book 方法时传递 book 实例
        code = self.seller.add_book(self.store_id, 10, new_book)

        # 打印响应内容以帮助调试
        print(f"Response code: {code}")
        
        # 验证返回的 code 是否为 200
        assert code == 200

