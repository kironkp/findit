from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),

    path('items/', views.item_index, name='item-index'),
    path('items/bulk/', views.bulk_item_form, name='item-bulk'),
    path('items/bulk/transcribe/', views.bulk_transcribe, name='item-bulk-transcribe'),
    path('items/bulk/parse/', views.bulk_parse, name='item-bulk-parse'),
    path('items/bulk/save/', views.bulk_save, name='item-bulk-save'),
    path('items/create/', views.ItemCreate.as_view(), name='item-create'),
    path('items/<int:pk>/', views.item_detail, name='item-detail'),
    path('items/<int:pk>/update/', views.ItemUpdate.as_view(), name='item-update'),
    path('items/<int:pk>/delete/', views.ItemDelete.as_view(), name='item-delete'),
    path('items/<int:pk>/move/', views.move_item, name='item-move'),
    path('items/<int:pk>/lend/', views.lend_item, name='item-lend'),
    path('items/<int:pk>/return/', views.return_item, name='item-return'),
    path('items/<int:pk>/move/quick/', views.quick_move_item, name='item-move-quick'),
    path('moves/<int:pk>/update/', views.LocationLogUpdate.as_view(), name='move-update'),
    path('moves/<int:pk>/delete/', views.LocationLogDelete.as_view(), name='move-delete'),
    path('items/<int:pk>/confirm/', views.confirm_item, name='item-confirm'),
    path('items/<int:pk>/archive/', views.archive_item, name='item-archive'),
    path('items/<int:pk>/tags/<int:tag_id>/add/', views.add_tag, name='item-add-tag'),
    path('items/<int:pk>/tags/<int:tag_id>/remove/', views.remove_tag, name='item-remove-tag'),

    path('locations/', views.LocationList.as_view(), name='location-index'),
    path('locations/map/', views.location_map, name='location-map'),
    path('locations/create/', views.LocationCreate.as_view(), name='location-create'),
    path('locations/<int:pk>/', views.LocationDetail.as_view(), name='location-detail'),
    path('locations/<int:pk>/panel/', views.location_panel, name='location-panel'),
    path('locations/<int:pk>/reparent/', views.location_reparent, name='location-reparent'),
    path('locations/<int:pk>/update/', views.LocationUpdate.as_view(), name='location-update'),
    path('locations/<int:pk>/delete/', views.LocationDelete.as_view(), name='location-delete'),

    path('tags/', views.TagList.as_view(), name='tag-index'),
    path('tags/create/', views.TagCreate.as_view(), name='tag-create'),
    path('tags/<int:pk>/', views.TagDetail.as_view(), name='tag-detail'),
    path('tags/<int:pk>/update/', views.TagUpdate.as_view(), name='tag-update'),
    path('tags/<int:pk>/delete/', views.TagDelete.as_view(), name='tag-delete'),
]
