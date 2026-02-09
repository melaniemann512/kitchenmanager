# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0003_pantryitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='recipe',
            name='image',
            field=models.ImageField(blank=True, help_text='Upload a photo of the dish', upload_to='recipes/'),
        ),
    ]
