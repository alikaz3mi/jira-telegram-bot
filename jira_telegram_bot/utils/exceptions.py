"""Custom exceptions for the Jira Telegram Bot application."""

from typing import Dict, Any, Optional

from fastapi import HTTPException, status


class CustomException(Exception):
    """Base custom exception class.
    
    Attributes:
        message: The error message
        status_code: HTTP status code
        headers: Optional HTTP headers
    """
    
    def __init__(
        self,
        message: Dict[str, Any],
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Initialize the custom exception.
        
        Args:
            message: The error message as a dictionary
            status_code: HTTP status code
            headers: Optional HTTP headers
        """
        self.message = message
        self.status_code = status_code
        self.headers = headers
        super().__init__(self.message)


class CustomHTTPException(HTTPException):
    """HTTP exception with custom message and headers.
    
    Attributes:
        message: The error message
        status_code: HTTP status code
        headers: Optional HTTP headers
    """
    
    def __init__(
        self,
        status_code: int,
        message: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """Initialize the HTTP exception.
        
        Args:
            status_code: HTTP status code
            message: The error message as a dictionary
            headers: Optional HTTP headers
        """
        self.message = message
        super().__init__(status_code=status_code, detail=message)
        self.headers = headers

    def to_json(self) -> Dict[str, str]:
        """Convert headers to JSON format.
        
        Returns:
            Headers dictionary
        """
        return self.headers if self.headers else {}


class SpreadsheetError(Exception):
    """Exception raised for Google Sheets operations errors."""
    
    def __init__(self, message: str):
        """Initialize the spreadsheet error.
        
        Args:
            message: The error message
        """
        self.message = message
        super().__init__(self.message)


class MetricsProcessingError(Exception):
    """Exception raised for metrics processing errors."""
    
    def __init__(self, message: str):
        """Initialize the metrics processing error.
        
        Args:
            message: The error message
        """
        self.message = message
        super().__init__(self.message)


class DatabaseConnectionError(Exception):
    """Exception raised for database connection errors."""
    
    def __init__(self, message: str):
        """Initialize the database connection error.
        
        Args:
            message: The error message
        """
        self.message = message
        super().__init__(self.message)


class RepositoryError(Exception):
    """Exception raised for repository operation errors."""
    
    def __init__(self, message: str):
        """Initialize the repository error.
        
        Args:
            message: The error message
        """
        self.message = message
        super().__init__(self.message)
