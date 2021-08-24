# Generated by Django 3.1.2 on 2020-11-15 19:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0012_auto_20201115_1558'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='seq',
            field=models.IntegerField(default=-1),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='assignment',
            constraint=models.UniqueConstraint(fields=('type', 'group', 'seq'), name='unq_type_group_seq'),
        ),
    ]
