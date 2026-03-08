from django.contrib import admin

from .models import Category, IngredientSubstitution, PantryItem, Recipe, ShoppingItem


@admin.register(IngredientSubstitution)
class IngredientSubstitutionAdmin(admin.ModelAdmin):
    list_display  = ["ingredient_name", "substitute_name", "dietary_need", "user", "ai_generated", "created_at"]
    list_filter   = ["dietary_need", "ai_generated"]
    search_fields = ["ingredient_name", "substitute_name"]
    raw_id_fields = ["user"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "slug"]
    list_filter = ["user"]
    raw_id_fields = ["user"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "prep_time", "cook_time", "servings", "calories", "created_at"]
    list_filter = ["user", "category", "created_at"]
    search_fields = ["title", "ingredients"]
    raw_id_fields = ["user"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"]
    fieldsets = [
        (None, {"fields": ["user", "title", "slug", "description", "category", "image"]}),
        ("Recipe Details", {"fields": ["ingredients", "instructions", "prep_time", "cook_time", "servings"]}),
        ("Nutrition (per serving, AI-estimated)", {
            "fields": ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"],
        }),
    ]


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "quantity", "storage", "sell_by_date", "used"]
    list_filter = ["user", "storage", "used", "sell_by_date"]
    search_fields = ["name"]
    raw_id_fields = ["user"]


@admin.register(ShoppingItem)
class ShoppingItemAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "quantity", "section", "checked", "added_at"]
    list_filter = ["user", "section", "checked"]
    search_fields = ["name"]
    raw_id_fields = ["user"]
