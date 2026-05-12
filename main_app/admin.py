from django.contrib import admin

from .models import Item, Location, LocationLog, Tag

admin.site.register(Item)
admin.site.register(Location)
admin.site.register(LocationLog)
admin.site.register(Tag)
