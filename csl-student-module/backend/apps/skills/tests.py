from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.skills.cli import SkillManagementCLI
from apps.skills.models import Skill, SkillCategory, SubSkill


class _FakeCommand:
    """Minimal stand-in for a BaseCommand so SkillManagementCLI is testable."""

    def __init__(self, out):
        self.stdout = _Stdout(out)
        self.style = _NoStyle()


class _Stdout:
    def __init__(self, out):
        self._out = out

    def write(self, text=""):
        self._out.write(str(text) + "\n")


class _NoStyle:
    def SUCCESS(self, text):
        return text

    def WARNING(self, text):
        return text

    def ERROR(self, text):
        return text


def make_cli(out, script):
    """Build a SkillManagementCLI whose input comes from a scripted list."""
    answers = iter(script)

    def input_fn(_label):
        return next(answers)

    return SkillManagementCLI(_FakeCommand(out), input_fn=input_fn)


class AdminCliSkillMenuTests(TestCase):
    """Full admin CLI runs with a scripted input function (no real stdin)."""

    def _run(self, script):
        out = StringIO()
        answers = iter(script)

        def scripted_input(_label):
            return next(answers)

        import builtins
        old_input = builtins.input
        builtins.input = scripted_input
        try:
            call_command("admin_cli", stdout=out)
        finally:
            builtins.input = old_input
        return out.getvalue()

    def test_main_menu_lists_skill_management(self):
        output = self._run(["5"])
        self.assertIn("3. Skill Management", output)
        self.assertIn("4. Course Management", output)
        self.assertIn("Exiting Admin CLI", output)

    def test_skill_management_entry_point_opens(self):
        # 3 opens Skill Management, 5 goes back, 5 exits the admin CLI.
        output = self._run(["3", "5", "5"])
        self.assertIn("SKILL MANAGEMENT", output)
        self.assertIn("Manage Categories", output)
        self.assertIn("Manage Skills", output)
        self.assertIn("Manage Sub-Skills", output)
        self.assertIn("Exiting Admin CLI", output)

    def test_add_category_through_cli(self):
        output = self._run(["3", "2", "2", "Programming", "", "6", "5", "5"])
        self.assertIn("Category 'Programming' created.", output)
        self.assertTrue(SkillCategory.objects.filter(name="Programming").exists())

    def test_add_skill_through_cli(self):
        SkillCategory.objects.create(name="Programming")
        output = self._run(["3", "3", "2", "1", "Python", "", "6", "5", "5"])
        self.assertIn("Programming / Python' created.", output)
        self.assertTrue(Skill.objects.filter(name="Python").exists())

    def test_add_sub_skill_through_cli(self):
        category = SkillCategory.objects.create(name="Programming")
        Skill.objects.create(category=category, name="Python")
        output = self._run(["3", "4", "2", "1", "1", "OOP", "", "6", "5", "5"])
        self.assertIn("Python / OOP' created.", output)
        self.assertTrue(SubSkill.objects.filter(name="OOP").exists())

    def test_view_taxonomy_through_cli(self):
        category = SkillCategory.objects.create(name="Programming")
        skill = Skill.objects.create(category=category, name="Python")
        SubSkill.objects.create(skill=skill, name="Fundamentals")
        output = self._run(["3", "1", "", "5", "5"])
        self.assertIn("Programming", output)
        self.assertIn("└── Python", output)
        self.assertIn("└── Fundamentals", output)
        self.assertIn("Totals: 1 categories, 1 skills, 1 sub-skills", output)

    def test_delete_category_through_cli(self):
        category = SkillCategory.objects.create(name="Programming")
        skill = Skill.objects.create(category=category, name="Python")
        SubSkill.objects.create(skill=skill, name="Fundamentals")
        output = self._run(["3", "2", "5", "1", "y", "6", "5", "5"])
        self.assertIn("Category 'Programming' deleted.", output)
        self.assertEqual(SkillCategory.objects.count(), 0)
        self.assertEqual(Skill.objects.count(), 0)
        self.assertEqual(SubSkill.objects.count(), 0)


class SkillTaxonomyCLITests(TestCase):
    """Targeted CLI behaviour tests with scripted input."""

    def setUp(self):
        self.out = StringIO()
        self.category = SkillCategory.objects.create(name="Programming")
        self.skill = Skill.objects.create(category=self.category, name="Python")
        SubSkill.objects.create(skill=self.skill, name="Fundamentals")

    def test_duplicate_category_name_rejected(self):
        cli = make_cli(self.out, ["Programming", ""])
        cli.add_category()
        self.assertIn("already exists", self.out.getvalue())
        self.assertEqual(SkillCategory.objects.count(), 1)

    def test_duplicate_skill_name_rejected(self):
        # add_skill prompts: category selection, then name, then description.
        cli = make_cli(self.out, ["1", "Python", ""])
        cli.add_skill()
        self.assertIn("already exists", self.out.getvalue())
        self.assertEqual(Skill.objects.count(), 1)

    def test_duplicate_skill_name_allowed_in_other_category(self):
        SkillCategory.objects.create(name="Databases")
        # Category 1 is 'Databases' (ordered by name), so 'Python' is new there.
        cli = make_cli(self.out, ["1", "Python", ""])
        cli.add_skill()
        self.assertIn("Databases / Python' created.", self.out.getvalue())
        self.assertEqual(Skill.objects.count(), 2)

    def test_duplicate_sub_skill_name_rejected(self):
        # add_sub_skill prompts: category, skill, then name.
        cli = make_cli(self.out, ["1", "1", "Fundamentals", ""])
        cli.add_sub_skill()
        self.assertIn("already exists", self.out.getvalue())
        self.assertEqual(SubSkill.objects.count(), 1)

    def test_edit_category_keeps_value_on_enter(self):
        cli = make_cli(self.out, ["1", "", ""])
        cli.edit_category()
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Programming")
        self.assertIn("updated to 'Programming'", self.out.getvalue())

    def test_edit_skill_to_duplicate_name_rejected(self):
        Skill.objects.create(category=self.category, name="JavaScript")
        # Prompts: category 1, then skill 2 = 'Python' (ordered by name), then new name.
        cli = make_cli(self.out, ["1", "2", "JavaScript", ""])
        cli.edit_skill()
        self.assertIn("already exists", self.out.getvalue())
        self.skill.refresh_from_db()
        self.assertEqual(self.skill.name, "Python")

    def test_toggle_category(self):
        cli = make_cli(self.out, ["1"])
        cli.toggle_category()
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)
        self.assertIn("now inactive", self.out.getvalue())

    def test_empty_required_value_reprompts(self):
        cli = make_cli(self.out, ["", "Web Dev", ""])
        cli.add_category()
        self.assertIn("Value is required.", self.out.getvalue())
        self.assertTrue(SkillCategory.objects.filter(name="Web Dev").exists())

    def test_invalid_selection_is_reported_not_crash(self):
        cli = make_cli(self.out, ["99"])
        self.assertIsNone(cli.select_category())
        self.assertIn("Selection out of range.", self.out.getvalue())

    def test_back_selection_returns_none(self):
        cli = make_cli(self.out, ["b"])
        self.assertIsNone(cli.select_category())


class SkillTaxonomyModelTests(TestCase):
    """Model-level guarantees the CLI relies on."""

    def setUp(self):
        self.category = SkillCategory.objects.create(name="Programming")
        self.skill = Skill.objects.create(category=self.category, name="Python")
        SubSkill.objects.create(skill=self.skill, name="Fundamentals")

    def test_str_representations(self):
        self.assertEqual(str(self.category), "Programming")
        self.assertEqual(str(self.skill), "Programming / Python")

    def test_delete_skill_cascades_to_sub_skills(self):
        self.skill.delete()
        self.assertEqual(SubSkill.objects.count(), 0)

    def test_delete_category_cascades(self):
        self.category.delete()
        self.assertEqual(Skill.objects.count(), 0)
        self.assertEqual(SubSkill.objects.count(), 0)

    def test_subskill_creation_order_preserved(self):
        # Create subskills in a specific, non-alphabetical order
        s1 = SubSkill.objects.create(skill=self.skill, name="Zeta", display_order=1)
        s2 = SubSkill.objects.create(skill=self.skill, name="Alpha", display_order=2)
        s3 = SubSkill.objects.create(skill=self.skill, name="Beta", display_order=3)

        subskills = list(SubSkill.objects.filter(skill=self.skill).exclude(name="Fundamentals"))
        self.assertEqual([s.name for s in subskills], ["Zeta", "Alpha", "Beta"])

    def test_subskill_renaming_does_not_change_order(self):
        s1 = SubSkill.objects.create(skill=self.skill, name="Step 1", display_order=1)
        s2 = SubSkill.objects.create(skill=self.skill, name="Step 2", display_order=2)
        # Rename Step 1 to 'Zebra Step' (alphabetically after Step 2)
        s1.name = "Zebra Step"
        s1.save()

        subskills = list(SubSkill.objects.filter(skill=self.skill).exclude(name="Fundamentals"))
        self.assertEqual([s.name for s in subskills], ["Zebra Step", "Step 2"])

    def test_subskill_cli_add_assigns_next_order(self):
        out = StringIO()
        # Category 1 -> Skill 1 -> name -> description
        cli = make_cli(out, ["1", "1", "First Added", ""])
        cli.add_sub_skill()
        first = SubSkill.objects.get(name="First Added")
        self.assertGreater(first.display_order, 0)

        cli2 = make_cli(out, ["1", "1", "Second Added", ""])
        cli2.add_sub_skill()
        second = SubSkill.objects.get(name="Second Added")
        self.assertEqual(second.display_order, first.display_order + 1)

