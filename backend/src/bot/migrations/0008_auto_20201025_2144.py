# Generated by Django 3.1.2 on 2020-10-25 21:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0007_submissionevent_payload'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='submission',
            name='unq_type_assignment_task',
        ),
        migrations.AlterField(
            model_name='botuser',
            name='github_login',
            field=models.TextField(db_index=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='botuser',
            name='telegram_chat_id',
            field=models.IntegerField(db_index=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='botuser',
            name='telegram_login',
            field=models.TextField(null=True, unique=True),
        ),
        migrations.AddConstraint(
            model_name='submission',
            constraint=models.UniqueConstraint(fields=('author', 'assignment_type', 'assignment_id', 'task_id'), name='unq_type_assignment_task'),
        ),
    ]
