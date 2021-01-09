from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import engine, Base, User, Profile, FacilityMaster, ProductMaster, ProductStockMaster, ItemMaster, ItemStockMaster, RecipeMaster, LoginHistory, uuid_url64, ActiveLoginSession, Board

# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(engine)
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()

# INSERT INTO `erp`.`user` (`username`,`password`,`type`) VALUES ('Admin', 'Admin','admin')	
# INSERT INTO `erp`.`profile` (`username`,`name`,`dob`,`sex`,`email`,`address`,`number`) VALUES ('Admin','Administrator God', '2017-04-15', 'Male', 'gurek15033@iiitd.ac.in','IIIT-Delhi, Okhla Estate III', '9910004979')

# Create dummy admin
admin = User(username="Admin", password="Admin", type='admin')
session.add(admin)
session.commit()

adminprofile = Profile(user=admin, username=admin.username,name=admin.username,sex='Male')
session.add(adminprofile)
session.commit()

# Create dummy user
User1 = User(username="Robo Barista", password="1234", type='user')
session.add(User1)
session.commit()

# Create dummy profile for User1
Profile1 = Profile(user=User1, username=User1.username,name=User1.username,sex='Male')
session.add(Profile1)
session.commit()

# Create dummy facility
facility1 = FacilityMaster(id="fac_1", name="fac_1")
session.add(facility1)
session.commit()

# Create dummy product
product1 = ProductMaster(id=str(uuid_url64()), name="prod_1")
session.add(product1)
session.commit()

productstock1 = ProductStockMaster(product=product1, stock=100)
session.add(productstock1)
session.commit()

recipe1 = RecipeMaster(name="recipe_prod_1", product=product1)
session.add(recipe1)
session.commit()

# Create dummy item
item1 = ItemMaster(name="item_1")
session.add(item1)
session.commit()

itemstock1 = ItemStockMaster(item=item1, stock=100, item_name=item1.name)
session.add(itemstock1)
session.commit()

item2 = ItemMaster(name="item_2")
session.add(item2)
session.commit()

itemstock2 = ItemStockMaster(item=item2, stock=100, item_name=item2.name)
session.add(itemstock2)
session.commit()

print('populate_database.py success')



