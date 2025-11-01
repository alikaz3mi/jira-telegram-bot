"""Use case for generating feature documentation in Google Docs."""
from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.release_notes import ReleaseNoteEntity
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    AcceptanceCriteriaSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import ApiListSection
from jira_telegram_bot.entities.synth_pm.google_docs_entities import DepartmentChip
from jira_telegram_bot.entities.synth_pm.google_docs_entities import DocumentColor
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentFooter,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentFormatting,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    DocumentHeader,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    ExpectedOutputSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureDocumentation,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FeatureTableInfo,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    FinalDesignSection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import SubtaskInfo
from jira_telegram_bot.entities.synth_pm.google_docs_entities import SubtasksSection
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    TableOfContents,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    UserStorySection,
)
from jira_telegram_bot.entities.synth_pm.google_docs_entities import (
    WireframeSection,
)
from jira_telegram_bot.entities.synth_pm.pm_board_features import (
    SynthPMFeatureEntity,
)
from jira_telegram_bot.use_cases.interfaces.google_docs_repository_interface import (
    GoogleDocsRepositoryInterface,
)
from jira_telegram_bot.use_cases.interfaces.user_config_interface import (
    UserConfigInterface,
)


class DocumentationGenerationUseCase:
    """Use case for generating and managing feature documentation in Google Docs."""
    
    def __init__(
        self,
        google_docs_repository: GoogleDocsRepositoryInterface,
        user_config: UserConfigInterface,
    ):
        """Initialize documentation generation use case.
        
        Args:
            google_docs_repository: Google Docs repository interface
            user_config: User configuration interface
        """
        self.google_docs_repository = google_docs_repository
        self.user_config = user_config
    
    async def create_feature_documentation(
        self,
        document_id: str,
        epic_name: str,
        feature: SynthPMFeatureEntity,
        release_note: ReleaseNoteEntity,
        subtasks: List[Dict],
    ) -> bool:
        """Create complete feature documentation in Google Docs.
        
        Args:
            document_id: Google Docs document ID
            epic_name: Epic name for organizing docs
            feature: Feature entity with task information
            release_note: Release note entity with additional info
            subtasks: List of subtasks for this feature
            
        Returns:
            True if successful, False otherwise
        """
        try:
            epic_tab_id = await self.google_docs_repository.get_or_create_epic_tab(
                document_id,
                epic_name,
            )
            
            feature_doc = await self._build_feature_documentation(
                feature,
                release_note,
                subtasks,
            )
            
            subtab_id, was_created = await self.google_docs_repository.get_or_create_feature_subtab(
                document_id,
                epic_tab_id,
                feature_doc,
            )
            
            if subtab_id:
                if was_created:
                    LOGGER.info(f"Created new feature documentation: {feature.task_title}")
                else:
                    LOGGER.info(f"Updated existing feature documentation: {feature.task_title}")
                
                await self._apply_status_color_coding(
                    document_id,
                    epic_tab_id,
                    feature,
                )
                return True
            
            return False
            
        except Exception as e:
            LOGGER.error(f"Failed to create feature documentation: {e}")
            return False
    
    async def _build_feature_documentation(
        self,
        feature: SynthPMFeatureEntity,
        release_note: ReleaseNoteEntity,
        subtasks: List[Dict],
    ) -> FeatureDocumentation:
        """Build complete feature documentation structure.
        
        Args:
            feature: Feature entity
            release_note: Release note entity
            subtasks: List of subtasks
            
        Returns:
            FeatureDocumentation entity
        """
        feature_info_table = self._build_feature_info_table(feature, release_note)
        
        toc = self._build_table_of_contents(feature)
        
        user_story = UserStorySection(
            story_content=feature.description or "توضیحات در دسترس نیست",
        )
        
        acceptance_criteria = self._build_acceptance_criteria(feature)
        
        wireframe = self._build_wireframe_section(feature)
        
        final_design = self._build_final_design_section(feature)
        
        backend_apis = self._build_backend_apis_section(feature)
        
        ai_apis = self._build_ai_apis_section(feature)
        
        expected_output = self._build_expected_output_section(feature, release_note)
        
        subtasks_section = self._build_subtasks_section(feature, subtasks)
        
        color_code = self._determine_color_code(feature)
        
        return FeatureDocumentation(
            feature_title=feature.task_title,
            table_of_contents=toc,
            feature_info_table=feature_info_table,
            user_story=user_story,
            acceptance_criteria=acceptance_criteria,
            wireframe=wireframe,
            final_design=final_design,
            backend_apis=backend_apis,
            ai_apis=ai_apis,
            expected_output=expected_output,
            subtasks=subtasks_section,
            color_code=color_code,
        )
    
    def _build_feature_info_table(
        self,
        feature: SynthPMFeatureEntity,
        release_note: ReleaseNoteEntity,
    ) -> FeatureTableInfo:
        """Build feature information table.
        
        Args:
            feature: Feature entity
            release_note: Release note entity
            
        Returns:
            FeatureTableInfo entity
        """
        departments = self._extract_departments(feature)
        
        reporter_email = self._get_reporter_email(release_note)
        
        pm_board_link = self._get_jira_link(feature.jira_issue_key)
        dev_board_link = self._get_jira_link(feature.developer_board_issue_key)
        
        return FeatureTableInfo(
            release_link=pm_board_link,
            feature_link=dev_board_link,
            departments=departments,
            reporter_email=reporter_email,
            start_date=release_note.start_date or "نامشخص",
            final_delivery_date=release_note.beta_delivery or "نامشخص",
        )
    
    def _extract_departments(
        self,
        feature: SynthPMFeatureEntity,
    ) -> List[DepartmentChip]:
        """Extract involved departments from feature.
        
        Args:
            feature: Feature entity
            
        Returns:
            List of DepartmentChip entities
        """
        departments = []
        
        department_fields = {
            "frontend": feature.frontend,
            "backend": feature.backend,
            "UI/UX": feature.ui_ux,
            "AI": feature.ai,
            "DevOps": feature.devops,
        }
        
        for dept_name, dept_value in department_fields.items():
            if dept_value and dept_value != "0" and dept_value != "":
                departments.append(DepartmentChip(name=dept_name))
        
        return departments
    
    def _get_reporter_email(self, release_note: ReleaseNoteEntity) -> str:
        """Get reporter email from release note or user config.
        
        Args:
            release_note: Release note entity
            
        Returns:
            Reporter email address
        """
        return "reporter@example.com"
    
    def _get_jira_link(self, issue_key: Optional[str]) -> str:
        """Get Jira issue link.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            Jira issue URL
        """
        if not issue_key:
            return "#"
        return f"https://jira.example.com/browse/{issue_key}"
    
    def _build_table_of_contents(
        self,
        feature: SynthPMFeatureEntity,
    ) -> TableOfContents:
        """Build table of contents based on feature.
        
        Args:
            feature: Feature entity
            
        Returns:
            TableOfContents entity
        """
        sections = [
            "یوزر استوری",
            "معیارهای پذیرش",
        ]
        
        if self._has_ui_ux(feature):
            sections.extend(["وایر فریم", "طراحی نهایی"])
        
        if self._has_backend(feature):
            sections.append("لیست API های بکند و خروجی آنها")
        
        if self._has_ai(feature):
            sections.append("لیست API های هوش و خروجی آن ها")
        
        sections.extend(["خروجی مد نظر", "تسک های زیرمجموعه"])
        
        return TableOfContents(sections=sections)
    
    def _build_acceptance_criteria(
        self,
        feature: SynthPMFeatureEntity,
    ) -> AcceptanceCriteriaSection:
        """Build acceptance criteria section.
        
        Args:
            feature: Feature entity
            
        Returns:
            AcceptanceCriteriaSection entity
        """
        criteria_list = []
        
        if feature.acceptance_criteria:
            criteria_list = feature.acceptance_criteria.split("\n")
        else:
            criteria_list = ["معیارهای پذیرش باید توسط تیم تکمیل شوند"]
        
        return AcceptanceCriteriaSection(criteria_list=criteria_list)
    
    def _build_wireframe_section(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[WireframeSection]:
        """Build wireframe section if UI/UX is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            WireframeSection if UI/UX involved, None otherwise
        """
        if not self._has_ui_ux(feature):
            return None
        
        designer_email = self._get_assignee_email_for_department(feature, "UI/UX")
        
        return WireframeSection(
            designer_email=designer_email,
        )
    
    def _build_final_design_section(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[FinalDesignSection]:
        """Build final design section if UI/UX is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            FinalDesignSection if UI/UX involved, None otherwise
        """
        if not self._has_ui_ux(feature):
            return None
        
        designer_email = self._get_assignee_email_for_department(feature, "UI/UX")
        
        return FinalDesignSection(
            designer_email=designer_email,
        )
    
    def _build_backend_apis_section(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[ApiListSection]:
        """Build backend APIs section if Backend is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            ApiListSection if Backend involved, None otherwise
        """
        if not self._has_backend(feature):
            return None
        
        assignee_emails = self._get_all_assignee_emails_for_department(
            feature,
            "Backend",
        )
        
        return ApiListSection(
            department="Backend",
            assignee_emails=assignee_emails,
        )
    
    def _build_ai_apis_section(
        self,
        feature: SynthPMFeatureEntity,
    ) -> Optional[ApiListSection]:
        """Build AI APIs section if AI is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            ApiListSection if AI involved, None otherwise
        """
        if not self._has_ai(feature):
            return None
        
        assignee_emails = self._get_all_assignee_emails_for_department(feature, "AI")
        
        return ApiListSection(
            department="AI",
            assignee_emails=assignee_emails,
        )
    
    def _build_expected_output_section(
        self,
        feature: SynthPMFeatureEntity,
        release_note: ReleaseNoteEntity,
    ) -> ExpectedOutputSection:
        """Build expected output section.
        
        Args:
            feature: Feature entity
            release_note: Release note entity
            
        Returns:
            ExpectedOutputSection entity
        """
        reporter_email = self._get_reporter_email(release_note)
        
        return ExpectedOutputSection(
            reporter_email=reporter_email,
            output_description=feature.po_notes,
        )
    
    def _build_subtasks_section(
        self,
        feature: SynthPMFeatureEntity,
        subtasks: List[Dict],
    ) -> SubtasksSection:
        """Build subtasks section.
        
        Args:
            feature: Feature entity
            subtasks: List of subtask dictionaries
            
        Returns:
            SubtasksSection entity
        """
        subtask_infos = []
        
        for subtask in subtasks:
            subtask_info = SubtaskInfo(
                title=subtask.get("title", "Untitled"),
                jira_link=self._get_jira_link(subtask.get("key")),
                acceptance_criteria=subtask.get("acceptance_criteria", []),
            )
            subtask_infos.append(subtask_info)
        
        return SubtasksSection(subtasks=subtask_infos)
    
    def _determine_color_code(self, feature: SynthPMFeatureEntity) -> DocumentColor:
        """Determine color code based on feature status.
        
        Args:
            feature: Feature entity
            
        Returns:
            DocumentColor enum value
        """
        status = feature.status
        
        if not status:
            return DocumentColor.DEFAULT
        
        status_lower = status.lower()
        
        if "done" in status_lower or "completed" in status_lower:
            return DocumentColor.GREEN
        elif "in progress" in status_lower or "development" in status_lower:
            return DocumentColor.RED
        elif "documented" in status_lower or "ready" in status_lower:
            return DocumentColor.YELLOW
        
        return DocumentColor.DEFAULT
    
    async def _apply_status_color_coding(
        self,
        document_id: str,
        epic_tab_id: str,
        feature: SynthPMFeatureEntity,
    ):
        """Apply color coding to feature based on status.
        
        Args:
            document_id: Google Docs document ID
            epic_tab_id: Epic tab ID
            feature: Feature entity
        """
        color_code = self._determine_color_code(feature)
        
        if color_code != DocumentColor.DEFAULT:
            await self.google_docs_repository.set_tab_color(
                document_id,
                epic_tab_id,
                color_code.value,
            )
    
    def _has_ui_ux(self, feature: SynthPMFeatureEntity) -> bool:
        """Check if UI/UX department is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            True if UI/UX involved, False otherwise
        """
        return bool(feature.ui_ux and feature.ui_ux != "0")
    
    def _has_backend(self, feature: SynthPMFeatureEntity) -> bool:
        """Check if Backend department is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            True if Backend involved, False otherwise
        """
        return bool(feature.backend and feature.backend != "0")
    
    def _has_ai(self, feature: SynthPMFeatureEntity) -> bool:
        """Check if AI department is involved.
        
        Args:
            feature: Feature entity
            
        Returns:
            True if AI involved, False otherwise
        """
        return bool(feature.ai and feature.ai != "0")
    
    def _get_assignee_email_for_department(
        self,
        feature: SynthPMFeatureEntity,
        department: str,
    ) -> str:
        """Get assignee email for specific department.
        
        Args:
            feature: Feature entity
            department: Department name
            
        Returns:
            Assignee email address
        """
        return f"{department.lower()}@example.com"
    
    def _get_all_assignee_emails_for_department(
        self,
        feature: SynthPMFeatureEntity,
        department: str,
    ) -> List[str]:
        """Get all assignee emails for specific department.
        
        Args:
            feature: Feature entity
            department: Department name
            
        Returns:
            List of assignee email addresses
        """
        return [f"{department.lower()}@example.com"]
    
    async def apply_document_formatting(
        self,
        document_id: str,
        epic_name: str,
    ) -> bool:
        """Apply standard formatting to document.
        
        Args:
            document_id: Google Docs document ID
            epic_name: Epic name for header
            
        Returns:
            True if successful, False otherwise
        """
        try:
            formatting = DocumentFormatting(
                font_family="Vazirmatn",
                header=DocumentHeader(epic_name=epic_name, alignment="RIGHT"),
                footer=DocumentFooter(show_page_number=True, alignment="CENTER"),
            )
            
            return await self.google_docs_repository.apply_document_formatting(
                document_id,
                formatting,
            )
            
        except Exception as e:
            LOGGER.error(f"Failed to apply document formatting: {e}")
            return False
