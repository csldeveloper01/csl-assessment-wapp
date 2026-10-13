from rest_framework import serializers
from .models import Activity, Task, Assessment, Project, Submission


class StudentActivityListSerializer(serializers.ModelSerializer):
    course = serializers.CharField(source="course.name", read_only=True)
    batch = serializers.SerializerMethodField()
    type = serializers.CharField(source="activity_type", read_only=True)
    due_date = serializers.DateTimeField(source="deadline", read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "type",
            "description",
            "course",
            "batch",
            "due_date",
            "max_marks",
            "status",
        ]

    def get_batch(self, obj):
        return obj.batch.name if obj.batch else None

    def get_status(self, obj):
        student_profile = self.context.get("student_profile")
        if not student_profile:
            return "PENDING"
        # Check if the student has a submission for this activity
        submission = Submission.objects.filter(
            activity=obj,
            student=student_profile,
        ).first()

        if submission:
            if hasattr(submission, "evaluation") and submission.evaluation:
                if submission.evaluation.status == "COMPLETED":
                    return "EVALUATED"
            if submission.status == Submission.Status.SUBMITTED:
                return "SUBMITTED"
            elif submission.status == Submission.Status.WITHDRAWN:
                return "WITHDRAWN"
            elif submission.status == Submission.Status.DRAFT:
                return "DRAFT"
        return "PENDING"


class StudentActivityDetailSerializer(serializers.ModelSerializer):
    course = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    batch = serializers.SerializerMethodField()
    type = serializers.CharField(source="activity_type", read_only=True)
    due_date = serializers.DateTimeField(source="deadline", read_only=True)
    status = serializers.SerializerMethodField()
    skills_covered = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "type",
            "description",
            "course",
            "course_code",
            "batch",
            "due_date",
            "max_marks",
            "status",
            "skills_covered",
            "created_at",
        ]

    def get_batch(self, obj):
        return obj.batch.name if obj.batch else None

    def get_status(self, obj):
        student_profile = self.context.get("student_profile")
        if not student_profile:
            return "PENDING"
        submission = Submission.objects.filter(
            activity=obj,
            student=student_profile,
        ).first()
        if submission:
            if hasattr(submission, "evaluation") and submission.evaluation:
                if submission.evaluation.status == "COMPLETED":
                    return "EVALUATED"
            if submission.status == Submission.Status.SUBMITTED:
                return "SUBMITTED"
            elif submission.status == Submission.Status.WITHDRAWN:
                return "WITHDRAWN"
            elif submission.status == Submission.Status.DRAFT:
                return "DRAFT"
        return "PENDING"

    def get_skills_covered(self, obj):
        skills_dict = {}
        # 1. If TASK
        if obj.activity_type == Activity.ActivityType.TASK:
            try:
                task = obj.task
                for mapping in task.skill_mappings.select_related("skill", "sub_skill").all():
                    sk = mapping.skill
                    if sk.id not in skills_dict:
                        skills_dict[sk.id] = {
                            "id": sk.id,
                            "name": sk.name,
                            "subskills": [],
                        }
                    if mapping.sub_skill:
                        skills_dict[sk.id]["subskills"].append({
                            "id": mapping.sub_skill.id,
                            "name": mapping.sub_skill.name,
                        })
            except Exception:
                pass

        # 2. If PROJECT
        elif obj.activity_type == Activity.ActivityType.PROJECT:
            try:
                project = obj.project
                for mapping in project.skill_mappings.select_related("skill", "sub_skill").all():
                    sk = mapping.skill
                    if sk.id not in skills_dict:
                        skills_dict[sk.id] = {
                            "id": sk.id,
                            "name": sk.name,
                            "subskills": [],
                        }
                    if mapping.sub_skill:
                        skills_dict[sk.id]["subskills"].append({
                            "id": mapping.sub_skill.id,
                            "name": mapping.sub_skill.name,
                        })
            except Exception:
                pass

        # 3. If ASSESSMENT
        elif obj.activity_type == Activity.ActivityType.ASSESSMENT:
            try:
                assessment = obj.assessment
                for section in assessment.sections.all():
                    for q in section.questions.select_related("skill", "sub_skill").all():
                        sk = q.skill
                        if sk.id not in skills_dict:
                            skills_dict[sk.id] = {
                                "id": sk.id,
                                "name": sk.name,
                                "subskills": [],
                            }
                        if q.sub_skill and not any(sub["id"] == q.sub_skill.id for sub in skills_dict[sk.id]["subskills"]):
                            skills_dict[sk.id]["subskills"].append({
                                "id": q.sub_skill.id,
                                "name": q.sub_skill.name,
                            })
            except Exception:
                pass

        return list(skills_dict.values())


# ==============================================================================
# Staff Activity Management Serializers
# ==============================================================================

class SkillMappingInputSerializer(serializers.Serializer):
    skill_id = serializers.IntegerField()
    sub_skill_id = serializers.IntegerField(required=False, allow_null=True)
    subskill_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class QuestionInputSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=False, allow_blank=True)
    question_text = serializers.CharField(required=False, allow_blank=True)
    skill_id = serializers.IntegerField()
    sub_skill_id = serializers.IntegerField(required=False, allow_null=True)
    max_marks = serializers.IntegerField(min_value=1, required=False)
    marks = serializers.IntegerField(min_value=1, required=False)
    order = serializers.IntegerField(default=1, required=False)

    def validate(self, data):
        prompt = data.get("prompt") or data.get("question_text")
        if not prompt:
            raise serializers.ValidationError({"prompt": "Question text or prompt is required."})
        data["prompt"] = prompt

        max_marks = data.get("max_marks") or data.get("marks")
        if not max_marks:
            raise serializers.ValidationError({"max_marks": "Maximum marks for question is required."})
        data["max_marks"] = max_marks

        return data


class SectionInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    order = serializers.IntegerField(default=1, required=False)
    questions = QuestionInputSerializer(many=True, required=False, default=list)


class StaffActivityCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    activity_type = serializers.ChoiceField(choices=Activity.ActivityType.choices, required=False)
    type = serializers.ChoiceField(choices=Activity.ActivityType.choices, required=False)
    course_id = serializers.IntegerField()
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    max_marks = serializers.IntegerField(min_value=1)
    deadline = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=Activity.Status.choices,
        default=Activity.Status.DRAFT,
        required=False,
    )
    # For Task / Project
    skills = SkillMappingInputSerializer(many=True, required=False, default=list)
    # For Assessment
    sections = SectionInputSerializer(many=True, required=False, default=list)

    def validate(self, data):
        activity_type = data.get("activity_type") or data.get("type")
        if not activity_type:
            raise serializers.ValidationError({"activity_type": "This field is required."})
        data["activity_type"] = activity_type
        max_marks = data["max_marks"]

        # 1. Validate max marks limits per type
        if activity_type == Activity.ActivityType.ASSESSMENT and max_marks > 200:
            raise serializers.ValidationError({"max_marks": "Assessment cannot exceed 200 maximum marks."})
        elif activity_type in (Activity.ActivityType.TASK, Activity.ActivityType.PROJECT) and max_marks > 100:
            raise serializers.ValidationError({"max_marks": f"{activity_type.capitalize()} cannot exceed 100 maximum marks."})

        # 2. Validate course existence
        from apps.courses.models import Course, Batch
        try:
            course = Course.objects.get(id=data["course_id"])
            data["course_obj"] = course
        except Course.DoesNotExist:
            raise serializers.ValidationError({"course_id": "Specified course does not exist."})

        # 3. Validate batch if provided
        batch_id = data.get("batch_id")
        if batch_id:
            try:
                batch = Batch.objects.get(id=batch_id, course=course)
                data["batch_obj"] = batch
            except Batch.DoesNotExist:
                raise serializers.ValidationError({"batch_id": "Specified batch does not exist for this course."})
        else:
            data["batch_obj"] = None

        # 4. If status is ACTIVE, deadline is required
        if data.get("status") == Activity.Status.ACTIVE and not data.get("deadline"):
            raise serializers.ValidationError({"deadline": "A valid deadline is required for published/active activities."})

        # 5. Validate skills/subskills for Task and Project
        from apps.skills.models import Skill, SubSkill
        if activity_type in (Activity.ActivityType.TASK, Activity.ActivityType.PROJECT):
            for idx, item in enumerate(data.get("skills", [])):
                try:
                    sk = Skill.objects.get(id=item["skill_id"])
                except Skill.DoesNotExist:
                    raise serializers.ValidationError({f"skills[{idx}].skill_id": "Skill does not exist."})
                
                sub_id = item.get("sub_skill_id")
                if sub_id:
                    try:
                        sub = SubSkill.objects.get(id=sub_id, skill=sk)
                    except SubSkill.DoesNotExist:
                        raise serializers.ValidationError(
                            {f"skills[{idx}].sub_skill_id": f"SubSkill {sub_id} does not belong to Skill {sk.name}."}
                        )

        # 6. Validate assessment sections and questions
        if activity_type == Activity.ActivityType.ASSESSMENT:
            for s_idx, sec in enumerate(data.get("sections", [])):
                for q_idx, q in enumerate(sec.get("questions", [])):
                    try:
                        sk = Skill.objects.get(id=q["skill_id"])
                    except Skill.DoesNotExist:
                        raise serializers.ValidationError(
                            {f"sections[{s_idx}].questions[{q_idx}].skill_id": "Skill does not exist."}
                        )
                    sub_id = q.get("sub_skill_id")
                    if sub_id:
                        try:
                            sub = SubSkill.objects.get(id=sub_id, skill=sk)
                        except SubSkill.DoesNotExist:
                            raise serializers.ValidationError(
                                {f"sections[{s_idx}].questions[{q_idx}].sub_skill_id": f"SubSkill {sub_id} does not belong to Skill {sk.name}."}
                            )

        return data


class StaffActivityListSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.code", read_only=True)
    batch_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "description",
            "activity_type",
            "course",
            "course_name",
            "course_code",
            "batch",
            "batch_name",
            "max_marks",
            "deadline",
            "status",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_batch_name(self, obj):
        return obj.batch.name if obj.batch else None

    def get_created_by_name(self, obj):
        return obj.created_by.first_name or obj.created_by.email

