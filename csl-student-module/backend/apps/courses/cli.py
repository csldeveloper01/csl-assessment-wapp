"""Interactive Course & Batch & Required Skills Management flow for CSL Admin CLI.

Handles:
    Course -> Batch
    Course -> Required Skills (CourseSkill) -> Skill -> SubSkill

Follows the interaction style of SkillManagementCLI:
- numbered menus
- "B. Back" navigation
- self.stdout styling
- safe delete and duplicate handling
- injectable input_fn for testing
"""
from datetime import datetime
from django.db.models import Count, ProtectedError, Q

from apps.courses.models import Batch, Course, CourseSkill
from apps.skills.models import Skill, SkillCategory, SubSkill


class CourseManagementCLI:
    """Course, Batch, and CourseSkill management menus for Admin CLI."""

    def __init__(self, command, input_fn=None):
        self.command = command
        self.input_fn = input_fn or input

    # ── output helpers ────────────────────────────────────────────────────
    def write(self, text=""):
        self.command.stdout.write(text)

    def success(self, text):
        self.command.stdout.write(self.command.style.SUCCESS(text))

    def warning(self, text):
        self.command.stdout.write(self.command.style.WARNING(text))

    def error(self, text):
        self.command.stdout.write(self.command.style.ERROR(text))

    # ── input helpers ─────────────────────────────────────────────────────
    def prompt(self, label):
        return self.input_fn(label).strip()

    def prompt_required(self, label):
        while True:
            value = self.prompt(label)
            if value:
                return value
            self.warning("Value is required.")

    def confirm(self, question):
        return self.prompt(f"{question} (y/n): ").lower() == "y"

    def pause(self, label="\nPress Enter to return..."):
        self.input_fn(label)

    # ── COURSE MANAGEMENT (Main) ──────────────────────────────────────────
    def main_menu(self):
        while True:
            course_count = Course.objects.count()
            self.write("\n========================================")
            self.write("           COURSE MANAGEMENT")
            self.write("========================================\n")
            self.write(f"1. List Courses ({course_count})")
            self.write("2. Add Course")
            self.write("3. Edit Course")
            self.write("4. Toggle Course Active/Inactive")
            self.write("5. Delete Course")
            self.write("6. Manage Batches")
            self.write("7. Manage Required Skills")
            self.write("8. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.list_courses()
            elif choice == "2":
                self.add_course()
            elif choice == "3":
                self.edit_course()
            elif choice == "4":
                self.toggle_course()
            elif choice == "5":
                self.delete_course()
            elif choice == "6":
                self.batches_menu()
            elif choice == "7":
                self.required_skills_menu()
            elif choice == "8" or choice.lower() == "b":
                break
            else:
                self.warning("Invalid option. Please choose 1 to 8.")

    # ── 1. List Courses ───────────────────────────────────────────────────
    def list_courses(self):
        courses = Course.objects.annotate(
            batch_count=Count("batches", distinct=True),
            skill_count=Count("course_skills", distinct=True),
        ).order_by("code")

        self.write("\nCOURSES\n")
        if not courses:
            self.write("No courses defined yet.")
            self.pause()
            return

        self.write("-" * 60)
        for idx, course in enumerate(courses, start=1):
            status = "Active" if course.is_active else "Inactive"
            desc = course.description or "(no description)"
            self.write(
                f"{idx}. [{course.code}] {course.name}  [{status}]\n"
                f"   Batches: {course.batch_count} | Required Skills: {course.skill_count} | {desc}"
            )
            self.write("-" * 60)
        self.pause()

    # ── 2. Add Course ─────────────────────────────────────────────────────
    def add_course(self):
        self.write("\nADD COURSE\n")
        code = self.prompt_required("Course code (e.g. CS101): ")
        if Course.objects.filter(code__iexact=code).exists():
            self.error(f"A course with code '{code}' already exists.")
            return

        name = self.prompt_required("Course name: ")
        description = self.prompt("Description (optional, Enter to skip): ")

        course = Course.objects.create(
            code=code,
            name=name,
            description=description,
        )
        self.success(f"✓ Course '{course.code} - {course.name}' created.")

    # ── 3. Edit Course ────────────────────────────────────────────────────
    def edit_course(self):
        course = self.select_course()
        if course is None:
            return

        self.write(f"\nEditing: [{course.code}] {course.name}")
        self.write("Press Enter to keep the current value.")

        code = self.prompt(f"Course code [{course.code}]: ") or course.code
        if code.lower() != course.code.lower() and Course.objects.filter(code__iexact=code).exists():
            self.error(f"A course with code '{code}' already exists.")
            return

        name = self.prompt(f"Course name [{course.name}]: ") or course.name
        description = self.prompt(f"Description [{course.description or '(none)'}]: ") or course.description

        course.code = code
        course.name = name
        course.description = description
        course.save(update_fields=["code", "name", "description", "updated_at"])
        self.success(f"✓ Course updated to '[{course.code}] {course.name}'.")

    # ── 4. Toggle Course Active/Inactive ───────────────────────────────────
    def toggle_course(self):
        course = self.select_course()
        if course is None:
            return

        course.is_active = not course.is_active
        course.save(update_fields=["is_active", "updated_at"])
        state = "active" if course.is_active else "inactive"
        self.success(f"✓ Course '{course.code}' is now {state}.")

    # ── 5. Delete Course ──────────────────────────────────────────────────
    def delete_course(self):
        course = self.select_course()
        if course is None:
            return

        batch_count = course.batches.count()
        skill_count = course.course_skills.count()
        if batch_count or skill_count:
            self.warning(
                f"Warning: Course '{course.code}' has {batch_count} batch(es) "
                f"and {skill_count} required skill mapping(s). Deleting the course "
                f"will cascade delete these records."
            )

        if not self.confirm(f"Are you sure you want to delete course '{course.code} - {course.name}'?"):
            self.write("Deletion cancelled.")
            return

        try:
            code = course.code
            course.delete()
            self.success(f"✓ Course '{code}' deleted.")
        except ProtectedError as pe:
            self.error(
                f"Cannot delete course '{course.code}': it is referenced by protected "
                f"records (e.g. students or activities). Details: {pe}"
            )

    # ── Course selector ───────────────────────────────────────────────────
    def select_course(self):
        courses = list(Course.objects.order_by("code"))
        if not courses:
            self.write("No courses exist yet. Add one first.")
            return None

        self.write("\nAVAILABLE COURSES\n")
        self.write("-" * 60)
        for idx, course in enumerate(courses, start=1):
            status = "Active" if course.is_active else "Inactive"
            self.write(f"{idx}. [{course.code}] {course.name}  [{status}]")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select course number (or B to go back): ")
        if selection.lower() == "b":
            return None
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return None

        idx = int(selection)
        if 1 <= idx <= len(courses):
            return courses[idx - 1]
        self.warning("Selection out of range.")
        return None

    # ── BATCH MANAGEMENT ──────────────────────────────────────────────────
    def batches_menu(self):
        course = self.select_course()
        if course is None:
            return

        while True:
            batch_count = course.batches.count()
            self.write(f"\n========================================")
            self.write(f"COURSE: {course.name} ({course.code})")
            self.write(f"           BATCH MANAGEMENT ({batch_count})")
            self.write("========================================\n")
            self.write("1. List Batches")
            self.write("2. Add Batch")
            self.write("3. Edit Batch")
            self.write("4. Toggle Batch Active/Inactive")
            self.write("5. Delete Batch")
            self.write("6. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.list_batches(course)
            elif choice == "2":
                self.add_batch(course)
            elif choice == "3":
                self.edit_batch(course)
            elif choice == "4":
                self.toggle_batch(course)
            elif choice == "5":
                self.delete_batch(course)
            elif choice == "6" or choice.lower() == "b":
                break
            else:
                self.warning("Invalid option. Please choose 1 to 6.")

    def list_batches(self, course):
        batches = course.batches.order_by("-start_date", "name")
        self.write(f"\nBATCHES FOR {course.code} - {course.name}\n")
        if not batches.exists():
            self.write("No batches defined for this course yet.")
            self.pause()
            return

        self.write("-" * 60)
        for idx, batch in enumerate(batches, start=1):
            status = "Active" if batch.is_active else "Inactive"
            end_str = str(batch.end_date) if batch.end_date else "Present"
            self.write(
                f"{idx}. {batch.name}  [{status}]\n"
                f"   Period: {batch.start_date} to {end_str}"
            )
            self.write("-" * 60)
        self.pause()

    def add_batch(self, course):
        self.write(f"\nADD BATCH FOR {course.code}\n")
        name = self.prompt_required("Batch name (e.g. 2026-A): ")
        if Batch.objects.filter(course=course, name__iexact=name).exists():
            self.error(f"Batch '{name}' already exists for course '{course.code}'.")
            return

        start_date = self._prompt_date("Start date (YYYY-MM-DD): ", required=True)
        if start_date is None:
            return

        end_date = self._prompt_date("End date (YYYY-MM-DD, optional, Enter to skip): ", required=False)
        if end_date and end_date < start_date:
            self.error("End date cannot be earlier than start date.")
            return

        batch = Batch.objects.create(
            course=course,
            name=name,
            start_date=start_date,
            end_date=end_date,
        )
        self.success(f"✓ Batch '{batch.name}' created under '{course.code}'.")

    def edit_batch(self, course):
        batch = self.select_batch(course)
        if batch is None:
            return

        self.write(f"\nEditing Batch: {batch.name} ({course.code})")
        self.write("Press Enter to keep current value.")

        name = self.prompt(f"Batch name [{batch.name}]: ") or batch.name
        if name.lower() != batch.name.lower() and Batch.objects.filter(course=course, name__iexact=name).exists():
            self.error(f"Batch '{name}' already exists for course '{course.code}'.")
            return

        start_date_str = self.prompt(f"Start date [{batch.start_date}]: ")
        if start_date_str:
            start_date = self._parse_date(start_date_str)
            if start_date is None:
                self.error("Invalid date format. Use YYYY-MM-DD.")
                return
        else:
            start_date = batch.start_date

        current_end_str = str(batch.end_date) if batch.end_date else "(none)"
        end_date_str = self.prompt(f"End date [{current_end_str}]: ")
        if end_date_str:
            if end_date_str.lower() in ("none", "clear"):
                end_date = None
            else:
                end_date = self._parse_date(end_date_str)
                if end_date is None:
                    self.error("Invalid date format. Use YYYY-MM-DD.")
                    return
        else:
            end_date = batch.end_date

        if end_date and end_date < start_date:
            self.error("End date cannot be earlier than start date.")
            return

        batch.name = name
        batch.start_date = start_date
        batch.end_date = end_date
        batch.save(update_fields=["name", "start_date", "end_date", "updated_at"])
        self.success(f"✓ Batch '{batch.name}' updated.")

    def toggle_batch(self, course):
        batch = self.select_batch(course)
        if batch is None:
            return

        batch.is_active = not batch.is_active
        batch.save(update_fields=["is_active", "updated_at"])
        state = "active" if batch.is_active else "inactive"
        self.success(f"✓ Batch '{batch.name}' is now {state}.")

    def delete_batch(self, course):
        batch = self.select_batch(course)
        if batch is None:
            return

        if not self.confirm(f"Are you sure you want to delete batch '{batch.name}'?"):
            self.write("Deletion cancelled.")
            return

        try:
            name = batch.name
            batch.delete()
            self.success(f"✓ Batch '{name}' deleted.")
        except ProtectedError as pe:
            self.error(
                f"Cannot delete batch '{batch.name}': it is referenced by students or "
                f"activities. Details: {pe}"
            )

    def select_batch(self, course):
        batches = list(course.batches.order_by("-start_date", "name"))
        if not batches:
            self.write(f"No batches exist for course '{course.code}'. Add one first.")
            return None

        self.write(f"\nBatches for '{course.code}'\n")
        self.write("-" * 60)
        for idx, batch in enumerate(batches, start=1):
            status = "Active" if batch.is_active else "Inactive"
            self.write(f"{idx}. {batch.name}  [{status}] ({batch.start_date} to {batch.end_date or 'Present'})")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select batch number (or B to go back): ")
        if selection.lower() == "b":
            return None
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return None

        idx = int(selection)
        if 1 <= idx <= len(batches):
            return batches[idx - 1]
        self.warning("Selection out of range.")
        return None

    def _prompt_date(self, label, required=True):
        while True:
            val = self.prompt(label)
            if not val:
                if required:
                    self.warning("Date is required.")
                    continue
                return None
            dt = self._parse_date(val)
            if dt is not None:
                return dt
            self.error("Invalid date format. Expected YYYY-MM-DD.")
            if not required:
                return None

    def _parse_date(self, val):
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            return None

    # ── REQUIRED SKILLS MANAGEMENT ─────────────────────────────────────────
    def required_skills_menu(self):
        course = self.select_course()
        if course is None:
            return

        while True:
            req_count = course.course_skills.count()
            self.write("\n========================================")
            self.write(f"COURSE: {course.name} ({course.code})")
            self.write(f"       REQUIRED SKILLS ({req_count})")
            self.write("========================================\n")
            self.write("1. View Required Skills")
            self.write("2. Add Required Skill")
            self.write("3. Remove Required Skill")
            self.write("4. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.view_required_skills(course)
            elif choice == "2":
                self.add_required_skill(course)
            elif choice == "3":
                self.remove_required_skill(course)
            elif choice == "4" or choice.lower() == "b":
                break
            else:
                self.warning("Invalid option. Please choose 1, 2, 3, or 4.")

    def view_required_skills(self, course):
        """Displays required skills and subskills formatted as a tree per category."""
        course_skills = list(
            course.course_skills.select_related("skill__category", "sub_skill").order_by(
                "skill__category__name", "skill__name", "sub_skill__display_order", "sub_skill__id"
            )
        )

        self.write(f"\n{course.name} ({course.code})\n")
        self.write("Required Skills")
        self.write("-" * 40)

        if not course_skills:
            self.write("No required skills mapped for this course yet.")
            self.write("-" * 40)
            self.pause()
            return

        # Group mappings: category -> skill -> list of subskills (or None if skill-only)
        # Note: A course can have skill-only mapping (sub_skill is None) OR sub_skill mappings.
        tree = {}
        for cs in course_skills:
            cat_name = cs.skill.category.name
            skill_name = cs.skill.name
            if cat_name not in tree:
                tree[cat_name] = {}
            if skill_name not in tree[cat_name]:
                tree[cat_name][skill_name] = []

            if cs.sub_skill is not None:
                tree[cat_name][skill_name].append(cs.sub_skill.name)

        # Print tree representation
        for cat_name, skills in tree.items():
            for skill_name, subskills in skills.items():
                self.write(cat_name)
                self.write(f"└── {skill_name}")
                if subskills:
                    for s_idx, sub_name in enumerate(subskills):
                        connector = "└── " if s_idx == len(subskills) - 1 else "├── "
                        self.write(f"    {connector}{sub_name}")
                else:
                    self.write("    (entire skill)")
                self.write("")

        self.write(f"Total mappings: {len(course_skills)}")
        self.write("-" * 40)
        self.pause()

    def add_required_skill(self, course):
        """Steps:
        1. Display existing active Skill Categories.
        2. Select a Skill.
        3. Display that Skill's active SubSkills.
        4. Allow admin to select required SubSkills (or whole skill if none/desired).
        5. Create appropriate CourseSkill records safely.
        """
        self.write(f"\nADD REQUIRED SKILL TO {course.code}\n")

        # Step 1: Active Categories
        categories = list(SkillCategory.objects.filter(is_active=True).order_by("name"))
        if not categories:
            self.warning("No active skill categories found. Please create/activate categories first.")
            return

        self.write("ACTIVE SKILL CATEGORIES\n" + "-" * 40)
        for idx, cat in enumerate(categories, start=1):
            self.write(f"{idx}. {cat.name}")
        self.write("-" * 40)
        self.write("B. Back\n")

        cat_sel = self.prompt("Select category number (or B to cancel): ")
        if cat_sel.lower() == "b":
            return
        if not cat_sel.isdigit() or not (1 <= int(cat_sel) <= len(categories)):
            self.warning("Invalid category selection.")
            return

        category = categories[int(cat_sel) - 1]

        # Step 2: Active Skills in Category
        skills = list(category.skills.filter(is_active=True).order_by("name"))
        if not skills:
            self.warning(f"Category '{category.name}' has no active skills.")
            return

        self.write(f"\nACTIVE SKILLS IN '{category.name}'\n" + "-" * 40)
        for idx, sk in enumerate(skills, start=1):
            sub_count = sk.sub_skills.filter(is_active=True).count()
            self.write(f"{idx}. {sk.name} (Active SubSkills: {sub_count})")
        self.write("-" * 40)
        self.write("B. Back\n")

        skill_sel = self.prompt("Select skill number (or B to cancel): ")
        if skill_sel.lower() == "b":
            return
        if not skill_sel.isdigit() or not (1 <= int(skill_sel) <= len(skills)):
            self.warning("Invalid skill selection.")
            return

        skill = skills[int(skill_sel) - 1]

        # Step 3: Active SubSkills in Skill
        sub_skills = list(skill.sub_skills.filter(is_active=True).order_by("display_order", "id"))
        if not sub_skills:
            # Skill has no subskills: check if whole skill can be mapped
            self.write(f"\nSkill '{skill.name}' has no subskills.")
            if not self.confirm(f"Map entire skill '{skill.name}' to {course.code}?"):
                return

            if CourseSkill.objects.filter(course=course, skill=skill, sub_skill__isnull=True).exists():
                self.warning(f"Skill '{skill.name}' is already mapped to {course.code}.")
                return

            CourseSkill.objects.create(course=course, skill=skill, sub_skill=None)
            self.success(f"✓ Skill '{skill.name}' added to {course.code}.")
            return

        # Step 4: Allow admin to select required SubSkills
        self.write(f"\nACTIVE SUBSKILLS FOR '{skill.name}'\n" + "-" * 40)
        for idx, sub in enumerate(sub_skills, start=1):
            already = CourseSkill.objects.filter(course=course, skill=skill, sub_skill=sub).exists()
            status_text = " [ALREADY MAPPED]" if already else ""
            self.write(f"{idx}. {sub.name}{status_text}")
        self.write("-" * 40)
        self.write("Enter numbers separated by comma (e.g. 1, 2, 3), 'ALL' for all subskills, or 'B' to cancel.\n")

        selection = self.prompt("Select subskills: ")
        if selection.lower() == "b":
            return

        selected_subskills = []
        if selection.upper() == "ALL":
            selected_subskills = sub_skills
        else:
            parts = [p.strip() for p in selection.split(",") if p.strip()]
            if not parts:
                self.warning("No subskills selected.")
                return

            for part in parts:
                if not part.isdigit():
                    self.warning(f"Invalid entry '{part}'. Aborting.")
                    return
                idx = int(part)
                if not (1 <= idx <= len(sub_skills)):
                    self.warning(f"Index '{idx}' is out of range. Aborting.")
                    return
                sub = sub_skills[idx - 1]
                if sub not in selected_subskills:
                    selected_subskills.append(sub)

        # Step 5: Create CourseSkill records safely with duplicate protection
        created_count = 0
        skipped_count = 0
        for sub in selected_subskills:
            exists = CourseSkill.objects.filter(
                course=course,
                skill=skill,
                sub_skill=sub,
            ).exists()
            if exists:
                self.warning(f"Mapping '{course.code} → {skill.name} → {sub.name}' already exists. Skipped.")
                skipped_count += 1
            else:
                CourseSkill.objects.create(
                    course=course,
                    skill=skill,
                    sub_skill=sub,
                )
                created_count += 1

        if created_count > 0:
            self.success(f"✓ Successfully mapped {created_count} subskill(s) to {course.code}.")
        if skipped_count > 0 and created_count == 0:
            self.warning("No new mappings were created (all selected were already mapped).")

    def remove_required_skill(self, course):
        """Remove a required skill mapping from the course."""
        mappings = list(
            course.course_skills.select_related("skill__category", "sub_skill").order_by(
                "skill__category__name", "skill__name", "sub_skill__name"
            )
        )
        if not mappings:
            self.write(f"No required skills mapped for {course.code} to remove.")
            return

        self.write(f"\nCURRENT REQUIRED SKILL MAPPINGS FOR {course.code}\n" + "-" * 60)
        for idx, cs in enumerate(mappings, start=1):
            sub_label = f" → {cs.sub_skill.name}" if cs.sub_skill else " (entire skill)"
            self.write(f"{idx}. [{cs.skill.category.name}] {cs.skill.name}{sub_label}")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select mapping number to remove (or B to cancel): ")
        if selection.lower() == "b":
            return
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return

        idx = int(selection)
        if not (1 <= idx <= len(mappings)):
            self.warning("Selection out of range.")
            return

        chosen = mappings[idx - 1]
        target_name = (
            f"{chosen.skill.name} → {chosen.sub_skill.name}"
            if chosen.sub_skill
            else chosen.skill.name
        )
        if not self.confirm(f"Remove required skill '{target_name}' from {course.code}?"):
            self.write("Removal cancelled.")
            return

        try:
            chosen.delete()
            self.success(f"✓ Removed '{target_name}' from {course.code}.")
        except ProtectedError as pe:
            self.error(f"Cannot remove mapping: it is referenced by other records ({pe}).")
