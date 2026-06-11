"""Tests for project_intake.py — deterministic project intake question generator.

Pure unit tests — no DB, no LLM, no network, no side effects.
"""

from __future__ import annotations

import asyncio
import inspect
import unittest

import src.orchestrator.project_intake as project_intake_module
from src.orchestrator.project_intake import (
    ConfirmedPlanRunPreviewRequest,
    ConfirmedPlanRunPreviewResponse,
    ConfirmedRunStepPreview,
    DevelopmentPlanPhaseStatus,
    DevelopmentPlanPreviewRequest,
    DevelopmentPlanPreviewResponse,
    MAX_TOTAL,
    ProjectBriefDraftRequest,
    ProjectBriefDraftResponse,
    ProjectBriefSectionStatus,
    ProjectIntakeMode,
    ProjectIntakeRequest,
    ProjectIntakeResponse,
    ProjectMaturityGoal,
    RequirementCoveragePreviewRequest,
    RequirementCoveragePreviewResponse,
    RequirementCoveragePreviewStatus,
    SourceOfTruthPreviewRequest,
    SourceOfTruthPreviewResponse,
    ProjectTargetType,
    QuestionCategory,
    QuestionPriority,
    analyze_project_intake,
    build_confirmed_plan_run_preview,
    build_requirement_coverage_from_plan,
    build_source_of_truth_from_intake,
    detect_intake_mode,
    detect_maturity_goal,
    detect_target_type,
    draft_development_plan,
    draft_project_brief,
)
from src.orchestrator.source_of_truth_contract import (
    ProjectRequirementContract,
    ProjectSourceOfTruthContract,
    ProjectInputSourceType,
    RequirementPriority,
    RequirementStatus,
)


class TestDetectIntakeMode(unittest.TestCase):
    """Mode detection — new vs existing project."""

    def test_explicit_mode_overrides_detection(self):
        req = ProjectIntakeRequest(idea="anything", mode=ProjectIntakeMode.EXISTING_PROJECT)
        self.assertEqual(detect_intake_mode(req), ProjectIntakeMode.EXISTING_PROJECT)

    def test_existing_project_attached_flag(self):
        req = ProjectIntakeRequest(idea="some idea", existing_project_attached=True)
        self.assertEqual(detect_intake_mode(req), ProjectIntakeMode.EXISTING_PROJECT)

    def test_existing_keyword_russian(self):
        req = ProjectIntakeRequest(idea="Уже есть проект на Django, нужно доработать")
        self.assertEqual(detect_intake_mode(req), ProjectIntakeMode.EXISTING_PROJECT)

    def test_existing_keyword_english(self):
        req = ProjectIntakeRequest(idea="I have an existing React app that needs refactoring")
        self.assertEqual(detect_intake_mode(req), ProjectIntakeMode.EXISTING_PROJECT)

    def test_existing_project_onboarding_phrases(self):
        phrases = [
            "у меня уже есть проект на Laravel",
            "полуготовый проект нужно довести до MVP",
            "продолжить разработку CRM",
            "доработать существующий проект",
            "загрузить папку проекта и продолжить",
            "existing project with a broken test suite",
            "continue an existing app",
        ]

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    detect_intake_mode(ProjectIntakeRequest(idea=phrase)),
                    ProjectIntakeMode.EXISTING_PROJECT,
                )

    def test_new_project_default(self):
        req = ProjectIntakeRequest(idea="Build a task management web app")
        self.assertEqual(detect_intake_mode(req), ProjectIntakeMode.NEW_PROJECT)


class TestDetectTargetType(unittest.TestCase):
    """Target type detection from idea text."""

    def test_web_app(self):
        self.assertEqual(detect_target_type("Build a React dashboard"), ProjectTargetType.WEB_APP)

    def test_mobile_app(self):
        self.assertEqual(detect_target_type("Flutter мобильное приложение"), ProjectTargetType.MOBILE_APP)

    def test_api_service(self):
        self.assertEqual(detect_target_type("Build a REST API microservice"), ProjectTargetType.API_SERVICE)

    def test_cli_tool(self):
        self.assertEqual(detect_target_type("Command-line utility for file processing"), ProjectTargetType.CLI_TOOL)

    def test_automation(self):
        self.assertEqual(detect_target_type("Telegram bot для уведомлений"), ProjectTargetType.AUTOMATION)

    def test_desktop(self):
        self.assertEqual(detect_target_type("Electron desktop app"), ProjectTargetType.DESKTOP_APP)

    def test_unknown(self):
        self.assertEqual(detect_target_type("I want to build something cool"), ProjectTargetType.UNKNOWN)


class TestDetectMaturityGoal(unittest.TestCase):
    """Maturity goal detection from idea text."""

    def test_mvp(self):
        self.assertEqual(detect_maturity_goal("Build an MVP for a startup"), ProjectMaturityGoal.MVP)

    def test_full_product(self):
        self.assertEqual(detect_maturity_goal("Full production system"), ProjectMaturityGoal.FULL_PRODUCT)

    def test_diploma(self):
        self.assertEqual(detect_maturity_goal("Дипломный проект для университета"), ProjectMaturityGoal.DIPLOMA)

    def test_prototype(self):
        self.assertEqual(detect_maturity_goal("Quick proof of concept demo"), ProjectMaturityGoal.PROTOTYPE)

    def test_internal_tool(self):
        self.assertEqual(detect_maturity_goal("Internal tool для команды"), ProjectMaturityGoal.INTERNAL_TOOL)

    def test_unknown(self):
        self.assertEqual(detect_maturity_goal("I want to build something"), ProjectMaturityGoal.UNKNOWN)


class TestAnalyzeProjectIntake(unittest.TestCase):
    """Full intake analysis — entry point tests."""

    def test_vague_idea_returns_many_questions_not_ready(self):
        """A vague idea should produce required questions and not be ready to plan."""
        resp = analyze_project_intake(ProjectIntakeRequest(idea="Хочу сделать что-то"))
        self.assertIsInstance(resp, ProjectIntakeResponse)
        self.assertFalse(resp.ready_to_plan)
        self.assertEqual(resp.confidence, "low")
        self.assertGreater(len(resp.questions), 3)
        required = [q for q in resp.questions if q.priority == QuestionPriority.REQUIRED]
        self.assertGreater(len(required), 0)

    def test_detailed_web_app_idea(self):
        """A detailed web app idea should detect type and have fewer missing fields."""
        idea = (
            "Build a React web dashboard with JWT auth, PostgreSQL database, "
            "file uploads to S3, Stripe billing, Tailwind design, "
            "deployed on AWS with full CI/CD pipeline. MVP version."
        )
        resp = analyze_project_intake(ProjectIntakeRequest(idea=idea))
        self.assertEqual(resp.detected_target_type, ProjectTargetType.WEB_APP)
        self.assertEqual(resp.detected_maturity_goal, ProjectMaturityGoal.MVP)
        self.assertEqual(resp.mode, ProjectIntakeMode.NEW_PROJECT)
        # Many signals detected → fewer missing items
        self.assertIn("Auth/login mentioned", " ".join(resp.assumptions))
        self.assertIn("Payments mentioned", " ".join(resp.assumptions))

    def test_existing_project_detection(self):
        """Existing project keywords should trigger existing mode questions."""
        resp = analyze_project_intake(
            ProjectIntakeRequest(idea="У меня уже есть Django проект, нужно продолжить разработку")
        )
        self.assertEqual(resp.mode, ProjectIntakeMode.EXISTING_PROJECT)
        self.assertFalse(resp.ready_to_plan)
        categories = {q.category for q in resp.questions}
        self.assertIn(QuestionCategory.EXISTING_PROJECT, categories)

    def test_existing_project_onboarding_questions_cover_core_context(self):
        resp = analyze_project_intake(
            ProjectIntakeRequest(idea="Доработать существующий проект, часть функций уже готова")
        )
        question_text = " ".join(q.question.lower() for q in resp.questions)

        self.assertEqual(resp.mode, ProjectIntakeMode.EXISTING_PROJECT)
        self.assertLessEqual(len(resp.questions), MAX_TOTAL)
        self.assertIn("where are the project files", question_text)
        self.assertIn("tech stack", question_text)
        self.assertIn("what already works", question_text)
        self.assertIn("broken", question_text)
        self.assertIn("next goal", question_text)
        self.assertIn("dev/build commands", question_text)
        self.assertIn("database", question_text)
        self.assertIn("environment variables", question_text)
        self.assertIn("git history", question_text)
        self.assertIn("not be modified", question_text)
        self.assertIn("tests exist", question_text)
        self.assertIn("deployment target", question_text)
        self.assertIn(".env", question_text)

    def test_bounded_question_count(self):
        """Total questions must never exceed MAX_TOTAL."""
        # Use a maximally signal-rich idea to trigger as many optional questions as possible
        idea = (
            "Build a React SPA web dashboard with JWT auth login, PostgreSQL database, "
            "S3 file upload photos, Stripe payment subscription billing, email notifications, "
            "external API integration Zapier webhook, pytest unit tests CI/CD, "
            "Docker deploy Kubernetes AWS, Figma design responsive Tailwind theme, "
            "MVP minimum viable product"
        )
        resp = analyze_project_intake(ProjectIntakeRequest(idea=idea))
        self.assertLessEqual(len(resp.questions), MAX_TOTAL)

    def test_known_stack_suppresses_stack_question(self):
        """Providing known_stack should suppress the tech stack question."""
        resp_no_stack = analyze_project_intake(
            ProjectIntakeRequest(idea="Build a web app")
        )
        resp_with_stack = analyze_project_intake(
            ProjectIntakeRequest(idea="Build a web app", known_stack=["React", "FastAPI"])
        )
        stack_qs_no = [q for q in resp_no_stack.questions if q.category == QuestionCategory.TECH_STACK]
        stack_qs_with = [q for q in resp_with_stack.questions if q.category == QuestionCategory.TECH_STACK]
        self.assertGreater(len(stack_qs_no), 0)
        self.assertEqual(len(stack_qs_with), 0)

    def test_signal_keywords_trigger_questions(self):
        """Signal keywords (payments, uploads) should trigger relevant questions."""
        resp = analyze_project_intake(
            ProjectIntakeRequest(idea="Web app with Stripe payment and file upload photos")
        )
        categories = {q.category for q in resp.questions}
        self.assertIn(QuestionCategory.PAYMENTS_BILLING, categories)
        self.assertIn(QuestionCategory.FILES_UPLOADS, categories)

    def test_response_serializes_to_json(self):
        """Pydantic model should serialize cleanly."""
        resp = analyze_project_intake(ProjectIntakeRequest(idea="A simple web app"))
        data = resp.model_dump()
        self.assertIn("mode", data)
        self.assertIn("questions", data)
        self.assertIn("ready_to_plan", data)
        self.assertIn("confidence", data)
        self.assertIn("summary", data)
        for q in data["questions"]:
            self.assertIn("id", q)
            self.assertIn("category", q)
            self.assertIn("priority", q)
            self.assertIn("question", q)
            self.assertIn("why_it_matters", q)

    def test_question_ids_are_unique(self):
        """Every question should have a unique ID."""
        resp = analyze_project_intake(ProjectIntakeRequest(idea="Build a React dashboard with auth"))
        ids = [q.id for q in resp.questions]
        self.assertEqual(len(ids), len(set(ids)))


class TestReadinessHeuristic(unittest.TestCase):
    """Test the ready_to_plan / confidence logic."""

    def test_very_detailed_idea_is_ready(self):
        """An extremely detailed idea with many signals should be ready to plan."""
        idea = (
            "Build an MVP React web dashboard with JWT authentication and role-based access control, "
            "PostgreSQL database for data storage, user file uploads with S3-compatible storage, "
            "responsive Tailwind CSS design with dark theme support, "
            "deployed locally first then to Docker containers on a VPS with CI/CD pipeline."
        )
        resp = analyze_project_intake(
            ProjectIntakeRequest(idea=idea, known_stack=["React", "FastAPI", "PostgreSQL"])
        )
        self.assertTrue(resp.ready_to_plan)
        self.assertEqual(resp.confidence, "high")

    def test_existing_project_never_ready(self):
        """Existing projects are never immediately ready (need answers)."""
        resp = analyze_project_intake(
            ProjectIntakeRequest(
                idea="I already have a React app with auth and PostgreSQL deployed on AWS",
                mode=ProjectIntakeMode.EXISTING_PROJECT,
                known_stack=["React", "FastAPI"],
            )
        )
        self.assertFalse(resp.ready_to_plan)
        self.assertEqual(resp.confidence, "low")


class TestMissingInformation(unittest.TestCase):
    """Missing information field correctness."""

    def test_vague_idea_has_missing_info(self):
        resp = analyze_project_intake(ProjectIntakeRequest(idea="Сделай приложение"))
        self.assertGreater(len(resp.missing_information), 0)

    def test_specific_idea_fewer_missing(self):
        idea = "React web app with JWT auth and PostgreSQL database for MVP"
        resp = analyze_project_intake(ProjectIntakeRequest(idea=idea))
        # Should not have "Target platform not specified"
        self.assertNotIn("Target platform not specified", resp.missing_information)
        self.assertNotIn("Auth requirements not mentioned", resp.missing_information)
        self.assertNotIn("Database/storage requirements not mentioned", resp.missing_information)


class TestProjectBriefDraft(unittest.TestCase):
    """Deterministic project brief draft generation."""

    def test_vague_idea_produces_missing_sections_and_open_questions(self):
        resp = draft_project_brief(ProjectBriefDraftRequest(idea="Сделай приложение"))

        self.assertIsInstance(resp, ProjectBriefDraftResponse)
        self.assertFalse(resp.ready_to_plan)
        self.assertEqual(resp.readiness, "needs_clarification")
        self.assertGreater(len(resp.open_questions), 0)
        self.assertLessEqual(len(resp.open_questions), MAX_TOTAL)
        self.assertTrue(any(section.status == ProjectBriefSectionStatus.MISSING for section in resp.sections))
        self.assertIn("## Open questions", resp.brief_markdown)

    def test_detailed_idea_produces_useful_sections(self):
        idea = (
            "Build an MVP React web dashboard with JWT auth, PostgreSQL database, "
            "Tailwind responsive UI, Docker deployment, and pytest CI checks."
        )
        resp = draft_project_brief(
            ProjectBriefDraftRequest(
                idea=idea,
                known_stack=["React", "FastAPI", "PostgreSQL"],
            )
        )

        titles = {section.title for section in resp.sections}
        self.assertIn("Product idea", titles)
        self.assertIn("Tech stack", titles)
        self.assertIn("Quality/testing", titles)
        self.assertTrue(resp.ready_to_plan)
        self.assertIn("React, FastAPI, PostgreSQL", resp.brief_markdown)
        self.assertIn("Project Brief Draft", resp.brief_markdown)

    def test_existing_project_wording_sets_existing_mode(self):
        resp = draft_project_brief(
            ProjectBriefDraftRequest(
                idea="I already have a Django project and need to continue development",
                known_stack=["Django", "PostgreSQL"],
            )
        )

        self.assertEqual(resp.mode, ProjectIntakeMode.EXISTING_PROJECT)
        self.assertFalse(resp.ready_to_plan)
        self.assertEqual(resp.readiness, "needs_clarification")

    def test_response_serializes(self):
        resp = draft_project_brief(ProjectBriefDraftRequest(idea="React web app with JWT auth and PostgreSQL database for MVP"))
        data = resp.model_dump()

        self.assertIn("brief_markdown", data)
        self.assertIn("sections", data)
        self.assertIn("open_questions", data)
        self.assertIn("ready_to_plan", data)

    def test_brief_draft_endpoint_returns_structured_response(self):
        from src.api import routes

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(routes.post_project_intake_brief_draft(
            ProjectBriefDraftRequest(idea="React web app with JWT auth and PostgreSQL database for MVP")
        ))

        self.assertIsInstance(resp, ProjectBriefDraftResponse)
        self.assertIn("# Project Brief Draft", resp.brief_markdown)
        self.assertLessEqual(len(resp.open_questions), MAX_TOTAL)


class TestDevelopmentPlanPreview(unittest.TestCase):
    """Deterministic development plan preview generation."""

    def test_vague_new_project_not_ready_and_has_required_inputs(self):
        resp = draft_development_plan(DevelopmentPlanPreviewRequest(idea="Сделай приложение"))

        self.assertIsInstance(resp, DevelopmentPlanPreviewResponse)
        self.assertFalse(resp.ready_to_start)
        self.assertGreater(len(resp.required_inputs), 0)
        self.assertTrue(any(phase.status != DevelopmentPlanPhaseStatus.READY for phase in resp.phases))
        self.assertIn("product-manager", resp.recommended_agent_ids)

    def test_detailed_web_app_returns_meaningful_phases(self):
        idea = (
            "Build an MVP React web dashboard for admins and regular users with JWT auth, "
            "PostgreSQL database, Tailwind responsive UI, Docker deployment, and pytest CI checks."
        )
        resp = draft_development_plan(
            DevelopmentPlanPreviewRequest(
                idea=idea,
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins and regular users"},
            )
        )

        phase_ids = {phase.id for phase in resp.phases}
        self.assertTrue(resp.ready_to_start)
        self.assertIn("architecture-design", phase_ids)
        self.assertIn("backend-api", phase_ids)
        self.assertIn("frontend-ui", phase_ids)
        self.assertIn("auth-rbac", phase_ids)
        self.assertIn("testing-qa", phase_ids)
        self.assertIn("deployment", phase_ids)
        self.assertIn("documentation-final-report", phase_ids)
        self.assertIn("frontend-developer", resp.recommended_agent_ids)
        self.assertIn("backend-developer", resp.recommended_agent_ids)

    def test_existing_project_wording_returns_existing_project_phases(self):
        resp = draft_development_plan(
            DevelopmentPlanPreviewRequest(
                idea="I already have a Django project and need to continue development of billing",
                existing_project_attached=True,
                known_stack=["Django", "PostgreSQL"],
                user_goal="Continue billing feature development",
            )
        )

        phase_ids = {phase.id for phase in resp.phases}
        self.assertEqual(resp.mode, ProjectIntakeMode.EXISTING_PROJECT)
        self.assertIn("project-inventory", phase_ids)
        self.assertIn("stack-profile-detection", phase_ids)
        self.assertIn("safe-command-validation", phase_ids)
        self.assertIn("existing-code-risk-audit", phase_ids)
        self.assertIn("context-gathering", phase_ids)
        self.assertIn("patch-proposal-review", phase_ids)
        self.assertIn("manual-apply", phase_ids)
        self.assertIn("test-fix-loop", phase_ids)
        self.assertIn("final-verification-report", phase_ids)
        self.assertIn("qa-expert", resp.recommended_agent_ids)

    def test_response_serializes(self):
        resp = draft_development_plan(
            DevelopmentPlanPreviewRequest(idea="React web app with JWT auth and PostgreSQL database for MVP")
        )
        data = resp.model_dump()

        self.assertIn("phases", data)
        self.assertIn("required_inputs", data)
        self.assertIn("recommended_agent_ids", data)
        self.assertIn("source_readiness", data)

    def test_plan_preview_endpoint_returns_structured_response(self):
        from src.api import routes

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(routes.post_project_intake_plan_preview(
            DevelopmentPlanPreviewRequest(idea="React web app with JWT auth and PostgreSQL database for MVP")
        ))

        self.assertIsInstance(resp, DevelopmentPlanPreviewResponse)
        self.assertGreater(len(resp.phases), 0)
        self.assertIn("testing-qa", {phase.id for phase in resp.phases})

    def test_intake_module_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(project_intake_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)


class TestSourceOfTruthPreviewBuilder(unittest.TestCase):
    """Deterministic source-of-truth preview generation from intake/brief/plan."""

    def test_new_idea_builds_source_of_truth_preview(self):
        resp = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea=(
                    "Build an MVP React web dashboard for sales managers with JWT auth, "
                    "PostgreSQL database, Tailwind UI, Docker deployment, and pytest checks."
                ),
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Sales managers"},
            )
        )

        self.assertIsInstance(resp, SourceOfTruthPreviewResponse)
        self.assertEqual(resp.source_of_truth.source_type, ProjectInputSourceType.NEW_IDEA)
        self.assertIn("Sales managers", resp.source_of_truth.target_users)
        self.assertTrue(any(req.priority == RequirementPriority.MUST for req in resp.source_of_truth.requirements))
        self.assertGreater(len(resp.source_of_truth.acceptance_criteria), 0)
        self.assertGreater(len(resp.source_of_truth.anti_drift_rules), 0)
        self.assertEqual(resp.coverage_matrix.unlinked_plan_item_ids, [])

    def test_existing_project_builds_preservation_constraints(self):
        resp = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="I already have an existing Django project and need to continue billing development",
                existing_project_attached=True,
                known_stack=["Django", "PostgreSQL"],
                user_goal="Finish billing feature safely",
            )
        )

        self.assertEqual(resp.source_of_truth.source_type, ProjectInputSourceType.EXISTING_PROJECT)
        constraint_text = " ".join(item.title.lower() for item in resp.source_of_truth.constraints)
        open_questions = " ".join(resp.source_of_truth.open_questions).lower()
        self.assertIn("preserve existing stack", constraint_text)
        self.assertIn("secrets", constraint_text)
        self.assertIn("incremental", constraint_text)
        self.assertIn("where are the project files", open_questions)
        self.assertIn("what already works", open_questions)
        self.assertIn("dev/build commands", open_questions)

    def test_document_like_text_sets_client_spec_or_proposal_source_type(self):
        spec_resp = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="ТЗ: обязательно сделать CRM для менеджеров с ролями и отчетами.",
                answers={"target_users": "Managers"},
            )
        )
        proposal_resp = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="КП: коммерческое предложение на разработку личного кабинета.",
                answers={"target_users": "Customers"},
            )
        )

        self.assertEqual(spec_resp.source_of_truth.source_type, ProjectInputSourceType.CLIENT_SPEC)
        self.assertEqual(proposal_resp.source_of_truth.source_type, ProjectInputSourceType.COMMERCIAL_PROPOSAL)

    def test_vague_idea_has_validation_gaps_and_open_questions(self):
        resp = build_source_of_truth_from_intake(SourceOfTruthPreviewRequest(idea="Сделай приложение"))

        self.assertFalse(resp.validation.valid)
        self.assertGreater(len(resp.validation.errors), 0)
        self.assertGreater(len(resp.source_of_truth.open_questions), 0)
        self.assertFalse(resp.ready_to_plan)

    def test_coverage_matrix_links_generated_plan_phases(self):
        resp = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="Build an MVP React web app for admins with JWT auth and PostgreSQL database.",
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        )

        self.assertGreater(len(resp.coverage_matrix.items), 0)
        self.assertEqual(resp.coverage_matrix.missing_requirement_ids, [])
        self.assertEqual(resp.coverage_matrix.coverage_score, 1.0)

    def test_source_of_truth_endpoint_returns_structured_response(self):
        from src.api import routes

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(routes.post_project_intake_source_of_truth_preview(
            SourceOfTruthPreviewRequest(
                idea="React web app for admins with JWT auth and PostgreSQL database for MVP",
                answers={"target_users": "Admins"},
            )
        ))

        self.assertIsInstance(resp, SourceOfTruthPreviewResponse)
        data = resp.model_dump()
        self.assertIn("source_of_truth", data)
        self.assertIn("validation", data)
        self.assertIn("coverage_matrix", data)

    def test_source_builder_path_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(project_intake_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)


class TestRequirementCoveragePreview(unittest.TestCase):
    """Deterministic requirement coverage preview from source of truth and plan."""

    def test_coverage_preview_endpoint_returns_structured_matrix(self):
        from src.api import routes

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        resp = loop.run_until_complete(routes.post_project_intake_coverage_preview(
            RequirementCoveragePreviewRequest(
                idea="Build an MVP React app for admins with JWT auth and PostgreSQL database.",
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        ))

        self.assertIsInstance(resp, RequirementCoveragePreviewResponse)
        self.assertGreater(resp.summary.requirements_total, 0)
        self.assertGreater(len(resp.items), 0)
        self.assertIn("Requirement Coverage Preview", resp.title)

    def test_new_idea_links_requirements_to_plan_phases(self):
        resp = build_requirement_coverage_from_plan(
            RequirementCoveragePreviewRequest(
                idea=(
                    "Build an MVP React web dashboard for sales managers with JWT auth, "
                    "PostgreSQL database, Tailwind UI, Docker deployment, and pytest checks."
                ),
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Sales managers"},
            )
        )

        self.assertGreater(resp.summary.covered_requirements, 0)
        self.assertEqual(resp.summary.missing_requirements, 0)
        self.assertEqual(resp.summary.unlinked_plan_phases, 0)
        self.assertTrue(all(item.linked_plan_phases for item in resp.items))

    def test_missing_mandatory_requirement_is_flagged(self):
        source_preview = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="Build a React app for admins with JWT auth and PostgreSQL database.",
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        )
        source = source_preview.source_of_truth
        source.requirements.append(ProjectRequirementContract(
            id="REQ-MISSING",
            title="Offline export",
            description="The app must export reports offline.",
            priority=RequirementPriority.MUST,
            status=RequirementStatus.CONFIRMED,
        ))

        resp = build_requirement_coverage_from_plan(
            RequirementCoveragePreviewRequest(
                idea="Build a React app for admins with JWT auth and PostgreSQL database.",
                source_of_truth=source,
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        )

        missing = [item for item in resp.items if item.requirement_id == "REQ-MISSING"]
        self.assertEqual(missing[0].coverage_status, RequirementCoveragePreviewStatus.MISSING)
        self.assertEqual(missing[0].drift_risk.value, "high")
        self.assertIn("REQ-MISSING", " ".join(resp.drift_risks))

    def test_unlinked_plan_phase_is_flagged_as_drift_risk(self):
        source_preview = build_source_of_truth_from_intake(
            SourceOfTruthPreviewRequest(
                idea="Build a React app for admins with JWT auth and PostgreSQL database.",
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        )
        custom_source = ProjectSourceOfTruthContract(
            **{
                **source_preview.source_of_truth.model_dump(),
                "requirements": [
                    {
                        **source_preview.source_of_truth.requirements[0].model_dump(),
                        "source_refs": ["not-a-phase"],
                        "tags": ["not-a-phase"],
                    }
                ],
                "acceptance_criteria": source_preview.source_of_truth.acceptance_criteria[:1],
            }
        )

        resp = build_requirement_coverage_from_plan(
            RequirementCoveragePreviewRequest(
                idea="Build a React app for admins with JWT auth and PostgreSQL database.",
                source_of_truth=custom_source,
                known_stack=["React", "FastAPI", "PostgreSQL"],
                answers={"target_users": "Admins"},
            )
        )

        self.assertGreater(resp.summary.unlinked_plan_phases, 0)
        self.assertTrue(any(item.risk_level.value in {"medium", "high", "critical"} for item in resp.unlinked_plan_phases))

    def test_existing_project_constraints_produce_preservation_coverage_checks(self):
        resp = build_requirement_coverage_from_plan(
            RequirementCoveragePreviewRequest(
                idea="I already have an existing Django project and need to continue billing development",
                existing_project_attached=True,
                known_stack=["Django", "PostgreSQL"],
                user_goal="Finish billing feature safely",
            )
        )

        titles = " ".join(item.title.lower() for item in resp.items)
        risks = " ".join(resp.drift_risks).lower()
        self.assertIn("project inventory", titles)
        self.assertIn("patch proposal/review", titles)
        self.assertIn("manual apply", titles)
        self.assertNotIn("provider", risks)

    def test_coverage_response_serializes(self):
        resp = build_requirement_coverage_from_plan(
            RequirementCoveragePreviewRequest(
                idea="React web app for admins with JWT auth and PostgreSQL database for MVP",
                answers={"target_users": "Admins"},
            )
        )
        data = resp.model_dump()

        self.assertIn("summary", data)
        self.assertIn("items", data)
        self.assertIn("unlinked_plan_phases", data)
        self.assertIn("drift_risks", data)

    def test_coverage_builder_path_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(project_intake_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)


class TestBuildConfirmedPlanRunPreview(unittest.TestCase):
    """Full run-step preview — maps plan phases to future run steps."""

    def test_returns_structured_response(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Build a React web dashboard with auth")
        )
        self.assertIsInstance(resp, ConfirmedPlanRunPreviewResponse)
        self.assertIsInstance(resp.title, str)
        self.assertIsInstance(resp.ready_to_create_run, bool)
        self.assertIsInstance(resp.summary, str)
        self.assertIsInstance(resp.steps, list)
        self.assertGreater(len(resp.steps), 0)
        for step in resp.steps:
            self.assertIsInstance(step, ConfirmedRunStepPreview)
            self.assertTrue(step.id.startswith("rs-"))

    def test_vague_idea_not_ready(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Хочу что-то")
        )
        self.assertFalse(resp.ready_to_create_run)
        self.assertGreater(len(resp.blocking_issues) + len(resp.warnings), 0)

    def test_missing_mandatory_requirements_block_readiness(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Some vague project idea")
        )
        # A vague idea has missing mandatory reqs and/or SoT gaps → not ready
        self.assertFalse(resp.ready_to_create_run)

    def test_steps_linked_to_requirement_ids(self):
        idea = (
            "Build a React web dashboard with JWT auth, PostgreSQL database, "
            "file uploads, Stripe billing, Tailwind design, Docker deployment. MVP."
        )
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea=idea, known_stack=["React", "FastAPI"])
        )
        linked = [s for s in resp.steps if s.required_requirement_ids]
        # At least some steps should be linked to requirements
        self.assertGreater(len(linked), 0)

    def test_existing_project_mode_steps(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(
                idea="Доработать существующий Django проект, часть функций уже готова",
                mode=ProjectIntakeMode.EXISTING_PROJECT,
            )
        )
        self.assertFalse(resp.ready_to_create_run)
        self.assertGreater(len(resp.steps), 0)
        # Existing project mode always not ready (needs answers first)
        titles = " ".join(s.title.lower() for s in resp.steps)
        # Expect inventory/audit/context-style steps
        has_context_step = any(
            kw in titles for kw in ["inventory", "audit", "context", "scan", "review", "analysis"]
        )
        self.assertTrue(has_context_step, f"Expected context/inventory step in: {titles}")

    def test_step_dependencies_use_rs_prefix(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Build a React web app with auth and database")
        )
        for step in resp.steps:
            for dep in step.depends_on:
                self.assertTrue(dep.startswith("rs-"), f"Dep {dep} should start with rs-")

    def test_serializes_through_pydantic(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Build a web app")
        )
        data = resp.model_dump()
        self.assertIn("title", data)
        self.assertIn("ready_to_create_run", data)
        self.assertIn("steps", data)
        self.assertIn("blocking_issues", data)
        self.assertIn("warnings", data)
        self.assertIn("source_of_truth_ready", data)
        self.assertIn("coverage_ready", data)
        for step_data in data["steps"]:
            self.assertIn("id", step_data)
            self.assertIn("title", step_data)
            self.assertIn("coverage_status", step_data)
            self.assertIn("drift_risk", step_data)
            self.assertIn("manual_approval_required", step_data)
            self.assertIn("safe_to_prepare", step_data)

    def test_no_db_tool_provider_execution(self):
        """The run-preview builder must not import DB/tool/provider modules."""
        source = inspect.getsource(project_intake_module)
        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)

    def test_safe_to_prepare_and_manual_approval_flags(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(
                idea="Build a React dashboard with auth, deploy to Docker on AWS with CI/CD"
            )
        )
        safe_steps = [s for s in resp.steps if s.safe_to_prepare]
        approval_steps = [s for s in resp.steps if s.manual_approval_required]
        # Should have at least one safe-to-prepare (design/architecture) and
        # potentially approval steps (deploy)
        self.assertGreater(len(safe_steps), 0, "Expected at least one safe-to-prepare step")

    def test_summary_includes_step_count(self):
        resp = build_confirmed_plan_run_preview(
            ConfirmedPlanRunPreviewRequest(idea="Build a web app")
        )
        self.assertIn("run steps", resp.summary)


if __name__ == "__main__":
    unittest.main()
