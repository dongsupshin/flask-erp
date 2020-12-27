from sqlalchemy import Column, ForeignKey, Integer, String, Date, Sequence, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import select, func
import re, uuid, base64

def uuid_url64():
    rv = base64.b64encode(uuid.uuid4().bytes).decode('utf-8')
    return re.sub(r'[\=\+\/]', lambda m: {'+': '-', '/': '_', '=': ''}[m.group(0)], rv)

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'

    username = Column(String(256), primary_key=True)
    password = Column(String(256), nullable=False)
    type = Column(mysql.ENUM('user', 'admin'), nullable=False)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class Profile(Base):
    __tablename__ = 'profile'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    user = relationship(User)
    username = Column(String(256), ForeignKey('user.username'))
    name = Column(String(256), nullable=False)
    dob = Column(Date)
    sex = Column(mysql.ENUM('Male','Female'), nullable=False)
    email = Column(String(256))
    address = Column(String(256))
    number = Column(String(256))

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class FacilityMaster(Base):
    __tablename__ = 'facility_master'
    
    id = Column(String(256), primary_key=True)
    name = Column(String(256), nullable=False)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductMaster(Base):
    __tablename__ = 'product_master'
    
    id = Column(String(256), primary_key=True)
    name = Column(String(256), nullable=False, unique=True)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductDetail(Base):
    __tablename__ = 'product_detail'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)

    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductStockMaster(Base):
    __tablename__ = 'product_stock_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)

    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))

    stock = Column(Integer, nullable=False)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductStatusMaster(Base):
    __tablename__ = 'product_status_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))

    status = Column(mysql.ENUM('Idle','OnGoing','Finished'), nullable=False, default='Idle')

    created_date = Column(DateTime(timezone=True), server_default=func.now()) # 제조일자
    target_quantity = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit = Column(mysql.ENUM('kg','lb'), nullable=False, default='kg')
    user = relationship(User)
    person_in_charge = Column(String(256), ForeignKey('user.username'))
    facility = relationship(FacilityMaster)
    facility_id = Column(String(256), ForeignKey('facility_master.id'))

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ItemMaster(Base):
    __tablename__ = 'item_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    name = Column(String(256), nullable=False, unique=True)
    user = relationship(User)
    person_in_charge = Column(String(256), ForeignKey('user.username'))
    
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ItemStockMaster(Base):
    __tablename__ = 'item_stock_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)

    item = relationship(ItemMaster)
    item_id = Column(Integer, ForeignKey('item_master.id'), unique=True)

    stock = Column(Integer, nullable=False, default=0)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())


class RecipeMaster(Base):
    __tablename__ = 'recipe_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    name = Column(String(256), nullable=False)
    detail = Column(String(1024), nullable=True)

    # target_product
    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))

    # required_items_to_create_product
    item_list_in_json = Column(String(1024), nullable=True) # ['item1_id':3]

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ActiveLoginSession(Base):
    __tablename__ = 'active_login_session'

    id = Column(Integer, primary_key=True)
    user = relationship(User)
    username = Column(String(256), ForeignKey('user.username'), nullable=True)
    token = Column(String(256), nullable=False, unique=True)
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    updated_date = Column(DateTime(timezone=True), onupdate=func.now())

class LoginHistory(Base):
    __tablename__ = 'login_history'

    id = Column(String(256), primary_key=True)
    user = relationship(User)
    username = Column(String(256), ForeignKey('user.username'), nullable=True)
    request_url = Column(String(2048), nullable=False)
    remote_address = Column(String(1024), nullable=False)
    error_log = Column(String(1024), nullable=True, default='')

    login_time = Column(DateTime(timezone=True), server_default=func.now())
    time_created = Column(DateTime(timezone=True), server_default=func.now())

engine = create_engine('mysql://dbms:justanothersecret@localhost/erp?charset=utf8', convert_unicode=False, pool_size=200, max_overflow=0)

# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(engine)
print('database_setup.py success')