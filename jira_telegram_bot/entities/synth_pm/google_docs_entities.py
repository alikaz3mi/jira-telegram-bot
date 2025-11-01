"""Entities for Google Docs documentation structure."""
from __future__ import annotations

from enum import Enum
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class DocumentColor(str, Enum):
    """Color codes for document sections based on status."""
    
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    DEFAULT = "DEFAULT"


class DepartmentChip(BaseModel):
    """Represents a department tag/chip in the document."""
    
    name: str = Field(description="Department name")
    color: Optional[str] = Field(default=None, description="Chip color")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class FeatureTableInfo(BaseModel):
    """Information table for feature documentation."""
    
    release_link: str = Field(description="Link to release in PM board")
    feature_link: str = Field(description="Link to feature in Jira")
    departments: List[DepartmentChip] = Field(description="Involved departments")
    reporter_email: str = Field(description="Reporter email to be tagged")
    start_date: str = Field(description="Start date")
    final_delivery_date: str = Field(description="Final delivery date")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class DocumentSection(BaseModel):
    """Base class for document sections."""
    
    heading_level: int = Field(description="Heading level (1-6)")
    title: str = Field(description="Section title")
    content: Optional[str] = Field(default=None, description="Section content")
    assignee_email: Optional[str] = Field(
        default=None,
        description="Email to tag for this section",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class UserStorySection(DocumentSection):
    """User story section of feature documentation."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="یوزر استوری", description="Section title")
    story_content: str = Field(description="User story content")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class AcceptanceCriteriaSection(DocumentSection):
    """Acceptance criteria section of feature documentation."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="معیارهای پذیرش", description="Section title")
    criteria_list: List[str] = Field(description="List of acceptance criteria")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class WireframeSection(DocumentSection):
    """Wireframe section for UI/UX work."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="وایر فریم", description="Section title")
    designer_email: str = Field(description="UI/UX designer email to tag")
    figma_link: Optional[str] = Field(default=None, description="Figma design link")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class FinalDesignSection(DocumentSection):
    """Final design section for UI/UX work."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="طراحی نهایی", description="Section title")
    designer_email: str = Field(description="Designer email to tag")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class ApiListSection(DocumentSection):
    """API list section for backend/AI work."""
    
    heading_level: int = Field(default=2, description="Heading level")
    department: str = Field(description="Department name (Backend/AI)")
    assignee_emails: List[str] = Field(description="Developer emails to tag")
    api_list: Optional[List[str]] = Field(
        default=None,
        description="List of API endpoints",
    )
    
    def __init__(self, **data):
        """Initialize API list section with dynamic title."""
        if 'title' not in data:
            dept = data.get('department', 'بکند')
            if 'AI' in dept or 'ai' in dept.lower():
                data['title'] = 'لیست API های هوش و خروجی آن ها'
            else:
                data['title'] = 'لیست API های بکند و خروجی آنها'
        super().__init__(**data)
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class ExpectedOutputSection(DocumentSection):
    """Expected output section."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="خروجی مد نظر", description="Section title")
    reporter_email: str = Field(description="Reporter email to tag")
    output_description: Optional[str] = Field(
        default=None,
        description="Output description",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class SubtaskInfo(BaseModel):
    """Information about a subtask."""
    
    title: str = Field(description="Subtask title")
    jira_link: str = Field(description="Link to Jira subtask")
    acceptance_criteria: Optional[List[str]] = Field(
        default=None,
        description="Acceptance criteria for this subtask",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class SubtasksSection(DocumentSection):
    """Subtasks section listing all subtasks."""
    
    heading_level: int = Field(default=2, description="Heading level")
    title: str = Field(default="تسک های زیرمجموعه", description="Section title")
    subtasks: List[SubtaskInfo] = Field(description="List of subtasks")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class TableOfContents(BaseModel):
    """Table of contents for the document."""
    
    sections: List[str] = Field(description="List of section titles")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class FeatureDocumentation(BaseModel):
    """Complete feature documentation structure."""
    
    feature_title: str = Field(description="Feature title (Heading 1)")
    table_of_contents: TableOfContents = Field(description="Table of contents")
    feature_info_table: FeatureTableInfo = Field(description="Feature information table")
    user_story: UserStorySection = Field(description="User story section")
    acceptance_criteria: AcceptanceCriteriaSection = Field(
        description="Acceptance criteria",
    )
    wireframe: Optional[WireframeSection] = Field(
        default=None,
        description="Wireframe section (if UI/UX involved)",
    )
    final_design: Optional[FinalDesignSection] = Field(
        default=None,
        description="Final design section (if UI/UX involved)",
    )
    backend_apis: Optional[ApiListSection] = Field(
        default=None,
        description="Backend APIs section (if Backend involved)",
    )
    ai_apis: Optional[ApiListSection] = Field(
        default=None,
        description="AI APIs section (if AI involved)",
    )
    expected_output: ExpectedOutputSection = Field(description="Expected output")
    subtasks: SubtasksSection = Field(description="Subtasks section")
    color_code: DocumentColor = Field(
        default=DocumentColor.DEFAULT,
        description="Color code based on status",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class EpicTab(BaseModel):
    """Represents an Epic tab in Google Docs."""
    
    epic_name: str = Field(description="Epic name")
    tab_id: Optional[str] = Field(default=None, description="Google Docs tab ID")
    features: List[FeatureDocumentation] = Field(
        default_factory=list,
        description="Features in this epic",
    )
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class DocumentHeader(BaseModel):
    """Document header configuration."""
    
    epic_name: str = Field(description="Epic name to show in header")
    alignment: str = Field(default="RIGHT", description="Text alignment")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class DocumentFooter(BaseModel):
    """Document footer configuration."""
    
    show_page_number: bool = Field(default=True, description="Show page number")
    alignment: str = Field(default="CENTER", description="Text alignment")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class DocumentFormatting(BaseModel):
    """Document formatting settings."""
    
    font_family: str = Field(default="Vazirmatn", description="Font family")
    header: DocumentHeader = Field(description="Header configuration")
    footer: DocumentFooter = Field(description="Footer configuration")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class GoogleDocsStructure(BaseModel):
    """Complete Google Docs structure for release documentation."""
    
    document_id: str = Field(description="Google Docs document ID")
    document_url: str = Field(description="Google Docs document URL")
    epic_tabs: List[EpicTab] = Field(description="Epic tabs in the document")
    formatting: DocumentFormatting = Field(description="Document formatting settings")
    
    class Config:
        """Pydantic configuration."""
        frozen = True


class DocumentationTaskInfo(BaseModel):
    """Information about documentation subtask for each department."""
    
    department: str = Field(description="Department name")
    assignee_email: str = Field(description="Assignee email")
    estimated_hours: int = Field(default=2, description="Estimated hours (default: 2)")
    task_title: str = Field(description="Documentation task title")
    parent_issue_key: str = Field(description="Parent feature issue key")
    
    class Config:
        """Pydantic configuration."""
        frozen = True
