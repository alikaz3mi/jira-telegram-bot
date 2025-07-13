from abc import ABC, abstractmethod
from io import BytesIO

from jira_telegram_bot.entities.current_stories_report import CurrentStoriesReport


class XlsxReportServiceInterface(ABC):
    """Interface for XLSX report generation service."""
    
    @abstractmethod
    async def generate_current_stories_xlsx(self, report: CurrentStoriesReport) -> BytesIO:
        """Generate XLSX file from current stories report.
        
        Args:
            report: The current stories report data
            
        Returns:
            BytesIO containing the XLSX file
        """
        pass
