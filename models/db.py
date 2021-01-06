import os
import pymongo
import random
import threading

class PrefixData:
	"""Class to handle prefix data"""
	data_key = "prefixes"
	def __init__(self, db):
		self.db = db[self.data_key]

	def get_prefix(self, client, message):

		prefix_db = self.db
		prefix_entry = prefix_db.find_one(
			{
				"_id": f"{message.guild.id}"
			}
		)

		if not prefix_entry:
			prefix_entry = prefix_db.find_one({"_id": "default"})
		return prefix_entry["prefix"]

	def set_prefix(self, guild_id, prefix):

		prefix_db = self.db
		prefix_entry = prefix_db.find_one({"_id": f"{guild_id}"})
		if not prefix_entry:

			prefix_db.insert_one(
				{
					"_id": f"{guild_id}",
					"prefix": f"{prefix}"
				}
			)
			return

		prefix_db.update_one(
			{
				"_id": f"{guild_id}"
			},
			{
				'$set': {
					"prefix": f"{prefix}"
				}
			}
		)
		return

class UserData:
	"""Class that handles user data"""
	data_key = "users"
	def __init__(self, db, parent_db):
		self.db = db[self.data_key]
		self.parent = parent_db
		
	def create_user(self, user_id, guild_id):
		user = {
			"_id": f"{guild_id}-{user_id}",
			"money": 0,
			"bank": {
				"money": 0,
				"interest": 0.01,
				"last_seen": 0
			},
			"rewards": {
				"daily": 0,
				"hourly": 0
			},
			"prestige": 0
		}
		try:
			_ = self.db.insert_one(user)
			self.parent.update_users()
			return 1
		except Exception as e:
			print(e)
			return None

	def fetch_user(self, user_id, guild_id):
		return self.db.find_one({"_id": f"{guild_id}-{user_id}"})

	def update_user_set_fields(self, _filter, fields):

		fields_to_set = {}
		for field, value in fields:
			fields_to_set[field] = value

		result = self.db.update_one(
			_filter,
			{"$set": fields_to_set}
		)

		return bool(result.matched_count) and bool(result.modified_count)

	def fetch_user_of(self, guild_id):
		return list(self.db.find({"_id": {"$regex": f"^{guild_id}-"}}))

class ItemsData:
	"""Class handling item data"""
	data_key = "items"
	def __init__(self, db, parent_db):
		self.db = db[self.data_key]
		self.parent = parent_db

	def fetch_items_of(self, guild_id):
		return list(self.db.find({"server_id": f"{guild_id}"}))

	def fetch_user_items(self, user_id):
		return list(self.db.find({f"owners.{user_id}": {"$exists": True}}))

	def fetch_item_named(self, item_name, guild_id):
		return self.db.find_one({"server_id": f"{guild_id}", "name": item_name})

	def set_items_of(self, guild_id, user_id, item_name, new_item_count, new_supply_count):

		fields = {f"owners.{user_id}": new_item_count}
		if new_supply_count: fields["supply"] = new_supply_count

		result = self.db.update_one(
			{"name": item_name, "server_id": f"{guild_id}"},
			{"$set": fields}
		)
		success = (bool(result.matched_count) and bool(result.modified_count))

		return {
			"success": success,
			"item": item_name,
			"new_count": new_item_count
		}

	def update_items_price(self, guild_id):
		results = list(self.db.find(
			{"server_id": f"{guild_id}"}
		))
		for result in results:
			threading.Thread(target=ItemsData.update_item_price_of, kwargs={"result": result, "db": self.db, "guild_id": guild_id}).start()

	@staticmethod
	def update_item_price_of(result, db, guild_id):
			min_multipler, max_multiplier = result['multipliers']
			multiplier = random.randint(int(min_multipler), int(max_multiplier))
			new_cost = round(result['avg_price'] * (multiplier/100))
			db.update_one(
				{"name": result["name"], "server_id": f"{guild_id}"},
				{"$set": {f"cost": new_cost}}
			)
			print(f"Updated `{result['name']}` cost from {result['cost']} to {new_cost}")


	def remove_item_from_owner(self, guild_id, user_id, item_name, new_supply_count):

		update_query = {"$unset": {f"owners.{user_id}": 0}}
		if new_supply_count: update_query["$set"] = {"supply": new_supply_count}

		result = self.db.update_one(
			{"name": item_name, "server_id": f"{guild_id}"},
			update_query
		)
		success = (bool(result.matched_count) and bool(result.modified_count))
		return {
			"success": success,
		}

class Database:
	"""Class to handle the whole database"""
	def __init__(self, password, dbname, username, clustername):
		self.password = password
		self.dbname = dbname
		self.username = username
		self.clustername = clustername
		self.cluster = pymongo.MongoClient(f"mongodb+srv://{self.username}:{self.password}@{self.clustername}.jhxcv.mongodb.net/{self.dbname}?retryWrites=true&w=majority")
		self.database = self.cluster[self.dbname]

		self.prefix_db = PrefixData(self.database)
		self.user_db = UserData(self.database, self)
		self.items_db = ItemsData(self.database, self)

		#init with all users
		self.users = []
		self.update_users()

	def update_users(self):
		self.users = list(map(lambda result: result["_id"], self.user_db.db.find({})))

	def db_ping(self):
		return self.database.list_collection_names()

if __name__ != "db":
	password = os.environ['MONGODB_PASSWORD']
	dbname = os.environ['MONGODB_DBNAME']
	username = os.environ["MONGODB_USER"]
	clustername = os.environ["MONGODB_CLUSTER"]

	db = Database(password, dbname, username, clustername)
