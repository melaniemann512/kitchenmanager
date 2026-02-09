from django import forms

from .models import PantryItem, Recipe, ShoppingItem


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = [
            "title",
            "description",
            "image",
            "ingredients",
            "instructions",
            "category",
            "prep_time",
            "cook_time",
            "servings",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Recipe title"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Brief description"}),
            "ingredients": forms.Textarea(
                attrs={"rows": 8, "placeholder": "One ingredient per line"}
            ),
            "instructions": forms.Textarea(
                attrs={"rows": 10, "placeholder": "One step per line"}
            ),
            "prep_time": forms.NumberInput(attrs={"min": 0}),
            "cook_time": forms.NumberInput(attrs={"min": 0}),
            "servings": forms.NumberInput(attrs={"min": 1}),
        }


class PantryItemForm(forms.ModelForm):
    class Meta:
        model = PantryItem
        fields = ["name", "quantity", "storage", "sell_by_date", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Ground Beef"}),
            "quantity": forms.TextInput(attrs={"placeholder": "e.g., 2 lbs"}),
            "sell_by_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes"}),
        }


class ShoppingItemForm(forms.ModelForm):
    class Meta:
        model = ShoppingItem
        fields = ["name", "quantity", "section"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., Milk"}),
            "quantity": forms.TextInput(attrs={"placeholder": "e.g., 1 gallon"}),
        }
