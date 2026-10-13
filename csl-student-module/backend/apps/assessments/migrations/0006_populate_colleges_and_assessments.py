from django.db import migrations
import re


def populate_colleges_and_assessments(apps, schema_editor):
    College = apps.get_model('assessments', 'College')
    Assessment = apps.get_model('assessments', 'Assessment')
    AssessmentConfig = apps.get_model('assessments', 'AssessmentConfig')
    Candidate = apps.get_model('assessments', 'Candidate')
    AssessmentAttempt = apps.get_model('assessments', 'AssessmentAttempt')

    # 1. Backfill Colleges from existing Candidates
    college_map = {}
    code_counter = 1
    for candidate in Candidate.objects.all():
        college_name = (candidate.college or "").strip()
        if not college_name:
            college_name = "General Institution"

        if college_name not in college_map:
            # Generate a code if none exists
            clean_code = re.sub(r'[^A-Z0-9]', '', college_name.upper())[:10]
            if not clean_code or College.objects.filter(code=clean_code).exists():
                clean_code = f"COL-{code_counter:03d}"
                while College.objects.filter(code=clean_code).exists():
                    code_counter += 1
                    clean_code = f"COL-{code_counter:03d}"
            
            college, _ = College.objects.get_or_create(
                name=college_name,
                defaults={
                    "code": clean_code,
                    "location": "Campus",
                    "is_active": True,
                }
            )
            college_map[college_name] = college
            code_counter += 1

        college = college_map[college_name]
        candidate.college_ref = college
        candidate.college = college.name
        candidate.save(update_fields=['college_ref', 'college'])

    # Ensure at least one default college exists if none existed
    if not College.objects.exists():
        default_college = College.objects.create(
            name="Coimbatore Institute of Technology",
            code="CIT",
            location="Coimbatore",
            is_active=True,
        )
    else:
        default_college = College.objects.first()

    # 2. Get or create default Assessment from AssessmentConfig
    config = AssessmentConfig.objects.filter(is_active=True).first()
    
    title = config.title if config else "CSL Initial Assessment"
    description = config.description if config else "CSL 50-mark balanced diagnostic assessment."
    duration_minutes = config.duration_minutes if config else 60
    total_marks = config.total_marks if config else 50
    aptitude_count = config.aptitude_count if config else 25
    coding_count = config.coding_count if config else 25
    max_attempts = config.max_attempts if config else 1
    max_tab_switches = config.max_tab_switches_warning if config else 2
    auto_submit = config.auto_submit_on_tab_limit if config is not None else True

    assessment, created = Assessment.objects.get_or_create(
        code="CSL-INITIAL-01",
        defaults={
            "title": title,
            "description": description,
            "status": "OPEN",
            "duration_minutes": duration_minutes,
            "total_marks": total_marks,
            "aptitude_count": aptitude_count,
            "coding_count": coding_count,
            "max_attempts": max_attempts,
            "max_tab_switches_warning": max_tab_switches,
            "auto_submit_on_tab_limit": auto_submit,
        }
    )

    # Link all active colleges to this default assessment
    all_colleges = list(College.objects.filter(is_active=True))
    if all_colleges:
        assessment.eligible_colleges.set(all_colleges)

    # 3. Link all existing AssessmentAttempts to this assessment
    AssessmentAttempt.objects.filter(assessment__isnull=True).update(assessment=assessment)


def reverse_populate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0005_college_assessment_evolution'),
    ]

    operations = [
        migrations.RunPython(populate_colleges_and_assessments, reverse_populate),
    ]
