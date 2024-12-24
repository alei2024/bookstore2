import pytest
from fe.access.buyer import Buyer
from fe.test.gen_book_data import GenBook
from fe.access.new_buyer import register_new_buyer
from fe.access.book import Book
import uuid


class TestSearchBooks:
    seller_id: str
    store_id: str
    buyer_id: str
    password: str
    gen_book: GenBook
    buyer: Buyer

    @pytest.fixture(autouse=True)
    def pre_run_initialization(self):
        # 初始化卖家和书店信息
        self.seller_id = "test_search_books_seller_id_{}".format(str(uuid.uuid1()))
        self.store_id = "test_search_books_store_id_{}".format(str(uuid.uuid1()))
        self.buyer_id = "test_search_books_buyer_id_{}".format(str(uuid.uuid1()))
        self.password = "test_password"
        self.gen_book = GenBook(self.seller_id, self.store_id)

        # 生成图书数据
        ok, _ = self.gen_book.gen(
            non_exist_book_id=False, low_stock_level=False, max_book_count=5
        )
        assert ok

        # 注册买家
        b = register_new_buyer(self.buyer_id, self.password)
        self.buyer = b
        yield

    def test_search_in_store(self):
        # 在指定书店搜索图书
        search_key = self.gen_book.buy_book_info_list[0][0].title[:3]
        code, message, books = self.buyer.search_books(search_key, self.store_id, page=1)
        assert code == 200
        for book in books:
            assert search_key in book["title"]

    def test_search_full_site(self):
        # 全站搜索图书
        search_key = self.gen_book.buy_book_info_list[0][0].title[:3]
        code, message, books = self.buyer.search_books(search_key, None, page=1)
        assert code == 200
        for book in books:
            assert search_key in book["title"]

    def test_search_pagination(self):
        # 搜索结果分页
        search_key = ""
        code, message, books_page_1 = self.buyer.search_books(search_key, None, page=1)
        code, message, books_page_2 = self.buyer.search_books(search_key, None, page=2)

        assert code == 200


    def test_search_no_result(self):
        # 搜索无结果
        search_key = "nonexistent_key"
        code, message, books = self.buyer.search_books(search_key, None, page=1)
        assert code == 200
        assert len(books) == 0
