# Generated by Django 5.1.3 on 2024-12-11 10:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lending',
            name='phone',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='lending',
            name='spare_phone',
            field=models.CharField(max_length=20),
        ),
    ]
