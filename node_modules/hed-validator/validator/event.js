const utils = require('../utils')
const {
  parseHedString,
  ParsedHedString,
  ParsedHedGroup,
  ParsedHedTag,
  hedStringIsAGroup,
} = require('./stringParser')
const { generateIssue } = require('../utils/issues/issues')
const { buildSchemaAttributesObject } = require('./schema')
const { Schemas } = require('../utils/schema')
const { convertHedStringToLong } = require('../converter/converter')

const uniqueType = 'unique'
const requiredType = 'required'
const requireChildType = 'requireChild'
const tagGroupType = 'tagGroup'
const topLevelTagGroupType = 'topLevelTagGroup'
const unitsElement = 'units'
const clockTimeUnitClass = 'clockTime'
const dateTimeUnitClass = 'dateTime'
const timeUnitClass = 'time'

// Validation tests

/**
 * Check for duplicate tags at the top level or within a single group.
 */
const checkForDuplicateTags = function (tagList) {
  const issues = []
  const duplicateTags = []
  for (const firstTag of tagList) {
    for (const secondTag of tagList) {
      if (firstTag === secondTag) {
        continue
      }
      if (firstTag.formattedTag === secondTag.formattedTag) {
        if (!duplicateTags.includes(firstTag)) {
          issues.push(
            generateIssue('duplicateTag', {
              tag: firstTag.originalTag,
              bounds: firstTag.originalBounds,
            }),
          )
          duplicateTags.push(firstTag)
        }
        if (!duplicateTags.includes(secondTag)) {
          issues.push(
            generateIssue('duplicateTag', {
              tag: secondTag.originalTag,
              bounds: secondTag.originalBounds,
            }),
          )
          duplicateTags.push(secondTag)
        }
      }
    }
  }
  return issues
}

/**
 * Check for multiple instances of a unique tag.
 */
const checkForMultipleUniqueTags = function (tagList, hedSchemas) {
  const issues = []
  const uniqueTagPrefixes =
    hedSchemas.baseSchema.attributes.tagAttributes[uniqueType]
  for (const uniqueTagPrefix in uniqueTagPrefixes) {
    let foundOne = false
    for (const tag of tagList) {
      if (tag.formattedTag.startsWith(uniqueTagPrefix)) {
        if (!foundOne) {
          foundOne = true
        } else {
          issues.push(
            generateIssue('multipleUniqueTags', {
              tag: uniqueTagPrefix,
            }),
          )
          break
        }
      }
    }
  }
  return issues
}

/**
 * Check if a tag is missing a required child.
 */
const checkIfTagRequiresChild = function (tag, hedSchemas) {
  const issues = []
  const invalid = hedSchemas.baseSchema.attributes.tagHasAttribute(
    tag.formattedTag,
    requireChildType,
  )
  if (invalid) {
    issues.push(generateIssue('childRequired', { tag: tag.originalTag }))
  }
  return issues
}

/**
 * Check that all required tags are present.
 */
const checkForRequiredTags = function (topLevelTags, hedSchemas) {
  const issues = []
  const requiredTagPrefixes =
    hedSchemas.baseSchema.attributes.tagAttributes[requiredType]
  for (const requiredTagPrefix in requiredTagPrefixes) {
    let foundOne = false
    for (const tag of topLevelTags) {
      if (tag.formattedTag.startsWith(requiredTagPrefix)) {
        foundOne = true
        break
      }
    }
    if (!foundOne) {
      issues.push(
        generateIssue('requiredPrefixMissing', {
          tagPrefix: requiredTagPrefix,
        }),
      )
    }
  }
  return issues
}

/**
 * Check that the unit is valid for the tag's unit class.
 *
 * @param {ParsedHedTag} tag A HED tag.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @param {boolean} checkForWarnings Whether to check for warnings.
 * @param {boolean} expectValuePlaceholderString Whether this string is expected to have a '#' placeholder representing a value.
 * @return {Issue[]} Any issues found.
 */
const checkIfTagUnitClassUnitsAreValid = function (
  tag,
  hedSchemas,
  checkForWarnings,
  expectValuePlaceholderString = false,
) {
  const issues = []
  if (
    !utils.HED.tagExistsInSchema(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
    ) &&
    utils.HED.isUnitClassTag(tag.formattedTag, hedSchemas.baseSchema.attributes)
  ) {
    const tagUnitClasses = utils.HED.getTagUnitClasses(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
    )
    const originalTagUnitValue = utils.HED.getTagName(tag.originalTag)
    const formattedTagUnitValue = utils.HED.getTagName(tag.formattedTag)
    const tagUnitClassUnits = utils.HED.getTagUnitClassUnits(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
    )
    if (dateTimeUnitClass in hedSchemas.baseSchema.attributes.unitClasses) {
      if (tagUnitClasses.includes(dateTimeUnitClass)) {
        if (utils.string.isDateTime(formattedTagUnitValue)) {
          return []
        } else {
          issues.push(generateIssue('invalidValue', { tag: tag.originalTag }))
          return issues
        }
      }
    }
    if (clockTimeUnitClass in hedSchemas.baseSchema.attributes.unitClasses) {
      if (tagUnitClasses.includes(clockTimeUnitClass)) {
        if (utils.string.isClockFaceTime(formattedTagUnitValue)) {
          return []
        } else {
          issues.push(generateIssue('invalidValue', { tag: tag.originalTag }))
          return issues
        }
      }
    } else if (timeUnitClass in hedSchemas.baseSchema.attributes.unitClasses) {
      if (
        tagUnitClasses.includes(timeUnitClass) &&
        tag.originalTag.includes(':')
      ) {
        if (utils.string.isClockFaceTime(formattedTagUnitValue)) {
          return []
        } else {
          issues.push(generateIssue('invalidValue', { tag: tag.originalTag }))
          return issues
        }
      }
    }
    const [foundUnit, validUnit, value] = utils.HED.validateUnits(
      originalTagUnitValue,
      tagUnitClassUnits,
      hedSchemas.baseSchema.attributes,
    )
    const validValue = utils.HED.validateValue(
      value,
      hedSchemas.baseSchema.attributes.tagHasAttribute(
        utils.HED.replaceTagNameWithPound(tag.formattedTag),
        'isNumeric',
      ),
      hedSchemas.isHed3,
    )
    if (!foundUnit && checkForWarnings) {
      const defaultUnit = utils.HED.getUnitClassDefaultUnit(
        tag.formattedTag,
        hedSchemas.baseSchema.attributes,
      )
      issues.push(
        generateIssue('unitClassDefaultUsed', {
          tag: tag.originalTag,
          defaultUnit: defaultUnit,
        }),
      )
    } else if (!validUnit) {
      issues.push(
        generateIssue('unitClassInvalidUnit', {
          tag: tag.originalTag,
          unitClassUnits: tagUnitClassUnits.sort().join(','),
        }),
      )
    } else if (!validValue) {
      issues.push(generateIssue('invalidValue', { tag: tag.originalTag }))
    }
    return issues
  } else {
    return []
  }
}

/**
 * Check the syntax of tag values.
 *
 * @param {ParsedHedTag} tag A HED tag.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @param {boolean} expectValuePlaceholderString Whether this string is expected to have a '#' placeholder representing a value.
 * @return {Issue[]} Any issues found.
 */
const checkValueTagSyntax = function (
  tag,
  hedSchemas,
  expectValuePlaceholderString,
) {
  if (
    utils.HED.tagTakesValue(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
      hedSchemas.isHed3,
    ) &&
    !utils.HED.isUnitClassTag(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
    )
  ) {
    const isValidValue = utils.HED.validateValue(
      utils.HED.getTagName(tag.formattedTag),
      hedSchemas.baseSchema.attributes.tagHasAttribute(
        utils.HED.replaceTagNameWithPound(tag.formattedTag),
        'isNumeric',
      ),
      hedSchemas.isHed3,
    )
    if (!isValidValue) {
      return [generateIssue('invalidValue', { tag: tag.originalTag })]
    } else {
      return []
    }
  } else {
    // Unit class tags are handled by the two functions above.
    return []
  }
}

/**
 * Check if an individual HED tag is in the schema or is an allowed extension.
 */
const checkIfTagIsValid = function (
  tag,
  previousTag,
  hedSchemas,
  checkForWarnings,
  expectValuePlaceholderString,
) {
  const issues = []
  if (
    utils.HED.tagExistsInSchema(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
    ) || // This tag itself exists in the HED schema.
    utils.HED.tagTakesValue(
      tag.formattedTag,
      hedSchemas.baseSchema.attributes,
      hedSchemas.isHed3,
    ) // This tag is a valid value-taking tag in the HED schema.
  ) {
    return []
  }
  // Whether this tag has an ancestor with the 'extensionAllowed' attribute.
  const isExtensionAllowedTag = utils.HED.isExtensionAllowedTag(
    tag.formattedTag,
    hedSchemas.baseSchema.attributes,
  )
  if (
    expectValuePlaceholderString &&
    tag.formattedTag.split('#').length === 2
  ) {
    const valueTag = utils.HED.replaceTagNameWithPound(tag.formattedTag)
    if (
      valueTag.split('#').length !== 2 || // To avoid a redundant issue.
      utils.HED.tagTakesValue(
        valueTag,
        hedSchemas.baseSchema.attributes,
        hedSchemas.isHed3,
      )
    ) {
      return []
    } else {
      issues.push(
        generateIssue('invalidPlaceholder', {
          tag: tag.originalTag,
        }),
      )
      return issues
    }
  }
  if (
    !isExtensionAllowedTag &&
    utils.HED.tagTakesValue(
      previousTag.formattedTag,
      hedSchemas.baseSchema.attributes,
      hedSchemas.isHed3,
    )
  ) {
    // This tag isn't an allowed extension, but the previous tag takes a value.
    // This is likely caused by an extraneous comma.
    issues.push(
      generateIssue('extraCommaOrInvalid', {
        tag: tag.originalTag,
        previousTag: previousTag.originalTag,
      }),
    )
    return issues
  } else if (!isExtensionAllowedTag) {
    // This is not a valid tag.
    issues.push(generateIssue('invalidTag', { tag: tag.originalTag }))
    return issues
  } else {
    // This is an allowed extension.
    if (checkForWarnings) {
      issues.push(generateIssue('extension', { tag: tag.originalTag }))
      return issues
    } else {
      return []
    }
  }
}

/**
 * Check basic placeholder tag syntax.
 *
 * @param {ParsedHedTag} tag A HED tag.
 * @return {Issue[]} Any issues found.
 */
const checkPlaceholderTagSyntax = function (tag) {
  const placeholderCount = utils.string.getCharacterCount(tag.formattedTag, '#')
  if (placeholderCount === 0) {
    return []
  } else if (placeholderCount === 1) {
    const valueTag = utils.HED.replaceTagNameWithPound(tag.formattedTag)
    if (utils.string.getCharacterCount(valueTag, '#') !== 1) {
      return [
        generateIssue('invalidPlaceholder', {
          tag: tag.originalTag,
        }),
      ]
    } else {
      return []
    }
  } else {
    // More than one placeholder.
    return [
      generateIssue('invalidPlaceholder', {
        tag: tag.originalTag,
      }),
    ]
  }
}

/**
 * Check full-string placeholder syntax.
 *
 * @param {ParsedHedString} parsedString The parsed HED string.
 * @param {boolean} expectValuePlaceholderString Whether this string is expected to have a '#' placeholder representing a value.
 * @return {Issue[]} Any issues found.
 */
const checkPlaceholderStringSyntax = function (
  parsedString,
  expectValuePlaceholderString,
) {
  const issues = []
  let standalonePlaceholders = 0
  let definitionPlaceholders
  let standaloneIssueGenerated = false
  let firstStandaloneTag = ''
  for (const tag of parsedString.topLevelTags) {
    const tagString = tag.formattedTag
    const tagPlaceholders = utils.string.getCharacterCount(tagString, '#')
    standalonePlaceholders += tagPlaceholders
    if (!firstStandaloneTag && standalonePlaceholders >= 1) {
      firstStandaloneTag = tag.originalTag
    }
    if (
      tagPlaceholders &&
      ((!expectValuePlaceholderString && standalonePlaceholders) ||
        standalonePlaceholders > 1)
    ) {
      if (expectValuePlaceholderString && !standaloneIssueGenerated) {
        issues.push(
          generateIssue('invalidPlaceholder', {
            tag: firstStandaloneTag,
          }),
        )
      }
      issues.push(
        generateIssue('invalidPlaceholder', {
          tag: tag.originalTag,
        }),
      )
      standaloneIssueGenerated = true
    }
  }
  for (const tagGroup of parsedString.tagGroups) {
    if (tagGroup.isDefinitionGroup) {
      definitionPlaceholders = 0
      const isDefinitionPlaceholder =
        utils.HED.getTagName(tagGroup.definitionTag.formattedTag) === '#'
      const definitionName = isDefinitionPlaceholder
        ? utils.HED.getTagName(
            utils.HED.getParentTag(tagGroup.definitionTag.originalTag),
          )
        : utils.HED.getTagName(tagGroup.definitionTag.originalTag)
      for (const tag of tagGroup.tagIterator()) {
        if (isDefinitionPlaceholder && tag === tagGroup.definitionTag) {
          continue
        }
        const tagString = tag.formattedTag
        definitionPlaceholders += utils.string.getCharacterCount(tagString, '#')
      }
      if (
        !(
          (!isDefinitionPlaceholder && definitionPlaceholders === 0) ||
          (isDefinitionPlaceholder && definitionPlaceholders === 1)
        )
      ) {
        issues.push(
          generateIssue('invalidPlaceholderInDefinition', {
            definition: definitionName,
          }),
        )
      }
    } else if (!standaloneIssueGenerated) {
      for (const tag of tagGroup.tagIterator()) {
        const tagString = tag.formattedTag
        const tagPlaceholders = utils.string.getCharacterCount(tagString, '#')
        standalonePlaceholders += tagPlaceholders
        if (!firstStandaloneTag && standalonePlaceholders >= 1) {
          firstStandaloneTag = tag.originalTag
        }
        if (
          tagPlaceholders &&
          ((!expectValuePlaceholderString && standalonePlaceholders) ||
            standalonePlaceholders > 1)
        ) {
          if (expectValuePlaceholderString && !standaloneIssueGenerated) {
            issues.push(
              generateIssue('invalidPlaceholder', {
                tag: firstStandaloneTag,
              }),
            )
          }
          issues.push(
            generateIssue('invalidPlaceholder', {
              tag: tag.originalTag,
            }),
          )
          standaloneIssueGenerated = true
        }
      }
    }
  }
  if (expectValuePlaceholderString && standalonePlaceholders === 0) {
    issues.push(
      generateIssue('missingPlaceholder', {
        string: parsedString.hedString,
      }),
    )
  }
  return issues
}

// HED 3 checks

/**
 * Check the syntax of HED 3 definitions.
 *
 * @param {ParsedHedGroup} tagGroup The tag group.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @return {Issue[]} Any issues found.
 */
const checkDefinitionSyntax = function (tagGroup, hedSchemas) {
  const definitionShortTag = 'definition'
  const defExpandShortTag = 'def-expand'
  const defShortTag = 'def'
  const [definitionParentTag, definitionParentTagIssues] =
    convertHedStringToLong(hedSchemas, definitionShortTag)
  const [defExpandParentTag, defExpandParentTagIssues] = convertHedStringToLong(
    hedSchemas,
    defExpandShortTag,
  )
  const [defParentTag, defParentTagIssues] = convertHedStringToLong(
    hedSchemas,
    defShortTag,
  )
  const issues = [].concat(
    definitionParentTagIssues,
    defExpandParentTagIssues,
    defParentTagIssues,
  )
  let definitionTagFound = false
  let defExpandTagFound = false
  let definitionName
  for (const tag of tagGroup.tags) {
    if (tag instanceof ParsedHedGroup) {
      continue
    }
    if (tag.canonicalTag.startsWith(definitionParentTag)) {
      definitionTagFound = true
      definitionName = utils.HED.getTagName(tag.originalTag)
      break
    } else if (tag.canonicalTag.startsWith(defExpandParentTag)) {
      defExpandTagFound = true
      definitionName = utils.HED.getTagName(tag.originalTag)
      break
    }
  }
  if (!(definitionTagFound || defExpandTagFound)) {
    return []
  }
  let tagGroupValidated = false
  let tagGroupIssueGenerated = false
  const nestedDefinitionParentTags = [
    definitionParentTag,
    defExpandParentTag,
    defParentTag,
  ]
  for (const tag of tagGroup.tags) {
    if (tag instanceof ParsedHedGroup) {
      if (tagGroupValidated && !tagGroupIssueGenerated) {
        issues.push(
          generateIssue('multipleTagGroupsInDefinition', {
            definition: definitionName,
          }),
        )
        tagGroupIssueGenerated = true
        continue
      }
      tagGroupValidated = true
      for (const innerTag of tag.tagIterator()) {
        if (
          nestedDefinitionParentTags.includes(innerTag.canonicalTag) ||
          nestedDefinitionParentTags.includes(
            utils.HED.getParentTag(innerTag.canonicalTag),
          )
        ) {
          issues.push(
            generateIssue('nestedDefinition', {
              definition: definitionName,
            }),
          )
        }
      }
    } else if (
      (definitionTagFound &&
        !tag.canonicalTag.startsWith(definitionParentTag)) ||
      (defExpandTagFound && !tag.canonicalTag.startsWith(defExpandParentTag))
    ) {
      issues.push(
        generateIssue('illegalDefinitionGroupTag', {
          tag: tag.originalTag,
          definition: definitionName,
        }),
      )
    }
  }
  return issues
}

/**
 * Check for missing HED 3 definitions.
 *
 * @param {ParsedHedTag} tag The HED tag.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @param {Map<string, ParsedHedGroup>} definitions The parsed definitions.
 * @param {string} defShortTag The short tag to check for.
 * @return {Issue[]} Any issues found.
 */
const checkForMissingDefinitions = function (
  tag,
  hedSchemas,
  definitions,
  defShortTag = 'Def',
) {
  const [defParentTag, defParentTagIssues] = convertHedStringToLong(
    hedSchemas,
    defShortTag,
  )
  const formattedDefParentTag = defParentTag.toLowerCase()
  const issues = defParentTagIssues
  if (!utils.HED.isDescendantOf(tag.formattedTag, formattedDefParentTag)) {
    return []
  }
  const defName = utils.HED.getDefinitionName(tag.formattedTag, defShortTag)
  if (!definitions.has(defName)) {
    issues.push(generateIssue('missingDefinition', { def: defName }))
  }
  return issues
}

/**
 * Check for invalid top-level tags.
 *
 * @param {ParsedHedTag[]} topLevelTags The list of top-level tags.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @return {Issue[]} Any issues found.
 */
const checkForInvalidTopLevelTags = function (topLevelTags, hedSchemas) {
  const issues = []
  for (const topLevelTag of topLevelTags) {
    if (
      !hedStringIsAGroup(topLevelTag.formattedTag) &&
      (hedSchemas.baseSchema.attributes.tagHasAttribute(
        topLevelTag.formattedTag,
        tagGroupType,
      ) ||
        hedSchemas.baseSchema.attributes.tagHasAttribute(
          utils.HED.getParentTag(topLevelTag.formattedTag),
          tagGroupType,
        ))
    ) {
      issues.push(
        generateIssue('invalidTopLevelTag', {
          tag: topLevelTag.originalTag,
        }),
      )
    }
  }
  return issues
}

/**
 * Check for invalid top-level tag group tags.
 *
 * @param {ParsedHedString} parsedString The parsed HED string to validate.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @return {Issue[]} Any issues found.
 */
const checkForInvalidTopLevelTagGroupTags = function (
  parsedString,
  hedSchemas,
) {
  let issues = []
  const topLevelTagGroupTagsFound = {}
  for (const tag of parsedString.tags) {
    if (
      hedSchemas.baseSchema.attributes.tagHasAttribute(
        tag.formattedTag,
        topLevelTagGroupType,
      ) ||
      hedSchemas.baseSchema.attributes.tagHasAttribute(
        utils.HED.getParentTag(tag.formattedTag),
        topLevelTagGroupType,
      )
    ) {
      let tagFound = false
      parsedString.topLevelTagGroups.forEach((tagGroup, index) => {
        if (tagGroup.includes(tag)) {
          tagFound = true
          if (topLevelTagGroupTagsFound[index]) {
            issues.push(
              generateIssue('multipleTopLevelTagGroupTags', {
                tag: tag.originalTag,
                otherTag: topLevelTagGroupTagsFound[index],
              }),
            )
          } else {
            topLevelTagGroupTagsFound[index] = tag.originalTag
          }
        }
      })
      if (!tagFound) {
        issues.push(
          generateIssue('invalidTopLevelTagGroupTag', {
            tag: tag.originalTag,
          }),
        )
      }
    }
  }
  return issues
}

// Validation groups

/**
 * Validate the full parsed HED string.
 *
 * @param {ParsedHedString} parsedString The parsed HED string to validate.
 * @param {boolean} expectValuePlaceholderString Whether this string is expected to have a '#' placeholder representing a value.
 * @return {Issue[]} Any issues found.
 */
const validateFullParsedHedString = function (
  parsedString,
  expectValuePlaceholderString,
) {
  return checkPlaceholderStringSyntax(
    parsedString,
    expectValuePlaceholderString,
  )
}

/**
 * Validate an individual HED tag.
 */
const validateIndividualHedTag = function (
  tag,
  previousTag,
  hedSchemas,
  doSemanticValidation,
  checkForWarnings,
  isEventLevel,
  expectValuePlaceholderString,
  definitions,
) {
  let issues = []
  if (doSemanticValidation) {
    issues = issues.concat(
      checkIfTagIsValid(
        tag,
        previousTag,
        hedSchemas,
        checkForWarnings,
        expectValuePlaceholderString,
      ),
      checkIfTagUnitClassUnitsAreValid(
        tag,
        hedSchemas,
        checkForWarnings,
        expectValuePlaceholderString,
      ),
      checkIfTagRequiresChild(tag, hedSchemas),
    )
    if (!isEventLevel) {
      issues = issues.concat(
        checkValueTagSyntax(tag, hedSchemas, expectValuePlaceholderString),
      )
    }
    if (hedSchemas.isHed3 && definitions !== null) {
      issues = issues.concat(
        checkForMissingDefinitions(tag, hedSchemas, definitions, 'Def'),
        checkForMissingDefinitions(tag, hedSchemas, definitions, 'Def-expand'),
      )
    }
  }
  if (expectValuePlaceholderString) {
    issues = issues.concat(checkPlaceholderTagSyntax(tag))
  }
  return issues
}

/**
 * Validate the individual HED tags in a parsed HED string object.
 */
const validateIndividualHedTags = function (
  parsedString,
  hedSchemas,
  doSemanticValidation,
  checkForWarnings,
  isEventLevel,
  expectValuePlaceholderString = false,
  definitions = null,
) {
  let issues = []
  let previousTag = new ParsedHedTag('', '', [0, 0], hedSchemas)
  for (const tag of parsedString.tags) {
    issues = issues.concat(
      validateIndividualHedTag(
        tag,
        previousTag,
        hedSchemas,
        doSemanticValidation,
        checkForWarnings,
        isEventLevel,
        expectValuePlaceholderString,
        definitions,
      ),
    )
    previousTag = tag
  }
  return issues
}

/**
 * Validate a HED tag level.
 */
const validateHedTagLevel = function (
  tagList,
  hedSchemas,
  doSemanticValidation,
) {
  let issues = []
  if (doSemanticValidation) {
    issues = issues.concat(checkForMultipleUniqueTags(tagList, hedSchemas))
  }
  issues = issues.concat(checkForDuplicateTags(tagList))
  return issues
}

/**
 * Validate the HED tag levels in a parsed HED string object.
 */
const validateHedTagLevels = function (
  parsedString,
  hedSchemas,
  doSemanticValidation,
) {
  let issues = []
  for (const tagGroup of parsedString.tagGroups) {
    for (const subGroup of tagGroup.subGroupIterator()) {
      issues = issues.concat(
        validateHedTagLevel(subGroup, hedSchemas, doSemanticValidation),
      )
    }
  }
  issues = issues.concat(
    validateHedTagLevel(
      parsedString.topLevelTags,
      hedSchemas,
      doSemanticValidation,
    ),
  )
  return issues
}

/**
 * Validate a HED tag group.
 */
const validateHedTagGroup = function (
  originalTagGroup,
  parsedTagGroup,
  hedSchemas,
  doSemanticValidation,
) {
  if (doSemanticValidation && hedSchemas.isHed3) {
    return checkDefinitionSyntax(parsedTagGroup, hedSchemas)
  } else {
    return []
  }
}

/**
 * Validate the HED tag groups in a parsed HED string.
 */
const validateHedTagGroups = function (
  parsedString,
  hedSchemas,
  doSemanticValidation,
) {
  let issues = []
  for (let i = 0; i < parsedString.tagGroups.length; i++) {
    const parsedTag = parsedString.tagGroups[i]
    const originalTag = parsedString.tagGroupStrings[i]
    issues = issues.concat(
      validateHedTagGroup(
        originalTag,
        parsedTag,
        hedSchemas,
        doSemanticValidation,
      ),
    )
  }
  return issues
}

/**
 * Validate the top-level HED tags in a parsed HED string.
 */
const validateTopLevelTags = function (
  parsedString,
  hedSchemas,
  doSemanticValidation,
  checkForWarnings,
) {
  let issues = []
  const topLevelTags = parsedString.topLevelTags
  if (hedSchemas.isHed3) {
    // This is false when doSemanticValidation is false (i.e. there is no loaded schema).
    issues = issues.concat(
      checkForInvalidTopLevelTags(topLevelTags, hedSchemas),
    )
  }
  if (doSemanticValidation && checkForWarnings) {
    issues = issues.concat(checkForRequiredTags(topLevelTags, hedSchemas))
  }
  return issues
}

/**
 * Validate the top-level HED tag groups in a parsed HED string.
 *
 * @param {ParsedHedString} parsedString The parsed HED string to validate.
 * @param {Schemas} hedSchemas The HED schema collection.
 * @param {boolean} doSemanticValidation Whether to perform semantic validation.
 * @return {Issue[]} Any issues found.
 */
const validateTopLevelTagGroups = function (
  parsedString,
  hedSchemas,
  doSemanticValidation,
) {
  if (doSemanticValidation) {
    return checkForInvalidTopLevelTagGroupTags(parsedString, hedSchemas)
  } else {
    return []
  }
}

/**
 * Perform initial validation on a HED string and parse it so further validation can be performed.
 *
 * @param {string|ParsedHedString} hedString The HED string to validate.
 * @param {Schemas} hedSchemas The HED schemas to validate against.
 * @return {[ParsedHedString, Schemas, Issue[], boolean]} The parsed HED string, the actual HED schema collection to use, any issues found, and whether to perform semantic validation.
 */
const initiallyValidateHedString = function (hedString, hedSchemas) {
  let doSemanticValidation = hedSchemas instanceof Schemas
  if (!doSemanticValidation) {
    hedSchemas = new Schemas(null)
  }
  let parsedString, fullStringIssues, parsedStringIssues
  // Skip parsing if we're passed an already-parsed string.
  if (hedString instanceof ParsedHedString) {
    parsedString = hedString
    fullStringIssues = []
    parsedStringIssues = []
  } else {
    ;[parsedString, fullStringIssues, parsedStringIssues] = parseHedString(
      hedString,
      hedSchemas,
    )
  }
  if (parsedString === null) {
    return [null, hedSchemas, fullStringIssues, null]
  } else if (parsedStringIssues.length > 0) {
    doSemanticValidation = false
    hedSchemas = new Schemas(null)
  }
  if (doSemanticValidation && !hedSchemas.baseSchema.attributes) {
    hedSchemas.baseSchema.attributes = buildSchemaAttributesObject(
      hedSchemas.baseSchema.xmlData,
    )
  }
  return [
    parsedString,
    hedSchemas,
    fullStringIssues.concat(parsedStringIssues),
    doSemanticValidation,
  ]
}

/**
 * Validate a HED string.
 *
 * @param {string|ParsedHedString} hedString The HED string to validate.
 * @param {Schemas} hedSchemas The HED schemas to validate against.
 * @param {boolean} checkForWarnings Whether to check for warnings or only errors.
 * @param {boolean} expectValuePlaceholderString Whether this string is expected to have a '#' placeholder representing a value.
 * @returns {[boolean, Issue[]]} Whether the HED string is valid and any issues found.
 * @deprecated
 */
const validateHedString = function (
  hedString,
  hedSchemas,
  checkForWarnings = false,
  expectValuePlaceholderString = false,
) {
  const [
    parsedString,
    actualHedSchemas,
    parsedStringIssues,
    doSemanticValidation,
  ] = initiallyValidateHedString(hedString, hedSchemas)
  if (parsedString === null) {
    return [false, parsedStringIssues]
  }

  const issues = parsedStringIssues.concat(
    validateFullParsedHedString(parsedString, expectValuePlaceholderString),
    validateIndividualHedTags(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
      checkForWarnings,
      false,
      expectValuePlaceholderString,
    ),
    validateHedTagGroups(parsedString, actualHedSchemas, doSemanticValidation),
  )

  return [issues.length === 0, issues]
}

/**
 * Validate a HED event string.
 *
 * @param {string|ParsedHedString} hedString The HED event string to validate.
 * @param {Schemas} hedSchemas The HED schemas to validate against.
 * @param {boolean} checkForWarnings Whether to check for warnings or only errors.
 * @returns {[boolean, Issue[]]} Whether the HED string is valid and any issues found.
 * @deprecated
 */
const validateHedEvent = function (
  hedString,
  hedSchemas,
  checkForWarnings = false,
) {
  const [
    parsedString,
    actualHedSchemas,
    parsedStringIssues,
    doSemanticValidation,
  ] = initiallyValidateHedString(hedString, hedSchemas)
  if (parsedString === null) {
    return [false, parsedStringIssues]
  }

  const issues = parsedStringIssues.concat(
    validateTopLevelTags(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
      checkForWarnings,
    ),
    validateTopLevelTagGroups(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
    ),
    validateIndividualHedTags(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
      checkForWarnings,
      true,
    ),
    validateHedTagLevels(parsedString, actualHedSchemas, doSemanticValidation),
    validateHedTagGroups(parsedString),
  )

  return [issues.length === 0, issues]
}

/**
 * Validate a HED event string.
 *
 * @param {string|ParsedHedString} hedString The HED event string to validate.
 * @param {Schemas} hedSchemas The HED schemas to validate against.
 * @param {Map<string, ParsedHedGroup>} definitions The dataset's parsed definitions.
 * @param {boolean} checkForWarnings Whether to check for warnings or only errors.
 * @returns {[boolean, Issue[]]} Whether the HED string is valid and any issues found.
 */
const validateHedEventWithDefinitions = function (
  hedString,
  hedSchemas,
  definitions,
  checkForWarnings = false,
) {
  const [
    parsedString,
    actualHedSchemas,
    parsedStringIssues,
    doSemanticValidation,
  ] = initiallyValidateHedString(hedString, hedSchemas)
  if (parsedString === null) {
    return [false, parsedStringIssues]
  }

  const issues = parsedStringIssues.concat(
    validateTopLevelTags(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
      checkForWarnings,
    ),
    validateTopLevelTagGroups(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
    ),
    validateIndividualHedTags(
      parsedString,
      actualHedSchemas,
      doSemanticValidation,
      checkForWarnings,
      true,
      definitions,
    ),
    validateHedTagLevels(parsedString, actualHedSchemas, doSemanticValidation),
    validateHedTagGroups(parsedString),
  )

  return [issues.length === 0, issues]
}

module.exports = {
  validateIndividualHedTags: validateIndividualHedTags,
  validateHedTagGroups: validateHedTagGroups,
  validateHedTagLevels: validateHedTagLevels,
  validateTopLevelTags: validateTopLevelTags,
  validateTopLevelTagGroups: validateTopLevelTagGroups,
  validateHedString: validateHedString,
  validateHedEvent: validateHedEvent,
  validateHedEventWithDefinitions: validateHedEventWithDefinitions,
}
