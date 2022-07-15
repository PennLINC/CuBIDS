const { stringTemplate } = require('../string')

const issueData = {
  parentheses: {
    hedCode: 'HED_PARENTHESES_MISMATCH',
    level: 'error',
    message: stringTemplate`Number of opening and closing parentheses are unequal. ${'opening'} opening parentheses. ${'closing'} closing parentheses.`,
  },
  invalidTag: {
    hedCode: 'HED_TAG_INVALID',
    level: 'error',
    message: stringTemplate`Invalid tag - "${'tag'}"`,
  },
  extraDelimiter: {
    hedCode: 'HED_TAG_EMPTY',
    level: 'error',
    message: stringTemplate`Extra delimiter "${'character'}" at index ${'index'} of string "${'string'}"`,
  },
  commaMissing: {
    hedCode: 'HED_COMMA MISSING',
    level: 'error',
    message: stringTemplate`Comma missing after - "${'tag'}"`,
  },
  duplicateTag: {
    hedCode: 'HED_TAG_REPEATED',
    level: 'error',
    message: stringTemplate`Duplicate tag at indices (${0}, ${1}) - "${'tag'}"`,
  },
  multipleUniqueTags: {
    hedCode: 'HED_TAG_NOT_UNIQUE',
    level: 'error',
    message: stringTemplate`Multiple unique tags with prefix - "${'tag'}"`,
  },
  tooManyTildes: {
    hedCode: 'HED_TILDES_UNSUPPORTED',
    level: 'error',
    message: stringTemplate`Too many tildes - group "${'tagGroup'}"`,
  },
  childRequired: {
    hedCode: 'HED_TAG_REQUIRES_CHILD',
    level: 'error',
    message: stringTemplate`Descendant tag required - "${'tag'}"`,
  },
  requiredPrefixMissing: {
    hedCode: 'HED_REQUIRED_TAG_MISSING',
    level: 'warning',
    message: stringTemplate`Tag with prefix "${'tagPrefix'}" is required`,
  },
  unitClassDefaultUsed: {
    hedCode: 'HED_UNITS_MISSING',
    level: 'warning',
    message: stringTemplate`No unit specified. Using "${'defaultUnit'}" as the default - "${'tag'}"`,
  },
  unitClassInvalidUnit: {
    hedCode: 'HED_UNITS_INVALID',
    level: 'error',
    message: stringTemplate`Invalid unit - "${'tag'}" - valid units are "${'unitClassUnits'}"`,
  },
  extraCommaOrInvalid: {
    hedCode: 'HED_TAG_INVALID',
    level: 'error',
    message: stringTemplate`Either "${'previousTag'}" contains a comma when it should not or "${'tag'}" is not a valid tag`,
  },
  invalidCharacter: {
    hedCode: 'HED_CHARACTER_INVALID',
    level: 'error',
    message: stringTemplate`Invalid character "${'character'}" at index ${'index'} of string "${'string'}"`,
  },
  extension: {
    hedCode: 'HED_TAG_EXTENDED',
    level: 'warning',
    message: stringTemplate`Tag extension found - "${'tag'}"`,
  },
  invalidPlaceholder: {
    hedCode: 'HED_PLACEHOLDER_INVALID',
    level: 'error',
    message: stringTemplate`Invalid placeholder - "${'tag'}"`,
  },
  invalidPlaceholderInDefinition: {
    hedCode: 'HED_PLACEHOLDER_INVALID',
    level: 'error',
    message: stringTemplate`Invalid placeholder in definition - "${'definition'}"`,
  },
  missingPlaceholder: {
    hedCode: 'HED_PLACEHOLDER_INVALID',
    level: 'error',
    message: stringTemplate`HED value string "${'string'}" is missing a required placeholder.`,
  },
  invalidValue: {
    hedCode: 'HED_VALUE_INVALID',
    level: 'error',
    message: stringTemplate`Invalid placeholder value for tag "${'tag'}"`,
  },
  invalidParentNode: {
    hedCode: 'HED_VALUE_IS_NODE',
    level: 'error',
    message: stringTemplate`"${'tag'}" appears as "${'parentTag'}" and cannot be used as an extension. Indices (${0}, ${1}).`,
  },
  emptyTagFound: {
    hedCode: 'HED_NODE_NAME_EMPTY',
    level: 'error',
    message: stringTemplate`Empty tag cannot be converted.`,
  },
  duplicateTagsInSchema: {
    hedCode: 'HED_GENERIC_ERROR',
    level: 'error',
    message: stringTemplate`Source HED schema is invalid as it contains duplicate tags.`,
  },
  illegalDefinitionGroupTag: {
    hedCode: 'HED_DEFINITION_INVALID',
    level: 'error',
    message: stringTemplate`Illegal tag "${'tag'}" in tag group for definition "${'definition'}"`,
  },
  nestedDefinition: {
    hedCode: 'HED_DEFINITION_INVALID',
    level: 'error',
    message: stringTemplate`Illegal nested definition in tag group for definition "${'definition'}"`,
  },
  multipleTagGroupsInDefinition: {
    hedCode: 'HED_DEFINITION_INVALID',
    level: 'error',
    message: stringTemplate`Multiple inner tag groups found in definition "${'definition'}"`,
  },
  duplicateDefinition: {
    hedCode: 'HED_DEFINITION_INVALID',
    level: 'error',
    message: stringTemplate`Definition "${'definition'}" is declared multiple times. This instance's tag group is "${'tagGroup'}"`,
  },
  invalidTopLevelTagGroupTag: {
    hedCode: 'HED_TAG_GROUP_ERROR',
    level: 'error',
    message: stringTemplate`Tag "${'tag'}" is only allowed inside of a top-level tag group.`,
  },
  multipleTopLevelTagGroupTags: {
    hedCode: 'HED_TAG_GROUP_ERROR',
    level: 'error',
    message: stringTemplate`Tag "${'tag'}" found in top-level tag group where "${'otherTag'}" was already defined.`,
  },
  invalidTopLevelTag: {
    hedCode: 'HED_TAG_GROUP_ERROR',
    level: 'error',
    message: stringTemplate`Tag "${'tag'}" is only allowed inside of a tag group.`,
  },
  requestedSchemaLoadFailed: {
    hedCode: 'HED_SCHEMA_LOAD_FAILED',
    level: 'warning',
    message: stringTemplate`The requested schema "${'schemaDefinition'}" failed to load. The error given was "${'error'}". The fallback schema bundled with this validator will be used instead.`,
  },
  fallbackSchemaLoadFailed: {
    hedCode: 'HED_SCHEMA_LOAD_FAILED',
    level: 'error',
    message: stringTemplate`The fallback schema bundled with this validator failed to load. The error given was "${'error'}". No HED validation was performed.`,
  },
  genericError: {
    hedCode: 'HED_GENERIC_ERROR',
    level: 'error',
    message: stringTemplate`Unknown HED error.`,
  },
}

module.exports = issueData
