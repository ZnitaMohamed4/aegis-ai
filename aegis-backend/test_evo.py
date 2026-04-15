import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from moderation.evolution_api import get_instance_details
from moderation.models import ParentProfile

print("Testing get_instance_details...")
details = get_instance_details('aegis_parent_0e0d4828')
print("Returned:", details)
