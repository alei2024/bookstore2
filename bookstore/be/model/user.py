import jwt 
import time
import logging
from be.model import error
from be.model import db_conn
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pymongo.errors import PyMongoError
from be.model.encrypt import encrypt
from sqlalchemy.sql import text


# encode a json string like:
#   {
#       "user_id": [user name],
#       "terminal": [terminal code],
#       "timestamp": [ts]} to a JWT
#   }


def jwt_encode(user_id: str, terminal: str) -> str:
    encoded = jwt.encode(
        {"user_id": user_id, "terminal": terminal, "timestamp": time.time()},
        key=user_id,
        algorithm="HS256",
    )
    return encoded


# decode a JWT to a json string like:
#   {
#       "user_id": [user name],
#       "terminal": [terminal code],
#       "timestamp": [ts]} to a JWT
#   }
def jwt_decode(encoded_token, user_id: str) -> str:
    decoded = jwt.decode(encoded_token, key=user_id, algorithms="HS256")
    return decoded



class User(db_conn.DBConn):
    token_lifetime: int = 3600  # 3600 second

    def __init__(self):
        db_conn.DBConn.__init__(self)

    def __check_token(self, user_id, db_token, token) -> bool:# 判断登录信息是否失效
        try:
            if db_token != token:
                return False
            jwt_text = jwt_decode(encoded_token=token, user_id=user_id)
            ts = jwt_text["timestamp"]
            if ts is not None:
                now = time.time()
                if self.token_lifetime > now - ts >= 0:
                    return True
        
        except jwt.exceptions.InvalidSignatureError as e:
            logging.error(str(e))
            return False

    def register(self, user_id: str, password: str):
        try:
            terminal = "terminal_{}".format(str(time.time()))
            token = jwt_encode(user_id, terminal)
            password = encrypt(password)

            with self.conn.begin() as transaction:
                self.conn.execute(
                    text("INSERT into users(user_id, password, balance, token, terminal) "
                        "VALUES (:uid, :pw, 0, :tok, :ter);"),
                    {"uid": user_id, "pw": password, "tok": token, "ter": terminal}
                )
        except IntegrityError:
            return error.error_exist_user_id(user_id)
        return 200, "ok"


    def check_token(self, user_id: str, token: str) -> (int, str):
        cursor = self.conn.execute(text("SELECT token from users where user_id= :uid"), {"uid":user_id})
        row = cursor.fetchone()
        if row is None:
            return error.error_authorization_fail()
        db_token = row[0]
        if not self.__check_token(user_id, db_token, token):
            return error.error_authorization_fail()
        return 200, "ok"

    def check_password(self, user_id: str, password: str) -> (int, str):#检查密码
        cursor = self.conn.execute(text("SELECT password from users where user_id= :uid"), {"uid":user_id})
        row = cursor.fetchone()
        if row is None:
            return error.error_authorization_fail()
        ##############
        if encrypt(password) != row[0]:
        #if password != row[0]:
            return error.error_authorization_fail()

        return 200, "ok"
    
    def login(self, user_id: str, password: str, terminal: str) -> (int, str, str):
        token = ""
        try:
            # 显式开始事务
            with self.conn.begin() as transaction:  
                # 登录时先检查密码
                code, message = self.check_password(user_id, password)
                if code != 200:
                    return code, message, ""

                # 更新 token 和 terminal
                token = jwt_encode(user_id, terminal)
                cursor = self.conn.execute(text(
                    "UPDATE users SET token = :tok, terminal = :ter WHERE user_id = :uid"),
                    {'tok': token, 'ter': terminal, 'uid': user_id})
                
                # 检查更新操作是否成功
                if cursor.rowcount == 0:
                    return error.error_authorization_fail() + ("", )
                # 注意：事务会在退出 with 块时自动提交
        except SQLAlchemyError as e:
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            return 530, "{}".format(str(e)), ""
        return 200, "ok", token


    def logout(self, user_id: str, token: str) -> bool:
        try:
            # 显式开始事务
            with self.conn.begin() as transaction:  
                # 登出时检查 token
                code, message = self.check_token(user_id, token)
                if code != 200:
                    return code, message

                # 设置新的 terminal 和 dummy token
                terminal = "terminal_{}".format(str(time.time()))
                dummy_token = jwt_encode(user_id, terminal)
                
                # 更新用户的 token 和 terminal
                cursor = self.conn.execute(text(
                    "UPDATE users SET token = :tok, terminal = :ter WHERE user_id= :uid"),
                    {'tok': dummy_token, 'ter': terminal, 'uid': user_id})
                
                if cursor.rowcount == 0:
                    return error.error_authorization_fail()
                # 注意：事务会在退出 with 块时自动提交
        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"


    def unregister(self, user_id: str, password: str) -> (int, str):
        try:
            # 显式开始事务
            with self.conn.begin() as transaction:  
                # 注销前检查密码
                code, message = self.check_password(user_id, password)
                if code != 200:
                    return code, message

                # 删除用户
                cursor = self.conn.execute(text("DELETE from users where user_id= :uid"), {'uid': user_id})
                if cursor.rowcount == 1:
                    # 注意：事务会在退出 with 块时自动提交
                    pass  
                else:
                    return error.error_authorization_fail()
        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"


    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        try:
            # 显式开始事务
            with self.conn.begin() as transaction:  
                # 检查旧密码
                code, message = self.check_password(user_id, old_password)
                if code != 200:
                    return code, message

                # 生成新的 terminal 和 token
                terminal = "terminal_{}".format(str(time.time()))
                token = jwt_encode(user_id, terminal)

                # 加密新的密码
                new_password = encrypt(new_password)
                
                # 更新密码、token 和 terminal
                cursor = self.conn.execute(text(
                    "UPDATE users set password = :pw, token = :tok, terminal = :ter where user_id = :uid"),
                    {'pw': new_password, 'tok': token, 'ter': terminal, 'uid': user_id})
                
                if cursor.rowcount == 0:
                    return error.error_authorization_fail()
                # 注意：事务会在退出 with 块时自动提交
        except SQLAlchemyError as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"


'''
import jwt
import time
import logging
import sqlite3 as sqlite
from be.model import error
from be.model import db_conn

# encode a json string like:
#   {
#       "user_id": [user name],
#       "terminal": [terminal code],
#       "timestamp": [ts]} to a JWT
#   }


def jwt_encode(user_id: str, terminal: str) -> str:
    encoded = jwt.encode(
        {"user_id": user_id, "terminal": terminal, "timestamp": time.time()},
        key=user_id,
        algorithm="HS256",
    )
    return encoded


# decode a JWT to a json string like:
#   {
#       "user_id": [user name],
#       "terminal": [terminal code],
#       "timestamp": [ts]} to a JWT
#   }
def jwt_decode(encoded_token, user_id: str) -> str:
    decoded = jwt.decode(encoded_token, key=user_id, algorithms="HS256")
    return decoded


class User(db_conn.DBConn):
    token_lifetime: int = 3600  # 3600 second

    def __init__(self):
        db_conn.DBConn.__init__(self)

    def __check_token(self, user_id, db_token, token) -> bool:
        try:
            if db_token != token:
                return False
            jwt_text = jwt_decode(encoded_token=token, user_id=user_id)
            ts = jwt_text["timestamp"]
            if ts is not None:
                now = time.time()
                if self.token_lifetime > now - ts >= 0:
                    return True
        except jwt.exceptions.InvalidSignatureError as e:
            logging.error(str(e))
            return False

    def register(self, user_id: str, password: str):
        try:
            terminal = "terminal_{}".format(str(time.time()))
            token = jwt_encode(user_id, terminal)
            self.conn.execute(
                "INSERT into user(user_id, password, balance, token, terminal) "
                "VALUES (?, ?, ?, ?, ?);",
                (user_id, password, 0, token, terminal),
            )
            self.conn.commit()
        except sqlite.Error:
            return error.error_exist_user_id(user_id)
        return 200, "ok"

    def check_token(self, user_id: str, token: str) -> (int, str):
        cursor = self.conn.execute("SELECT token from user where user_id=?", (user_id,))
        row = cursor.fetchone()
        if row is None:
            return error.error_authorization_fail()
        db_token = row[0]
        if not self.__check_token(user_id, db_token, token):
            return error.error_authorization_fail()
        return 200, "ok"

    def check_password(self, user_id: str, password: str) -> (int, str):
        cursor = self.conn.execute(
            "SELECT password from user where user_id=?", (user_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return error.error_authorization_fail()

        if password != row[0]:
            return error.error_authorization_fail()

        return 200, "ok"

    def login(self, user_id: str, password: str, terminal: str) -> (int, str, str):
        token = ""
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message, ""

            token = jwt_encode(user_id, terminal)
            cursor = self.conn.execute(
                "UPDATE user set token= ? , terminal = ? where user_id = ?",
                (token, terminal, user_id),
            )
            if cursor.rowcount == 0:
                return error.error_authorization_fail() + ("",)
            self.conn.commit()
        except sqlite.Error as e:
            return 528, "{}".format(str(e)), ""
        except BaseException as e:
            return 530, "{}".format(str(e)), ""
        return 200, "ok", token

    def logout(self, user_id: str, token: str) -> bool:
        try:
            code, message = self.check_token(user_id, token)
            if code != 200:
                return code, message

            terminal = "terminal_{}".format(str(time.time()))
            dummy_token = jwt_encode(user_id, terminal)

            cursor = self.conn.execute(
                "UPDATE user SET token = ?, terminal = ? WHERE user_id=?",
                (dummy_token, terminal, user_id),
            )
            if cursor.rowcount == 0:
                return error.error_authorization_fail()

            self.conn.commit()
        except sqlite.Error as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"

    def unregister(self, user_id: str, password: str) -> (int, str):
        try:
            code, message = self.check_password(user_id, password)
            if code != 200:
                return code, message

            cursor = self.conn.execute("DELETE from user where user_id=?", (user_id,))
            if cursor.rowcount == 1:
                self.conn.commit()
            else:
                return error.error_authorization_fail()
        except sqlite.Error as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"

    def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> bool:
        try:
            code, message = self.check_password(user_id, old_password)
            if code != 200:
                return code, message

            terminal = "terminal_{}".format(str(time.time()))
            token = jwt_encode(user_id, terminal)
            cursor = self.conn.execute(
                "UPDATE user set password = ?, token= ? , terminal = ? where user_id = ?",
                (new_password, token, terminal, user_id),
            )
            if cursor.rowcount == 0:
                return error.error_authorization_fail()

            self.conn.commit()
        except sqlite.Error as e:
            return 528, "{}".format(str(e))
        except BaseException as e:
            return 530, "{}".format(str(e))
        return 200, "ok"
'''