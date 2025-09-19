# ORMD CLI Implementation Plan - Context Layer MVP

**Version**: 0.1-context-extension  
**Date**: 2025-09-19  
**Status**: Planning Phase

---

## Overview

This document outlines the implementation plan for extending the ORMD CLI with Context Layer MVP functionality. The goal is to add conversation lineage tracking and explicit uncertainty levels while maintaining backward compatibility.

## New CLI Commands

### 1. `ormd create --from-conversation`

**Purpose**: Create a new ORMD document with conversation lineage pre-populated.

**Usage**:
```bash
ormd create --from-conversation my-notes.ormd
ormd create --from-conversation my-notes.ormd --source "claude-session-123"
ormd create --from-conversation my-notes.ormd --confidence exploratory
```

**Behavior**:
- Creates new ORMD file with basic structure
- Auto-populates `context.lineage.source` with timestamp-based identifier
- Allows override of source identifier via `--source` flag
- Sets confidence level via `--confidence` flag (default: "exploratory")
- Prompts for title and basic metadata

**Implementation Priority**: High (core MVP functionality)

### 2. `ormd link parent.ormd child.ormd`

**Purpose**: Establish parent-child relationships between ORMD documents.

**Usage**:
```bash
ormd link parent.ormd child.ormd
ormd link parent.ormd child.ormd --bidirectional
ormd link --remove parent.ormd child.ormd
```

**Behavior**:
- Adds parent.ormd to child.ormd's `context.lineage.parent_docs` array
- With `--bidirectional`, also creates a semantic link in parent to child
- With `--remove`, removes the parent-child relationship
- Validates that both files exist and are valid ORMD
- Updates modification timestamps

**Implementation Priority**: Medium (useful but not critical)

### 3. `ormd trace document.ormd`

**Purpose**: Display the lineage chain and context information for a document.

**Usage**:
```bash
ormd trace document.ormd
ormd trace document.ormd --depth 3
ormd trace document.ormd --format json
```

**Behavior**:
- Shows document's source, confidence level, and parent documents
- Recursively traces parent documents (default depth: 2)
- Displays as tree structure or JSON format
- Highlights missing or broken parent links
- Shows creation/modification timestamps

**Implementation Priority**: Medium (helpful for debugging/understanding)

## Enhanced Existing Commands

### `ormd validate`

**Enhancements**:
- Validate context schema if present
- Check that confidence levels are valid enum values
- Warn about missing parent documents (non-fatal)
- Report context-related validation issues

**Backward Compatibility**: Must not fail on documents without context blocks.

### `ormd init`

**Enhancements**:
- Add `--with-context` flag to include context block template
- Add `--confidence` flag to set initial confidence level
- Add `--source` flag to set lineage source

**Example**:
```bash
ormd init my-doc.ormd --with-context --confidence working --source "planning-session"
```

### `ormd convert`

**Enhancements**:
- Preserve context information when converting between formats
- Add context block when converting from other formats (optional)
- Set appropriate confidence levels based on source format

## Implementation Phases

### Phase 1: Core Context Support (Week 1)
- [ ] Update YAML parser to handle context block
- [ ] Add context validation to `ormd validate`
- [ ] Implement `ormd create --from-conversation`
- [ ] Update `ormd init` with context flags

### Phase 2: Relationship Management (Week 2)
- [ ] Implement `ormd link` command
- [ ] Add parent document validation
- [ ] Handle relative/absolute path resolution
- [ ] Update modification timestamps on linking

### Phase 3: Visualization and Tracing (Week 3)
- [ ] Implement `ormd trace` command
- [ ] Add tree structure display
- [ ] Add JSON output format
- [ ] Handle missing/broken links gracefully

### Phase 4: Integration and Polish (Week 4)
- [ ] Update `ormd convert` with context preservation
- [ ] Add comprehensive tests for all new functionality
- [ ] Update documentation and help text
- [ ] Performance optimization for large lineage chains

## Technical Implementation Details

### Context Schema Validation

```python
CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "lineage": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "minLength": 1},
                "parent_docs": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        },
        "resolution": {
            "type": "object",
            "properties": {
                "confidence": {
                    "type": "string",
                    "enum": ["exploratory", "working", "validated"]
                }
            }
        }
    }
}
```

### File Path Resolution

- Parent document paths should be resolved relative to the current document
- Support both relative (`../parent.ormd`) and absolute paths
- Validate path existence but don't fail if parent is missing (warn only)

### Source Identifier Generation

Default source identifiers should be human-readable and unique:
- Format: `{tool}-{date}-{time}` (e.g., `cli-2025-09-19-14-30`)
- Allow custom source strings via command line flags
- Validate source strings are non-empty

## Testing Strategy

### Unit Tests
- Context schema validation
- Source identifier generation
- Path resolution logic
- Command argument parsing

### Integration Tests
- End-to-end workflow: create → link → trace
- Backward compatibility with existing ORMD files
- Error handling for missing/invalid files
- Cross-platform path handling

### Manual Testing
- Real conversation handoff scenarios
- Complex lineage chains (3+ levels deep)
- Mixed documents (with and without context)
- Performance with large document sets

## Backward Compatibility Requirements

### Must Not Break
- Existing ORMD files without context blocks
- Current CLI commands and their behavior
- Existing validation rules and error messages
- File format compatibility

### Should Preserve
- Performance characteristics of existing commands
- Output formats and structure
- Error message clarity and helpfulness
- Command line interface consistency

## Success Metrics

1. **Functional**: All new commands work as specified
2. **Compatibility**: 100% backward compatibility with existing files
3. **Performance**: No significant slowdown in existing operations
4. **Usability**: Clear error messages and helpful documentation
5. **Adoption**: Positive feedback from early users

## Future Considerations

### Potential Enhancements
- Visual lineage graphs (HTML output)
- Integration with external context systems
- Batch operations for large document sets
- Context-aware search and filtering

### CLP Integration Path
This MVP implementation provides foundation for future Context Layer Protocol integration:
- Context schema aligns with CLP ContextBundle concept
- Lineage tracking prepares for CLP provenance features
- Confidence levels map to CLP resolution limits

---

**Implementation Timeline**: 4 weeks from start of development  
**Dependencies**: None (builds on existing ORMD CLI)  
**Risk Level**: Low (additive changes, strong backward compatibility)
