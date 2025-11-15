import motor.motor_asyncio
from config import DB_NAME, DB_URI

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            session = None,
            is_premium = False,
            premium_expiry = None,
            downloads_today = 0,
            last_download_date = None
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def set_session(self, id, session):
        await self.col.update_one({'id': int(id)}, {'$set': {'session': session}})

    async def get_session(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('session') if user else None
    
    # Premium membership methods
    async def set_premium(self, user_id, is_premium, expiry_timestamp=None):
        """Set premium status for user"""
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'is_premium': is_premium, 'premium_expiry': expiry_timestamp}}
        )
    
    async def is_premium(self, user_id):
        """Check if user is premium"""
        import time
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False
        
        if user.get('is_premium'):
            expiry = user.get('premium_expiry')
            if expiry is None or expiry > time.time():
                return True
            else:
                # Expired, remove premium
                await self.set_premium(user_id, False, None)
                return False
        return False
    
    async def get_all_premium_users(self):
        """Get all premium users"""
        import time
        cursor = self.col.find({'is_premium': True})
        premium_users = []
        async for user in cursor:
            if user.get('premium_expiry') is None or user.get('premium_expiry') > time.time():
                premium_users.append(user)
        return premium_users
    
    # Download tracking for rate limiting
    async def check_and_update_downloads(self, user_id):
        """Check and update download count for rate limiting"""
        from datetime import datetime, date
        
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False
        
        today = str(date.today())
        last_date = user.get('last_download_date')
        downloads_today = user.get('downloads_today', 0)
        
        # Reset if new day
        if last_date != today:
            downloads_today = 0
        
        # Check limits
        is_premium_user = await self.is_premium(user_id)
        limit = 1000 if is_premium_user else 10  # Premium: 1000/day, Free: 10/day
        
        if downloads_today >= limit:
            return False  # Limit exceeded
        
        # Update count
        await self.col.update_one(
            {'id': int(user_id)},
            {'$set': {'downloads_today': downloads_today + 1, 'last_download_date': today}}
        )
        return True
    
    async def get_download_count(self, user_id):
        """Get today's download count"""
        from datetime import date
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return 0
        
        today = str(date.today())
        if user.get('last_download_date') == today:
            return user.get('downloads_today', 0)
        return 0

db = Database(DB_URI, DB_NAME)
