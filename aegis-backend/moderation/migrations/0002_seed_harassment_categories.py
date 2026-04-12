# Data migration: Seeds the HarassmentCategory reference table.
# These are the 6 UML categories + 'safe'. Never modified at runtime.
from django.db import migrations


CATEGORIES = [
    {
        'code': 'threat',
        'label_fr': 'Menace',
        'label_ar': 'تهديد',
        'label_en': 'Threat',
        'severity_weight': 1.5,
        'description': 'Direct or indirect threats of violence, harm, or intimidation.',
    },
    {
        'code': 'sexual_harassment',
        'label_fr': 'Harcèlement sexuel',
        'label_ar': 'تحرش جنسي',
        'label_en': 'Sexual Harassment',
        'severity_weight': 1.5,
        'description': 'Unwanted sexual advances, comments, or imagery.',
    },
    {
        'code': 'identity_theft',
        'label_fr': 'Usurpation d\'identité',
        'label_ar': 'انتحال الهوية',
        'label_en': 'Identity Theft',
        'severity_weight': 1.3,
        'description': 'Impersonating another person to cause harm or confusion.',
    },
    {
        'code': 'discrimination',
        'label_fr': 'Discrimination',
        'label_ar': 'تمييز',
        'label_en': 'Discrimination',
        'severity_weight': 1.2,
        'description': 'Hateful language based on race, gender, religion, or other protected characteristics.',
    },
    {
        'code': 'verbal_harassment',
        'label_fr': 'Harcèlement verbal',
        'label_ar': 'تحرش لفظي',
        'label_en': 'Verbal Harassment',
        'severity_weight': 1.0,
        'description': 'Insults, name-calling, and hostile verbal aggression.',
    },
    {
        'code': 'repeated_messages',
        'label_fr': 'Messages répétés',
        'label_ar': 'رسائل متكررة',
        'label_en': 'Repeated Messages',
        'severity_weight': 0.8,
        'description': 'Relentless messaging, spamming, or persistent unwanted contact.',
    },
    {
        'code': 'safe',
        'label_fr': 'Sûr',
        'label_ar': 'آمن',
        'label_en': 'Safe',
        'severity_weight': 0.0,
        'description': 'Benign content — no harassment detected.',
    },
]


def seed_categories(apps, schema_editor):
    HarassmentCategory = apps.get_model('moderation', 'HarassmentCategory')
    for cat_data in CATEGORIES:
        HarassmentCategory.objects.update_or_create(
            code=cat_data['code'],
            defaults=cat_data,
        )


def unseed_categories(apps, schema_editor):
    HarassmentCategory = apps.get_model('moderation', 'HarassmentCategory')
    HarassmentCategory.objects.filter(
        code__in=[c['code'] for c in CATEGORIES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('moderation', '0001_complete_uml_models'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
