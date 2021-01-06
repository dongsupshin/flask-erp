# Flask-ERP
### ERP System made on Flask, web-framework for Python.

The aim is to make a Enterprise Resource Planning System using Python based web-framework
Flask.

> ERP or Enterprise Resource Planning System is business process management software that allows an organization to use a system of integrated applications to manage the business and automate many back office functions related to technology, services and human resources.

## Features
1. Login/Signup:
	* Add new user
	* Login as Administrator/User

2. User Credentials:
	* Change username(if available)
	* Change password
	* Administrator can add another Administrator

3. User profile:
	* Details of the User
	* Can be edited

4. Online Fee Payment:
	* Previous payments
	* Show dues
	* Pay fee
	* Download fee details in CSV format

5. Announcements:
	* System-wide announcements by Administrator
	* List announcements in the selected time period

6. Requests:
	* User requests for supplies
	* Supplies visible to the Administrator
	* Download requests in CSV format
	
## Python Packages Required
* pip install flask-mysql
* pip install cryptography
* pip install mysqlclient
* pip install sqlalchemy_utils
* pip install flask_bootstrap
* pip install lib
* pip install pillow
* pip install simplejson