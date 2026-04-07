from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Angular will connect to ws://localhost:8000/ws/alerts/
    re_path(r'ws/alerts/$', consumers.AlertConsumer.as_asgi()),
]
