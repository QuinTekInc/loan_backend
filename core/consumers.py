
from channels.generic.websocket import WebsocketConsumer 

class NotificationConsumer(WebsocketConsumer):

    group_name = "notification"
    room_name = ""

    def connect(self):
        print("CONNECTED TO THE WEB SOCKET")
        self.accept()

    def disconnect(self):
        pass