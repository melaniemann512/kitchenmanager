from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("recipes/add/", views.recipe_create, name="recipe_create"),
    path("recipes/generate/", views.recipe_generate, name="recipe_generate"),
    path("recipes/<slug:slug>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<slug:slug>/edit/", views.recipe_edit, name="recipe_edit"),
    path("recipes/<slug:slug>/delete/", views.recipe_delete, name="recipe_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/<slug:slug>/", views.category_detail, name="category_detail"),
    path("timer/", views.timer, name="timer"),
    path("converter/", views.converter, name="converter"),
    path("pantry/", views.pantry_list, name="pantry_list"),
    path("pantry/add/", views.pantry_add, name="pantry_add"),
    path("pantry/<int:pk>/edit/", views.pantry_edit, name="pantry_edit"),
    path("pantry/<int:pk>/used/", views.pantry_mark_used, name="pantry_mark_used"),
    path("pantry/<int:pk>/reduce/", views.pantry_reduce_quantity, name="pantry_reduce_quantity"),
    path("pantry/<int:pk>/delete/", views.pantry_delete, name="pantry_delete"),
    path("shopping/", views.shopping_list, name="shopping_list"),
    path("shopping/add/", views.shopping_add, name="shopping_add"),
    path("shopping/<int:pk>/edit/", views.shopping_edit, name="shopping_edit"),
    path("shopping/<int:pk>/toggle/", views.shopping_toggle, name="shopping_toggle"),
    path("shopping/<int:pk>/delete/", views.shopping_delete, name="shopping_delete"),
    path("shopping/clear/", views.shopping_clear, name="shopping_clear"),
    path("about/", views.about, name="about"),
]
