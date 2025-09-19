"""ORMD Front-Matter Schema Definition

This module defines the official YAML front-matter schema for ORMD 0.1 documents.
Based on the front-matter plan and design philosophy, all metadata should be in
the front-matter YAML block instead of using custom +++meta syntax.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import re
from enum import Enum


class DocumentStatus(Enum):
    """Document status values"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PermissionMode(Enum):
    """Permission mode values"""
    DRAFT = "draft"
    PUBLISHED = "published"
    PRIVATE = "private"


@dataclass
class Author:
    """Author information"""
    id: str
    display: str
    email: Optional[str] = None
    affiliation: Optional[str] = None
    orcid: Optional[str] = None


@dataclass
class Link:
    """Semantic link definition"""
    id: str
    rel: str
    to: str


@dataclass
class Permissions:
    """Document permissions"""
    mode: str = "draft"
    editable: bool = True
    signed: bool = False


@dataclass
class Dates:
    """Document timestamp information"""
    created: Optional[str] = None
    modified: Optional[str] = None


@dataclass
class Metrics:
    """Document metrics"""
    word_count: Optional[int] = None
    reading_time: Optional[str] = None


@dataclass
class Lineage:
    """Context lineage information"""
    source: Optional[str] = None
    parent_docs: Optional[List[str]] = field(default_factory=list)


@dataclass
class Resolution:
    """Context resolution information"""
    confidence: Optional[str] = None


@dataclass
class Context:
    """Context block for conversation lineage and uncertainty"""
    lineage: Optional[Lineage] = None
    resolution: Optional[Resolution] = None


@dataclass
class ORMDFrontMatter:
    """Complete ORMD front-matter schema for Phase 1"""
    # Required fields
    title: str
    authors: List[Union[Author, Dict[str, Any]]]
    links: List[Union[Link, Dict[str, Any]]]
    
    # Optional organized metadata (replaces +++meta blocks)
    dates: Optional[Dates] = None
    metrics: Optional[Metrics] = None
    permissions: Optional[Permissions] = None
    context: Optional[Context] = None
    
    # Optional simple fields
    version: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    license: Optional[str] = None
    keywords: Optional[List[str]] = None


class FrontMatterValidator:
    """Validates ORMD front-matter against the schema"""
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, front_matter: Dict[str, Any]) -> bool:
        """Validate front-matter dictionary against schema"""
        self.errors = []
        
        if not isinstance(front_matter, dict):
            self.errors.append("Front-matter must be a YAML object/dictionary")
            return False
        
        # Validate required fields
        if not self._validate_required_fields(front_matter):
            return False
        
        # Validate field types and structure
        self._validate_title(front_matter.get('title'))
        self._validate_authors(front_matter.get('authors'))
        self._validate_links(front_matter.get('links'))
        
        # Validate optional fields
        self._validate_optional_fields(front_matter)
        
        return len(self.errors) == 0
    
    def _validate_required_fields(self, front_matter: Dict[str, Any]) -> bool:
        """Check for required fields"""
        required_fields = ['title', 'authors', 'links']
        missing_fields = []
        
        for field in required_fields:
            if field not in front_matter:
                missing_fields.append(field)
        
        if missing_fields:
            for field in missing_fields:
                self.errors.append(f"Missing required field: {field}")
            return False
        
        return True
    
    def _validate_title(self, title: Any) -> None:
        """Validate title field"""
        if not isinstance(title, str):
            self.errors.append("Field 'title' must be a string")
        elif not title.strip():
            self.errors.append("Field 'title' cannot be empty")
    
    def _validate_authors(self, authors: Any) -> None:
        """Validate authors field"""
        if not isinstance(authors, list):
            self.errors.append("Field 'authors' must be a list")
            return
        
        if len(authors) == 0:
            self.errors.append("Field 'authors' cannot be empty")
            return
        
        for i, author in enumerate(authors):
            if isinstance(author, str):
                # Simple string format is acceptable
                continue
            elif isinstance(author, dict):
                self._validate_author_object(author, i)
            else:
                self.errors.append(f"Author {i} must be either a string or an object")
    
    def _validate_author_object(self, author: Dict[str, Any], index: int) -> None:
        """Validate individual author object"""
        if 'id' not in author:
            self.errors.append(f"Author {index} missing required field 'id'")
        elif not isinstance(author['id'], str) or not author['id'].strip():
            self.errors.append(f"Author {index} field 'id' must be a non-empty string")
        
        if 'display' not in author:
            self.errors.append(f"Author {index} missing required field 'display'")
        elif not isinstance(author['display'], str) or not author['display'].strip():
            self.errors.append(f"Author {index} field 'display' must be a non-empty string")
        
        # Validate optional fields
        if 'email' in author and not isinstance(author['email'], str):
            self.errors.append(f"Author {index} field 'email' must be a string")
        
        if 'orcid' in author:
            orcid = author['orcid']
            if not isinstance(orcid, str):
                self.errors.append(f"Author {index} field 'orcid' must be a string")
            elif not re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', orcid):
                self.errors.append(f"Author {index} field 'orcid' must be in format 0000-0000-0000-0000")
    
    def _validate_links(self, links: Any) -> None:
        """Validate links field"""
        if not isinstance(links, list):
            self.errors.append("Field 'links' must be a list")
            return
        
        # Empty links list is acceptable
        for i, link in enumerate(links):
            if not isinstance(link, dict):
                self.errors.append(f"Link {i} must be an object")
                continue
            
            # Required link fields
            required_link_fields = ['id', 'rel', 'to']
            for field in required_link_fields:
                if field not in link:
                    self.errors.append(f"Link {i} missing required field '{field}'")
                elif not isinstance(link[field], str) or not link[field].strip():
                    self.errors.append(f"Link {i} field '{field}' must be a non-empty string")
    
    def _validate_optional_fields(self, front_matter: Dict[str, Any]) -> None:
        """Validate optional fields"""
        # Validate dates structure
        if 'dates' in front_matter:
            self._validate_dates(front_matter['dates'])
        
        # Validate metrics structure
        if 'metrics' in front_matter:
            self._validate_metrics(front_matter['metrics'])
        
        # Validate permissions structure
        if 'permissions' in front_matter:
            self._validate_permissions(front_matter['permissions'])
        
        # Validate context structure
        if 'context' in front_matter:
            self._validate_context(front_matter['context'])

        # Validate simple optional fields
        self._validate_simple_optional_fields(front_matter)
    
    def _validate_dates(self, dates: Any) -> None:
        """Validate dates object"""
        if not isinstance(dates, dict):
            self.errors.append("Field 'dates' must be an object")
            return
        
        for date_field in ['created', 'modified']:
            if date_field in dates:
                date_value = dates[date_field]
                if not isinstance(date_value, str):
                    self.errors.append(f"Field 'dates.{date_field}' must be a string")
                else:
                    self._validate_iso_date(date_value, f"dates.{date_field}")
    
    def _validate_metrics(self, metrics: Any) -> None:
        """Validate metrics object"""
        if not isinstance(metrics, dict):
            self.errors.append("Field 'metrics' must be an object")
            return
        
        if 'word_count' in metrics:
            word_count = metrics['word_count']
            if not isinstance(word_count, int) or word_count < 0:
                self.errors.append("Field 'metrics.word_count' must be a non-negative integer")
        
        if 'reading_time' in metrics:
            reading_time = metrics['reading_time']
            if not isinstance(reading_time, str):
                self.errors.append("Field 'metrics.reading_time' must be a string")
    
    def _validate_permissions(self, permissions: Any) -> None:
        """Validate permissions object"""
        if not isinstance(permissions, dict):
            self.errors.append("Field 'permissions' must be an object")
            return
        
        if 'mode' in permissions:
            mode = permissions['mode']
            if not isinstance(mode, str):
                self.errors.append("Field 'permissions.mode' must be a string")
            elif mode not in ['draft', 'published', 'private']:
                self.errors.append("Field 'permissions.mode' must be one of: draft, published, private")
        
        for bool_field in ['editable', 'signed']:
            if bool_field in permissions:
                value = permissions[bool_field]
                if not isinstance(value, bool):
                    self.errors.append(f"Field 'permissions.{bool_field}' must be a boolean")

    def _validate_context(self, context: Any) -> None:
        """Validate context object"""
        if not isinstance(context, dict):
            self.errors.append("Field 'context' must be an object")
            return

        if 'lineage' in context:
            self._validate_lineage(context['lineage'])

        if 'resolution' in context:
            self._validate_resolution(context['resolution'])

    def _validate_lineage(self, lineage: Any) -> None:
        """Validate lineage object"""
        if not isinstance(lineage, dict):
            self.errors.append("Field 'context.lineage' must be an object")
            return

        if 'source' in lineage and not isinstance(lineage['source'], str):
            self.errors.append("Field 'context.lineage.source' must be a string")

        if 'parent_docs' in lineage:
            parent_docs = lineage['parent_docs']
            if not isinstance(parent_docs, list):
                self.errors.append("Field 'context.lineage.parent_docs' must be a list")
            else:
                for i, doc in enumerate(parent_docs):
                    if not isinstance(doc, str):
                        self.errors.append(f"Item {i} in 'context.lineage.parent_docs' must be a string")

    def _validate_resolution(self, resolution: Any) -> None:
        """Validate resolution object"""
        if not isinstance(resolution, dict):
            self.errors.append("Field 'context.resolution' must be an object")
            return

        if 'confidence' in resolution:
            confidence = resolution['confidence']
            if not isinstance(confidence, str):
                self.errors.append("Field 'context.resolution.confidence' must be a string")
            elif confidence not in ['exploratory', 'working', 'validated']:
                self.errors.append("Field 'context.resolution.confidence' must be one of: exploratory, working, validated")
    
    def _validate_simple_optional_fields(self, front_matter: Dict[str, Any]) -> None:
        """Validate simple optional fields"""
        string_fields = ['version', 'status', 'description', 'language', 'license']
        
        for field in string_fields:
            if field in front_matter:
                value = front_matter[field]
                if not isinstance(value, str):
                    self.errors.append(f"Field '{field}' must be a string")
        
        # Validate keywords
        if 'keywords' in front_matter:
            keywords = front_matter['keywords']
            if not isinstance(keywords, list):
                self.errors.append("Field 'keywords' must be a list")
            else:
                for i, keyword in enumerate(keywords):
                    if not isinstance(keyword, str):
                        self.errors.append(f"Keyword {i} must be a string")
        
        # Validate status values
        if 'status' in front_matter:
            status = front_matter['status']
            if isinstance(status, str) and status not in ['draft', 'published', 'archived']:
                self.errors.append("Field 'status' must be one of: draft, published, archived")
    
    def _validate_iso_date(self, date_str: str, field_name: str) -> None:
        """Validate ISO 8601 date format"""
        # Basic ISO 8601 pattern check
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)?$'
        if not re.match(iso_pattern, date_str):
            self.errors.append(f"Field '{field_name}' must be a valid ISO 8601 date (e.g., 2025-05-29T10:00:00Z)")
        
        # Try to parse the date to ensure it's actually valid
        try:
            # Remove timezone info for basic parsing
            date_part = date_str.replace('Z', '+00:00')
            if '+' in date_part or date_part.count('-') > 2:
                # Has timezone
                if 'T' in date_part:
                    from datetime import datetime
                    # Basic validation without full timezone parsing
                    datetime.fromisoformat(date_part.replace('Z', '+00:00'))
        except ValueError:
            self.errors.append(f"Field '{field_name}' contains an invalid date value")


def validate_front_matter_schema(front_matter: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate front-matter against the ORMD schema.
    
    Returns:
        tuple: (is_valid, error_list)
    """
    validator = FrontMatterValidator()
    is_valid = validator.validate(front_matter)
    return is_valid, validator.errors 