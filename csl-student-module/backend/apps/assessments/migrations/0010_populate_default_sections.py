from django.db import migrations


def populate_default_sections(apps, schema_editor):
    AssessmentSection = apps.get_model('assessments', 'AssessmentSection')
    QuestionBank = apps.get_model('assessments', 'QuestionBank')
    Assessment = apps.get_model('assessments', 'Assessment')
    AssessmentSectionAllocation = apps.get_model('assessments', 'AssessmentSectionAllocation')

    apt_sec, _ = AssessmentSection.objects.get_or_create(
        code="APTITUDE",
        defaults={
            "name": "Aptitude",
            "order": 1,
            "description": "Quantitative Problem Solving, Logical Reasoning, and Verbal Ability.",
            "is_active": True,
        },
    )
    cod_sec, _ = AssessmentSection.objects.get_or_create(
        code="CODING",
        defaults={
            "name": "Coding Fundamentals",
            "order": 2,
            "description": "Core Programming Principles, Control Flow, OOP, and Data Structures.",
            "is_active": True,
        },
    )

    # Link existing QuestionBank items
    QuestionBank.objects.filter(section_type="APTITUDE", section__isnull=True).update(section=apt_sec)
    QuestionBank.objects.filter(section_type="CODING", section__isnull=True).update(section=cod_sec)

    # Link existing Assessments
    for assessment in Assessment.objects.all():
        if not assessment.section_allocations.exists():
            apt_count = assessment.aptitude_count or 25
            cod_count = assessment.coding_count or 25
            AssessmentSectionAllocation.objects.get_or_create(
                assessment=assessment,
                section=apt_sec,
                defaults={"question_count": apt_count, "marks_per_question": 1, "order": 1},
            )
            AssessmentSectionAllocation.objects.get_or_create(
                assessment=assessment,
                section=cod_sec,
                defaults={"question_count": cod_count, "marks_per_question": 1, "order": 2},
            )


def reverse_populate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0009_alter_questionbank_options_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_default_sections, reverse_populate),
    ]
