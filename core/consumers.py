
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):

    group_name = "notification"
    room_name = ""

    async def connect(self):
        print("CONNECTED TO THE WEB SOCKET")

        await self.accept()

    async def disconnect(self, code):
        pass

    async def send(self, notification, event):
        return


    

class DashboardConsumer(AsyncWebsocketConsumer):

    group_name = ''
    room_name = ''

    async def connect(self):

        await self.accept()

    async def disconnect(self, code):
        pass 


    async def send(self, data, event):
        pass