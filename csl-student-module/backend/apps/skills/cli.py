"""Interactive Skill Management flow for the CSL Admin CLI.

Handles the global skill taxonomy:

    SkillCategory -> Skill -> SubSkill

This module is UI/menu logic only. It is invoked by the existing
``admin_cli`` management command (see apps/auth_api/management/commands/admin_cli.py)
and deliberately follows that command's interaction style: numbered menus,
"B. Back" navigation, and self.stdout styling.

All user input goes through an injectable ``input_fn`` (default: builtins
``input``) so the menus can be scripted in tests.
"""
from django.db.models import Count, Max, ProtectedError

from apps.skills.models import Skill, SkillCategory, SubSkill



class SkillManagementCLI:
    """Skill taxonomy management menus, driven by the admin CLI command."""

    def __init__(self, command, input_fn=None):
        # The parent BaseCommand instance provides stdout and styling.
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

    # ── entry point ───────────────────────────────────────────────────────
    def main_menu(self):
        while True:
            category_count = SkillCategory.objects.count()
            skill_count = Skill.objects.count()
            sub_skill_count = SubSkill.objects.count()

            self.write("\n========================================")
            self.write("           SKILL MANAGEMENT")
            self.write("========================================\n")
            self.write(f"1. View Skill Taxonomy  ({category_count} categories, {skill_count} skills, {sub_skill_count} sub-skills)")
            self.write("2. Manage Categories")
            self.write("3. Manage Skills")
            self.write("4. Manage Sub-Skills")
            self.write("5. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.view_taxonomy()
            elif choice == "2":
                self.categories_menu()
            elif choice == "3":
                self.skills_menu()
            elif choice == "4":
                self.sub_skills_menu()
            elif choice == "5":
                break
            else:
                self.warning("Invalid option. Please choose 1, 2, 3, 4, or 5.")

    # ── taxonomy tree view ────────────────────────────────────────────────
    def view_taxonomy(self):
        categories = SkillCategory.objects.prefetch_related(
            "skills__sub_skills"
        ).order_by("name")

        self.write("\nSKILL TAXONOMY\n")
        if not categories:
            self.write("No skill categories defined yet.")
            self.write("Use 'Manage Categories' to add the first one.")
            self.pause()
            return

        self.write("-" * 60)
        total_skills = 0
        total_sub_skills = 0
        for category in categories:
            status = "" if category.is_active else " [INACTIVE]"
            self.write(f"{category.name}{status}")
            skills = list(category.skills.all())
            if not skills:
                self.write("   (no skills)")
                continue
            for idx, skill in enumerate(skills):
                total_skills += 1
                connector = "└── " if idx == len(skills) - 1 else "├── "
                skill_status = "" if skill.is_active else " [INACTIVE]"
                self.write(f"   {connector}{skill.name}{skill_status}")
                sub_skills = list(skill.sub_skills.all())
                if not sub_skills:
                    continue
                prefix = "       " if idx == len(skills) - 1 else "   │    "
                for s_idx, sub_skill in enumerate(sub_skills):
                    total_sub_skills += 1
                    s_connector = "└── " if s_idx == len(sub_skills) - 1 else "├── "
                    sub_status = "" if sub_skill.is_active else " [INACTIVE]"
                    self.write(f"{prefix}{s_connector}{sub_skill.name}{sub_status}")
            self.write("-" * 60)

        self.write(
            f"Totals: {categories.count()} categories, "
            f"{total_skills} skills, {total_sub_skills} sub-skills"
        )
        self.pause()

    # ── categories ────────────────────────────────────────────────────────
    def categories_menu(self):
        while True:
            count = SkillCategory.objects.count()
            self.write("\nSKILL CATEGORIES\n")
            self.write(f"1. List Categories ({count})")
            self.write("2. Add Category")
            self.write("3. Edit Category")
            self.write("4. Toggle Category Active/Inactive")
            self.write("5. Delete Category")
            self.write("6. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.list_categories()
            elif choice == "2":
                self.add_category()
            elif choice == "3":
                self.edit_category()
            elif choice == "4":
                self.toggle_category()
            elif choice == "5":
                self.delete_category()
            elif choice == "6":
                break
            else:
                self.warning("Invalid option. Please choose 1, 2, 3, 4, 5, or 6.")

    def list_categories(self):
        categories = SkillCategory.objects.annotate(
            skills_count=Count("skills")
        ).order_by("name")
        self.write("\nSKILL CATEGORIES\n")
        if not categories:
            self.write("No skill categories defined yet.")
            return

        self.write("-" * 60)
        for idx, category in enumerate(categories, start=1):
            status = "Active" if category.is_active else "Inactive"
            description = category.description or "(no description)"
            self.write(
                f"{idx}. {category.name}  [{status}]\n"
                f"   Skills: {category.skills_count} | {description}"
            )
            self.write("-" * 60)
        self.pause()

    def add_category(self):
        self.write("\nADD SKILL CATEGORY\n")
        name = self.prompt_required("Category name: ")
        if self._category_name_taken(name):
            self.error(f"A category named '{name}' already exists.")
            return

        description = self.prompt("Description (optional, Enter to skip): ")
        category = SkillCategory.objects.create(
            name=name,
            description=description,
        )
        self.success(f"✓ Category '{category.name}' created.")

    def edit_category(self):
        category = self.select_category()
        if category is None:
            return

        self.write(f"\nEditing: {category.name}")
        self.write("Press Enter to keep the current value.")
        name = self.prompt(f"Category name [{category.name}]: ") or category.name
        description = (
            self.prompt(f"Description [{category.description or '(none)'}]: ")
            or category.description
        )

        if name != category.name and self._category_name_taken(name):
            self.error(f"A category named '{name}' already exists.")
            return

        category.name = name
        category.description = description
        category.save(update_fields=["name", "description", "updated_at"])
        self.success(f"✓ Category updated to '{category.name}'.")

    def toggle_category(self):
        category = self.select_category()
        if category is None:
            return
        category.is_active = not category.is_active
        category.save(update_fields=["is_active", "updated_at"])
        state = "active" if category.is_active else "inactive"
        self.success(f"✓ Category '{category.name}' is now {state}.")

    def delete_category(self):
        category = self.select_category()
        if category is None:
            return

        skill_count = category.skills.count()
        sub_skill_count = SubSkill.objects.filter(skill__category=category).count()
        if skill_count:
            self.warning(
                f"Warning: '{category.name}' contains {skill_count} skill(s) "
                f"and {sub_skill_count} sub-skill(s). Deleting the category "
                f"deletes all of them."
            )
        if not self.confirm(f"Delete category '{category.name}'?"):
            self.write("Deletion cancelled.")
            return

        try:
            name = category.name
            category.delete()
            self.success(f"✓ Category '{name}' deleted.")
        except ProtectedError:
            self.error(
                f"Cannot delete '{category.name}': it is referenced by other "
                f"records (e.g. course skill mappings). Remove those first."
            )

    def select_category(self):
        categories = list(SkillCategory.objects.order_by("name"))
        if not categories:
            self.write("No skill categories exist yet. Add one first.")
            return None

        self.write("-" * 60)
        for idx, category in enumerate(categories, start=1):
            status = "Active" if category.is_active else "Inactive"
            self.write(f"{idx}. {category.name}  [{status}] (Skills: {category.skills.count()})")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select category number (or B to go back): ")
        if selection.lower() == "b":
            return None
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return None

        idx = int(selection)
        if 1 <= idx <= len(categories):
            return categories[idx - 1]
        self.warning("Selection out of range.")
        return None

    def _category_name_taken(self, name):
        return SkillCategory.objects.filter(name__iexact=name).exists()

    # ── skills ────────────────────────────────────────────────────────────
    def skills_menu(self):
        while True:
            count = Skill.objects.count()
            self.write("\nSKILLS\n")
            self.write(f"1. List Skills ({count})")
            self.write("2. Add Skill")
            self.write("3. Edit Skill")
            self.write("4. Toggle Skill Active/Inactive")
            self.write("5. Delete Skill")
            self.write("6. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.list_skills()
            elif choice == "2":
                self.add_skill()
            elif choice == "3":
                self.edit_skill()
            elif choice == "4":
                self.toggle_skill()
            elif choice == "5":
                self.delete_skill()
            elif choice == "6":
                break
            else:
                self.warning("Invalid option. Please choose 1, 2, 3, 4, 5, or 6.")

    def list_skills(self):
        skills = Skill.objects.select_related("category").order_by("category__name", "name")
        self.write("\nSKILLS\n")
        if not skills:
            self.write("No skills defined yet.")
            return

        self.write("-" * 60)
        for idx, skill in enumerate(skills, start=1):
            status = "Active" if skill.is_active else "Inactive"
            self.write(
                f"{idx}. [{skill.category.name}] {skill.name}  [{status}]\n"
                f"   Sub-skills: {skill.sub_skills.count()} | "
                f"{skill.description or '(no description)'}"
            )
            self.write("-" * 60)
        self.pause()

    def add_skill(self):
        self.write("\nADD SKILL\n")
        category = self.select_category()
        if category is None:
            return

        name = self.prompt_required("Skill name: ")
        if self._skill_name_taken(category, name):
            self.error(f"Skill '{name}' already exists in category '{category.name}'.")
            return

        description = self.prompt("Description (optional, Enter to skip): ")
        skill = Skill.objects.create(
            category=category,
            name=name,
            description=description,
        )
        self.success(f"✓ Skill '{category.name} / {skill.name}' created.")

    def edit_skill(self):
        skill = self.select_skill()
        if skill is None:
            return

        self.write(f"\nEditing: {skill.category.name} / {skill.name}")
        self.write("Press Enter to keep the current value.")
        name = self.prompt(f"Skill name [{skill.name}]: ") or skill.name
        description = (
            self.prompt(f"Description [{skill.description or '(none)'}]: ")
            or skill.description
        )

        if name != skill.name and self._skill_name_taken(skill.category, name):
            self.error(f"Skill '{name}' already exists in category '{skill.category.name}'.")
            return

        skill.name = name
        skill.description = description
        skill.save(update_fields=["name", "description", "updated_at"])
        self.success(f"✓ Skill updated to '{skill.category.name} / {skill.name}'.")

    def toggle_skill(self):
        skill = self.select_skill()
        if skill is None:
            return
        skill.is_active = not skill.is_active
        skill.save(update_fields=["is_active", "updated_at"])
        state = "active" if skill.is_active else "inactive"
        self.success(f"✓ Skill '{skill.name}' is now {state}.")

    def delete_skill(self):
        skill = self.select_skill()
        if skill is None:
            return

        sub_skill_count = skill.sub_skills.count()
        if sub_skill_count:
            self.warning(
                f"Warning: '{skill.name}' contains {sub_skill_count} sub-skill(s). "
                f"Deleting the skill deletes all of them."
            )
        if not self.confirm(f"Delete skill '{skill.category.name} / {skill.name}'?"):
            self.write("Deletion cancelled.")
            return

        try:
            label = f"{skill.category.name} / {skill.name}"
            skill.delete()
            self.success(f"✓ Skill '{label}' deleted.")
        except ProtectedError:
            self.error(
                f"Cannot delete '{skill.name}': it is referenced by other "
                f"records (e.g. course skill mappings). Remove those first."
            )

    def select_skill(self, category=None):
        if category is None:
            category = self.select_category()
            if category is None:
                return None

        skills = list(category.skills.order_by("name"))
        if not skills:
            self.write(f"Category '{category.name}' has no skills yet.")
            return None

        self.write(f"\nSkills in '{category.name}'\n")
        self.write("-" * 60)
        for idx, skill in enumerate(skills, start=1):
            status = "Active" if skill.is_active else "Inactive"
            self.write(f"{idx}. {skill.name}  [{status}] (Sub-skills: {skill.sub_skills.count()})")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select skill number (or B to go back): ")
        if selection.lower() == "b":
            return None
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return None

        idx = int(selection)
        if 1 <= idx <= len(skills):
            return skills[idx - 1]
        self.warning("Selection out of range.")
        return None

    def _skill_name_taken(self, category, name):
        return Skill.objects.filter(category=category, name__iexact=name).exists()

    # ── sub-skills ────────────────────────────────────────────────────────
    def sub_skills_menu(self):
        while True:
            count = SubSkill.objects.count()
            self.write("\nSUB-SKILLS\n")
            self.write(f"1. List Sub-Skills ({count})")
            self.write("2. Add Sub-Skill")
            self.write("3. Edit Sub-Skill")
            self.write("4. Toggle Sub-Skill Active/Inactive")
            self.write("5. Delete Sub-Skill")
            self.write("6. Back\n")

            choice = self.prompt("Select option: ")

            if choice == "1":
                self.list_sub_skills()
            elif choice == "2":
                self.add_sub_skill()
            elif choice == "3":
                self.edit_sub_skill()
            elif choice == "4":
                self.toggle_sub_skill()
            elif choice == "5":
                self.delete_sub_skill()
            elif choice == "6":
                break
            else:
                self.warning("Invalid option. Please choose 1, 2, 3, 4, 5, or 6.")

    def list_sub_skills(self):
        sub_skills = SubSkill.objects.select_related("skill", "skill__category").order_by(
            "skill__category__name", "skill__name", "display_order", "id"
        )
        self.write("\nSUB-SKILLS\n")
        if not sub_skills:
            self.write("No sub-skills defined yet.")
            return

        self.write("-" * 60)
        for idx, sub_skill in enumerate(sub_skills, start=1):
            status = "Active" if sub_skill.is_active else "Inactive"
            self.write(
                f"{idx}. [{sub_skill.skill.category.name}] "
                f"{sub_skill.skill.name} / {sub_skill.name}  [{status}]"
            )
            self.write("-" * 60)
        self.pause()

    def add_sub_skill(self):
        self.write("\nADD SUB-SKILL\n")
        skill = self.select_skill()
        if skill is None:
            return

        name = self.prompt_required("Sub-skill name: ")
        if self._sub_skill_name_taken(skill, name):
            self.error(f"Sub-skill '{name}' already exists under skill '{skill.name}'.")
            return

        description = self.prompt("Description (optional, Enter to skip): ")
        max_order = SubSkill.objects.filter(skill=skill).aggregate(Max("display_order"))["display_order__max"] or 0
        sub_skill = SubSkill.objects.create(
            skill=skill,
            name=name,
            description=description,
            display_order=max_order + 1,
        )
        self.success(f"✓ Sub-skill '{skill.name} / {sub_skill.name}' created.")

    def edit_sub_skill(self):
        skill = self.select_skill()
        if skill is None:
            return
        sub_skill = self.select_sub_skill(skill)
        if sub_skill is None:
            return

        self.write(f"\nEditing: {skill.name} / {sub_skill.name}")
        self.write("Press Enter to keep the current value.")
        name = self.prompt(f"Sub-skill name [{sub_skill.name}]: ") or sub_skill.name
        description = (
            self.prompt(f"Description [{sub_skill.description or '(none)'}]: ")
            or sub_skill.description
        )

        if name != sub_skill.name and self._sub_skill_name_taken(skill, name):
            self.error(f"Sub-skill '{name}' already exists under skill '{skill.name}'.")
            return

        sub_skill.name = name
        sub_skill.description = description
        sub_skill.save(update_fields=["name", "description", "updated_at"])
        self.success(f"✓ Sub-skill updated to '{skill.name} / {sub_skill.name}'.")

    def toggle_sub_skill(self):
        skill = self.select_skill()
        if skill is None:
            return
        sub_skill = self.select_sub_skill(skill)
        if sub_skill is None:
            return
        sub_skill.is_active = not sub_skill.is_active
        sub_skill.save(update_fields=["is_active", "updated_at"])
        state = "active" if sub_skill.is_active else "inactive"
        self.success(f"✓ Sub-skill '{sub_skill.name}' is now {state}.")

    def delete_sub_skill(self):
        skill = self.select_skill()
        if skill is None:
            return
        sub_skill = self.select_sub_skill(skill)
        if sub_skill is None:
            return

        if not self.confirm(f"Delete sub-skill '{skill.name} / {sub_skill.name}'?"):
            self.write("Deletion cancelled.")
            return

        try:
            name = sub_skill.name
            sub_skill.delete()
            self.success(f"✓ Sub-skill '{name}' deleted.")
        except ProtectedError:
            self.error(
                f"Cannot delete '{sub_skill.name}': it is referenced by other "
                f"records (e.g. course skill mappings). Remove those first."
            )

    def select_sub_skill(self, skill):
        sub_skills = list(skill.sub_skills.order_by("display_order", "id"))
        if not sub_skills:
            self.write(f"Skill '{skill.name}' has no sub-skills yet.")
            return None

        self.write(f"\nSub-skills under '{skill.name}'\n")
        self.write("-" * 60)
        for idx, sub_skill in enumerate(sub_skills, start=1):
            status = "Active" if sub_skill.is_active else "Inactive"
            self.write(f"{idx}. {sub_skill.name}  [{status}]")
        self.write("-" * 60)
        self.write("B. Back\n")

        selection = self.prompt("Select sub-skill number (or B to go back): ")
        if selection.lower() == "b":
            return None
        if not selection.isdigit():
            self.warning("Please enter a valid number or 'B'.")
            return None

        idx = int(selection)
        if 1 <= idx <= len(sub_skills):
            return sub_skills[idx - 1]
        self.warning("Selection out of range.")
        return None

    def _sub_skill_name_taken(self, skill, name):
        return SubSkill.objects.filter(skill=skill, name__iexact=name).exists()
