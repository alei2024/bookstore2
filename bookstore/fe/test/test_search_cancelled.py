#import json
#from fe.access.new_buyer import register_new_buyer_auth
#from fe.access.new_seller import register_new_seller
#from fe.access import buyer,auth
#from fe import conf
import uuid
#from bookstore.be.model.buyer import Buyer
#import time
import pytest
from fe.access.new_buyer import register_new_buyer
from fe.test.gen_book_data import GenBook
import uuid
import time

class TestOrder:
    @pytest.fixture(autouse=True)
    def pre_run_initialization(self):
        self.seller_id = "test_order_seller_id_{}".format(str(uuid.uuid1()))
        self.store_id = "test_order_store_id_{}".format(str(uuid.uuid1()))
        self.buyer_id = "test_order_buyer_id_{}".format(str(uuid.uuid1()))
        self.password = self.seller_id
        self.buyer = register_new_buyer(self.buyer_id, self.password)
        self.gen_book = GenBook(self.seller_id, self.store_id)
        self.seller = self.gen_book.get_seller()
        ok, buy_book_id_list = self.gen_book.gen(non_exist_book_id=False, low_stock_level=False)
        assert ok
        code, self.order_id = self.buyer.new_order(self.store_id, buy_book_id_list)
        assert code == 200
        yield

    
    def test_user_cancel_order_ok1(self):
        # 正常取消未支付订单测试
        code = self.buyer.user_cancel_order(self.order_id)
        assert code == 200

    def test_user_cancel_order_ok2(self):
        # 正常取消已支付订单测试
        code = self.buyer.add_funds(1000000000)
        code = self.buyer.payment(self.order_id)
        code = self.buyer.user_cancel_order(self.order_id)
        assert code == 200  

    def test_user_cancel_non_exist_order_id(self):
        # 使用无效的 order_id 测试
        invalid_order_id = "invalid_order_id"
        code = self.buyer.user_cancel_order(invalid_order_id)
        assert code != 200

    def test_user_cancel_order_authorization_error(self):
        # 有效的 order_id和user_id 不匹配测试
        another_buyer_id = "another_buyer_id_{}".format(str(uuid.uuid1()))
        another_buyer = register_new_buyer(another_buyer_id, self.password)
        code = another_buyer.user_cancel_order(self.order_id)
        assert code != 200
    
    def test_user_cancel_wrong_order_status(self):
        code = self.buyer.add_funds(1000000000)
        code = self.buyer.payment(self.order_id)
        code = self.seller.send_books(self.store_id,self.order_id)
        code = self.buyer.receive_books(self.buyer_id, self.password, self.order_id)
        code = self.buyer.user_cancel_order(self.order_id)
        assert code != 200
    

    def test_auto_cancel_order_ok(self):
        # 创建订单时间距现在大于1min，自动取消订单成功测试
        print("wait one minute to complete the test...")
        time.sleep(65)  # 暂停执行65秒
        code = self.buyer.auto_cancel_order(self.order_id)
        assert code == 200
    
        
    def test_auto_cancel_order_timelimit(self):
        # 创建新的商店和书籍库存，确保库存充足
        store_id = "test_store_id_{}".format(str(uuid.uuid1()))
        seller_id = "test_seller_id_{}".format(str(uuid.uuid1()))
        buyer_id = "test_buyer_id_{}".format(str(uuid.uuid1()))
        
        # 为新商店生成书籍库存，确保库存充足
        gen_book = GenBook(seller_id, store_id)
        ok, buy_book_id_list = gen_book.gen(non_exist_book_id=False, low_stock_level=False)  # 确保库存充足
        assert ok
        # 创建一个新买家
        buyer = register_new_buyer(buyer_id, self.password)
        # 创建一个新订单
        code, new_order_id = buyer.new_order(store_id, buy_book_id_list)
        assert code == 200, f"Failed to create new order, got code {code}"
        # 现在尝试自动取消该订单（创建时间应小于1分钟，不能自动取消）
        code = buyer.auto_cancel_order(new_order_id)
        assert code == 403, f"Expected 403 for orders created less than 1 minute ago, but got {code}"


    
    def test_auto_cancel_non_exist_order_id(self):
        # 使用无效的 order_id 测试
        invalid_order_id = "invalid_order_id"
        code = self.buyer.auto_cancel_order(invalid_order_id)
        assert code != 200

    def test_auto_cancel_order_authorization_error(self):
        # 有效的 order_id和user_id 不匹配测试
        another_buyer_id = "another_buyer_id_{}".format(str(uuid.uuid1()))
        another_buyer = register_new_buyer(another_buyer_id, self.password)
        code = another_buyer.auto_cancel_order(self.order_id)
        assert code != 200
    
    def test_auto_cancel_wrong_order_status(self):
        code = self.buyer.add_funds(1000000000)
        code = self.buyer.payment(self.order_id)
        code = self.buyer.auto_cancel_order(self.order_id)
        assert code != 200
    
    '''
    def test_get_order(self):
        # 测试查询存在的历史订单
        code, result = self.buyer.get_orders()
        if code == 200:
            assert isinstance(result, list), "Expected result to be a list of orders"
            if result:
                for order in result:
                    assert "order_id" in order, "Expected 'order_id' in each order"
        else:
            pytest.fail(f"Unexpected status code {code} for get_orders")
    '''
    

