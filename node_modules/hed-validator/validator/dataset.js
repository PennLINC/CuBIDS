const { validateHedEventWithDefinitions } = require('./event')
const { parseHedStrings } = require('./stringParser')

const { generateIssue } = require('../utils/issues/issues')
const { filterNonEqualDuplicates } = require('../utils/map')

/**
 * Parse the dataset's definitions and evaluate labels in the dataset.
 *
 * @param {ParsedHedString[]} parsedHedStrings The dataset's parsed HED strings.
 * @return {[Map, Issue[]]} The definition map and any issues found.
 */
const parseDefinitions = function (parsedHedStrings) {
  const issues = []
  const parsedHedStringDefinitions = parsedHedStrings.flatMap(
    (parsedHedString) => {
      return parsedHedString.definitions
    },
  )
  const [definitionMap, definitionDuplicates] = filterNonEqualDuplicates(
    parsedHedStringDefinitions,
    (definition, other) => {
      return definition.equivalent(other)
    },
  )
  for (const [duplicateKey, duplicateValue] of definitionDuplicates) {
    issues.push(
      generateIssue('duplicateDefinition', {
        definition: duplicateKey,
        tagGroup: duplicateValue.originalTag,
      }),
    )
  }
  return [definitionMap, issues]
}

/**
 * Perform dataset-level validation on a HED dataset.
 *
 * @param {Definitions} definitions The parsed dataset definitions.
 * @param {string[]} hedStrings The dataset's HED strings.
 * @param {Schemas} hedSchemas The HED schema container object.
 * @return {[boolean, Issue[]]} Whether the HED dataset is valid and any issues found.
 */
const validateDataset = function(definitions, hedStrings, hedSchemas) {
  // TODO: Implement
  return [true, []]
}

/**
 * Validate a group of HED strings.
 *
 * @param {ParsedHedString[]} parsedHedStrings The dataset's parsed HED strings.
 * @param {Schemas} hedSchemas The HED schema container object.
 * @param {Map<string, ParsedHedGroup>} definitions The dataset's parsed definitions.
 * @param {boolean} checkForWarnings Whether to check for warnings or only errors.
 * @return {[boolean, Issue[]]} Whether the HED strings are valid and any issues found.
 */
const validateHedEvents = function (
  parsedHedStrings,
  hedSchemas,
  definitions,
  checkForWarnings,
) {
  let stringsValid = true
  let stringIssues = []
  for (const hedString of parsedHedStrings) {
    const [valid, issues] = validateHedEventWithDefinitions(
      hedString,
      hedSchemas,
      definitions,
      checkForWarnings,
    )
    stringsValid = stringsValid && valid
    stringIssues = stringIssues.concat(issues)
  }
  return [stringsValid, stringIssues]
}

/**
 * Validate a HED dataset.
 *
 * @param {string[]} hedStrings The dataset's HED strings.
 * @param {Schemas} hedSchemas The HED schema container object.
 * @param {boolean} checkForWarnings Whether to check for warnings or only errors.
 * @return {[boolean, Issue[]]} Whether the HED dataset is valid and any issues found.
 */
const validateHedDataset = function(
  hedStrings,
  hedSchemas,
  checkForWarnings = false,
) {
  if (hedStrings.length === 0) {
    return [true, []]
  }
  const [parsedHedStrings, parsedHedStringIssues, fullStringIssues] =
    parseHedStrings(hedStrings, hedSchemas)
  const [definitions, definitionIssues] = parseDefinitions(parsedHedStrings)
  const [stringsValid, stringIssues] = validateHedEvents(
    parsedHedStrings,
    hedSchemas,
    definitions,
    checkForWarnings,
  )
  stringIssues.concat(fullStringIssues, parsedHedStringIssues)
  if (!stringsValid) {
    return [false, stringIssues]
  }

  return [definitionIssues.length === 0, definitionIssues.concat(stringIssues)]
  //return validateDataset(definitions, newHedStrings, hedSchemas)
}

module.exports = {
  parseDefinitions: parseDefinitions,
  validateDataset: validateDataset,
  validateHedEvents: validateHedEvents,
  validateHedDataset: validateHedDataset,
}
