from django.db import migrations


def assign_to_first_user(apps, schema_editor):
    User = apps.get_model("auth", "User")
    try:
        first_user = User.objects.get(pk=1)
    except User.DoesNotExist:
        raise Exception(
            "No user with pk=1 found. Create a superuser first: "
            "python manage.py createsuperuser"
        )

    Category = apps.get_model("recipes", "Category")
    Recipe = apps.get_model("recipes", "Recipe")
    PantryItem = apps.get_model("recipes", "PantryItem")
    ShoppingItem = apps.get_model("recipes", "ShoppingItem")

    Category.objects.filter(user__isnull=True).update(user=first_user)
    Recipe.objects.filter(user__isnull=True).update(user=first_user)
    PantryItem.objects.filter(user__isnull=True).update(user=first_user)
    ShoppingItem.objects.filter(user__isnull=True).update(user=first_user)


def undo_assignment(apps, schema_editor):
    Category = apps.get_model("recipes", "Category")
    Recipe = apps.get_model("recipes", "Recipe")
    PantryItem = apps.get_model("recipes", "PantryItem")
    ShoppingItem = apps.get_model("recipes", "ShoppingItem")

    Category.objects.all().update(user=None)
    Recipe.objects.all().update(user=None)
    PantryItem.objects.all().update(user=None)
    ShoppingItem.objects.all().update(user=None)


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0008_add_user_fk_nullable"),
    ]

    operations = [
        migrations.RunPython(assign_to_first_user, undo_assignment),
    ]
