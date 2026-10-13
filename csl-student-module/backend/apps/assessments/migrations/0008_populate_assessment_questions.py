from django.db import migrations


def link_questions_to_default_assessment(apps, schema_editor):
    Assessment = apps.get_model('assessments', 'Assessment')
    QuestionBank = apps.get_model('assessments', 'QuestionBank')

    # Update questionbank assessment_type
    QuestionBank.objects.filter(assessment_type="").update(assessment_type="INITIAL_DIAGNOSTIC")

    assessment = Assessment.objects.filter(code="CSL-INITIAL-01").first()
    if assessment:
        all_questions = QuestionBank.objects.all()
        if all_questions.exists():
            assessment.questions.add(*all_questions)


def reverse_link(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0007_assessment_assessment_type_and_more'),
    ]

    operations = [
        migrations.RunPython(link_questions_to_default_assessment, reverse_link),
    ]
