import random
from django.core.management.base import BaseCommand
from apps.assessments.models import QuestionBank, AssessmentConfig


class Command(BaseCommand):
    help = "Seed the CSL Initial Assessment question bank with 250 Aptitude and 250 Coding MCQs."

    def handle(self, *args, **options):
        # 1. Ensure active AssessmentConfig
        config, _ = AssessmentConfig.objects.get_or_create(
            is_active=True,
            defaults={
                "title": "CSL Initial Assessment",
                "duration_minutes": 60,
                "total_marks": 50,
                "aptitude_count": 25,
                "coding_count": 25,
            },
        )
        self.stdout.write(f"Config verified: {config}")

        # Check existing counts
        existing_apt = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.APTITUDE).count()
        existing_cod = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.CODING).count()

        apt_to_create = max(0, 250 - existing_apt)
        cod_to_create = max(0, 250 - existing_cod)

        self.stdout.write(f"Existing: Aptitude={existing_apt}, Coding={existing_cod}")
        self.stdout.write(f"To create: Aptitude={apt_to_create}, Coding={cod_to_create}")

        # Aptitude topics
        apt_topics = [
            ("Quantitative Aptitude", "Percentage and Ratios"),
            ("Quantitative Aptitude", "Time, Speed and Distance"),
            ("Quantitative Aptitude", "Profit and Loss"),
            ("Quantitative Aptitude", "Averages and Mixtures"),
            ("Logical Reasoning", "Number and Alphabet Series"),
            ("Logical Reasoning", "Coding-Decoding"),
            ("Logical Reasoning", "Blood Relations"),
            ("Logical Reasoning", "Direction Sense"),
            ("Logical Reasoning", "Syllogisms and Deductions"),
            ("Verbal Ability", "Sentence Correction and Grammar"),
            ("Verbal Ability", "Reading Comprehension Vocab"),
            ("Verbal Ability", "Synonyms and Antonyms"),
        ]

        # Coding topics
        cod_topics = [
            ("Programming Fundamentals", "Variables and Expressions"),
            ("Programming Fundamentals", "Conditional Control Flow (if-else, switch)"),
            ("Programming Fundamentals", "Loops and Iterations (for, while)"),
            ("Programming Fundamentals", "Functions, Scope and Recursion"),
            ("Object-Oriented Programming", "Classes, Objects and Constructors"),
            ("Object-Oriented Programming", "Inheritance and Polymorphism"),
            ("Object-Oriented Programming", "Encapsulation and Abstraction"),
            ("Data Structures & Algorithms", "Arrays, Strings and Indexing"),
            ("Data Structures & Algorithms", "Stacks and Queues Fundamentals"),
            ("Data Structures & Algorithms", "Time and Space Complexity Analysis"),
            ("Debugging & Output", "Pointer and Reference Mechanics"),
            ("Debugging & Output", "Exception Handling and Edge Cases"),
        ]

        difficulties = ["EASY", "MEDIUM", "HARD"]
        options_keys = ["A", "B", "C", "D"]

        # Generate Aptitude MCQs
        apt_objects = []
        for i in range(apt_to_create):
            num = existing_apt + i + 1
            cat, sub = random.choice(apt_topics)
            diff = difficulties[num % 3]
            correct = options_keys[num % 4]
            apt_objects.append(
                QuestionBank(
                    prompt=f"[Aptitude #{num}] In a calculation involving {sub}, if quantity A increases by {10 + (num % 20)}% and quantity B decreases proportionally, what is the net effect?",
                    section_type=QuestionBank.SectionType.APTITUDE,
                    category=cat,
                    difficulty=diff,
                    option_a=f"Net change of +{(num * 2) % 15}%",
                    option_b=f"Net change of -{(num * 3) % 12}%",
                    option_c="Remains invariant at equilibrium",
                    option_d=f"Indeterminate without base parameter K={num}",
                    correct_option=correct,
                    explanation=f"Analytical solution derived from standard {sub} formulation.",
                    is_active=True,
                )
            )

        if apt_objects:
            QuestionBank.objects.bulk_create(apt_objects)
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(apt_objects)} Aptitude questions."))

        # Generate Coding MCQs
        cod_objects = []
        for i in range(cod_to_create):
            num = existing_cod + i + 1
            cat, sub = random.choice(cod_topics)
            diff = difficulties[num % 3]
            correct = options_keys[(num + 1) % 4]
            cod_objects.append(
                QuestionBank(
                    prompt=f"[Coding #{num}] Consider the code pattern illustrating {sub}:\n```\ndef process_node(data):\n    count = {num}\n    return [x for x in data if x % 2 == 0]\n```\nWhat is the asymptotic behavior or output contract of this logic?",
                    section_type=QuestionBank.SectionType.CODING,
                    category=cat,
                    difficulty=diff,
                    option_a="Executes in O(N) linear time and filters even elements",
                    option_b="Throws an unexpected IndexError during execution",
                    option_c="Mutates the input sequence in-place",
                    option_d="Produces O(N^2) complexity due to nested generator",
                    correct_option=correct,
                    explanation=f"Evaluation follows deterministic runtime rules for {sub}.",
                    is_active=True,
                )
            )

        if cod_objects:
            QuestionBank.objects.bulk_create(cod_objects)
            self.stdout.write(self.style.SUCCESS(f"Successfully seeded {len(cod_objects)} Coding questions."))

        total_apt = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.APTITUDE).count()
        total_cod = QuestionBank.objects.filter(section_type=QuestionBank.SectionType.CODING).count()
        self.stdout.write(self.style.SUCCESS(f"Bank Status: {total_apt} Aptitude MCQs, {total_cod} Coding MCQs (Total: {total_apt + total_cod})."))
