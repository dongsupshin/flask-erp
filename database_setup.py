from sqlalchemy import create_engine, Column, ForeignKey, Integer, String, Date, Sequence, DateTime, \
    Enum, Float, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import select, func
from common import uuid_url64

Base = declarative_base()

class Account(Base):
    __tablename__ = 'account'

    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key = True)
    default_official_name = Column(String(length = 256), nullable = False)
    preferred_name = Column(String(length = 256))
    iso_country_code = Column(String(3), nullable=False, default="KOR")
    address_point_wgs84_x = Column(Float, nullable = False)
    address_point_wgs84_y = Column(Float, nullable = False)
    address_english = Column(String(length = 256), nullable = True)
    address_local_language = Column(String(length = 256), nullable = True)

class User(Base):
    __tablename__ = 'user'

    username = Column(String(256), primary_key=True)
    password = Column(String(256), nullable=False)
    type = Column(Enum('user', 'admin'), nullable=False)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class Profile(Base):
    __tablename__ = 'profile'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    user = relationship(User)
    username = Column(String(256), ForeignKey('user.username'))
    name = Column(String(256), nullable=False)
    dob = Column(Date)
    sex = Column(Enum('Male','Female'), nullable=False)
    email = Column(String(256))
    address = Column(String(256))
    number = Column(String(256))
    iso_country_code = Column(String(3), nullable=False, default="KOR")
    address_area_code = Column(String(256), nullable=True)
    address_wgs84_x = Column(String(256), nullable=True)
    address_wgs84_y = Column(String(256), nullable=True)

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
    product_name = Column(String(256))

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductStockMaster(Base):
    __tablename__ = 'product_stock_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))
    product_name = Column(String(256))
    stock = Column(Integer, nullable=False)

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
    item_name = Column(String(256), nullable=False)
    stock = Column(Integer, nullable=False, default=0)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())


class RecipeMaster(Base):
    __tablename__ = 'recipe_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    name = Column(String(256), nullable=False, unique=True)
    detail = Column(String(1024), nullable=True)
    # target_product
    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))
    # required_items_to_create_product
    item_list_in_json = Column(String(1024), nullable=True) # ['item1_id':3]

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ProductStatusMaster(Base):
    __tablename__ = 'product_status_master'
    
    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    product = relationship(ProductMaster)
    product_id = Column(String(256), ForeignKey('product_master.id'))
    product_name = Column(String(256))
    recipe = relationship(RecipeMaster)
    recipe_id = Column(Integer, ForeignKey('recipe_master.id'))
    status = Column(Enum('OnGoing','Finished'), nullable=False, default='OnGoing')
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    target_quantity = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit = Column(Enum('kg','lb'), nullable=False, default='kg')
    user = relationship(User)
    person_in_charge = Column(String(256), ForeignKey('user.username'))
    facility = relationship(FacilityMaster)
    facility_id = Column(String(256), ForeignKey('facility_master.id'))

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

class ActiveLoginSession(Base):
    __tablename__ = 'active_login_session'

    id = Column(Integer, Sequence(__tablename__ + '_seq'), primary_key=True)
    user = relationship(User)
    username = Column(String(256), ForeignKey('user.username'), nullable=True)
    token = Column(String(256), nullable=False, unique=True)

    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())

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
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())
    
class Board(Base):
    __tablename__ = 'board'

    id = Column(String(256), primary_key=True)
    creator = relationship(User)
    creatorname = Column(String(256), ForeignKey('user.username'), nullable=True)
    views = Column(Integer, nullable=False)
    title = Column(String(256), nullable=True, default='')
    content = Column(String(1024), nullable=True, default='')
    
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    updated_date = Column(DateTime(timezone=True), onupdate=func.now())

# engine = create_engine('mysql://dbms:justanothersecret@localhost/erp?charset=utf8', convert_unicode=False, pool_size=200, max_overflow=0)
engine = create_engine('sqlite:///erp.db', connect_args={'check_same_thread': False})

# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(engine)
print('database_setup.py success')