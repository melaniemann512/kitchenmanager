from django.contrib import admin

from .models import Category, PantryItem, Recipe, ShoppingItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "prep_time", "cook_time", "servings", "calories", "created_at"]
    list_filter = ["category", "created_at"]
    search_fields = ["title", "ingredients"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "description", "category", "image"]}),
        ("Recipe Details", {"fields": ["ingredients", "instructions", "prep_time", "cook_time", "servings"]}),
        ("Nutrition (per serving, AI-estimated)", {
            "fields": ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"],
        }),
    ]


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "quantity", "storage", "sell_by_date", "used"]
    list_filter = ["storage", "used", "sell_by_date"]
    search_fields = ["name"]


@admin.register(ShoppingItem)
class ShoppingItemAdmin(admin.ModelAdmin):
    list_display = ["name", "quantity", "section", "checked", "added_at"]
    list_filter = ["section", "checked"]
    search_fields = ["name"]
