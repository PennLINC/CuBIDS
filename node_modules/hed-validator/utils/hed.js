const pluralize = require('pluralize')
pluralize.addUncountableRule('hertz')

const { isNumber } = require('./string')

const defaultUnitForTagAttribute = 'default'
const defaultUnitsForUnitClassAttribute = 'defaultUnits'
const extensionAllowedAttribute = 'extensionAllowed'
const tagsDictionaryKey = 'tags'
const takesValueType = 'takesValue'
const unitClassType = 'unitClass'
const unitClassUnitsType = 'units'
const unitPrefixType = 'unitPrefix'
const unitSymbolType = 'unitSymbol'
const SIUnitKey = 'SIUnit'
const SIUnitModifierKey = 'SIUnitModifier'
const SIUnitSymbolModifierKey = 'SIUnitSymbolModifier'

/**
 * Replace the end of a HED tag with a pound sign.
 */
const replaceTagNameWithPound = function (formattedTag) {
  const lastTagSlashIndex = formattedTag.lastIndexOf('/')
  if (lastTagSlashIndex !== -1) {
    return formattedTag.substring(0, lastTagSlashIndex) + '/#'
  } else {
    return '#'
  }
}

/**
 * Get the indices of all slashes in a HED tag.
 */
const getTagSlashIndices = function (tag) {
  const indices = []
  let i = -1
  while ((i = tag.indexOf('/', i + 1)) >= 0) {
    indices.push(i)
  }
  return indices
}

/**
 * Get the last part of a HED tag.
 *
 * @param {string} tag A HED tag
 * @param {string} character The character to use as a separator.
 * @return {string} The last part of the tag using the given separator.
 */
const getTagName = function (tag, character = '/') {
  const lastSlashIndex = tag.lastIndexOf(character)
  if (lastSlashIndex === -1) {
    return tag
  } else {
    return tag.substring(lastSlashIndex + 1)
  }
}

/**
 * Get the HED tag prefix (up to the last slash).
 */
const getParentTag = function (tag, character = '/') {
  const lastSlashIndex = tag.lastIndexOf(character)
  if (lastSlashIndex === -1) {
    return tag
  } else {
    return tag.substring(0, lastSlashIndex)
  }
}

const ancestorIterator = function* (tag) {
  while (tag.lastIndexOf('/') >= 0) {
    yield tag
    tag = getParentTag(tag)
  }
  yield tag
}

const isDescendantOf = function (tag, parent) {
  for (const ancestor of ancestorIterator(tag)) {
    if (ancestor === parent) {
      return true
    }
  }
  return false
}

/**
 * Determine the name of this group's definition.
 */
const getDefinitionName = function (formattedTag, definitionForm) {
  let tag = formattedTag
  let value = getTagName(tag)
  let previousValue
  for (const level of ancestorIterator(tag)) {
    if (value === definitionForm.toLowerCase()) {
      return previousValue
    }
    previousValue = value
    value = getTagName(level)
  }
  throw Error(
    `Completed iteration through ${definitionForm.toLowerCase()} tag without finding ${definitionForm} level.`,
  )
}

const hed2ValidValueCharacters = /^[-a-zA-Z0-9.$%^+_; :]+$/
const hed3ValidValueCharacters = /^[-a-zA-Z0-9.$%^+_; ]+$/
/**
 * Determine if a stripped value is valid.
 */
const validateValue = function (value, isNumeric, isHed3) {
  if (value === '#') {
    return true
  }
  if (isNumeric) {
    return isNumber(value)
  }
  if (isHed3) {
    return hed3ValidValueCharacters.test(value)
  } else {
    return hed2ValidValueCharacters.test(value)
  }
}

/**
 * Determine whether a unit is a valid prefix unit.
 *
 * @param {string} unit A unit string.
 * @param {SchemaAttributes} hedSchemaAttributes The collection of schema attributes.
 * @return {boolean} Whether the unit is a valid prefix unit.
 */
const isPrefixUnit = function (unit, hedSchemaAttributes) {
  if (unitPrefixType in hedSchemaAttributes.unitAttributes) {
    return hedSchemaAttributes.unitAttributes[unitPrefixType][unit] || false
  } else {
    return unit === '$'
  }
}

/**
 * Get the list of valid derivatives of a unit.
 *
 * @param {string} unit A unit string.
 * @param {SchemaAttributes} hedSchemaAttributes The collection of schema attributes.
 * @return {string[]} The list of valid derivative units.
 */
const getValidDerivativeUnits = function (unit, hedSchemaAttributes) {
  const pluralUnits = [unit]
  const isUnitSymbol =
    hedSchemaAttributes.unitAttributes[unitSymbolType][unit] !== undefined
  if (hedSchemaAttributes.hasUnitModifiers && !isUnitSymbol) {
    pluralUnits.push(pluralize.plural(unit))
  }
  const isSIUnit =
    hedSchemaAttributes.unitAttributes[SIUnitKey][unit] !== undefined
  if (isSIUnit && hedSchemaAttributes.hasUnitModifiers) {
    const derivativeUnits = [].concat(pluralUnits)
    const modifierKey = isUnitSymbol
      ? SIUnitSymbolModifierKey
      : SIUnitModifierKey
    for (const unitModifier in hedSchemaAttributes.unitModifiers[modifierKey]) {
      for (const plural of pluralUnits) {
        derivativeUnits.push(unitModifier + plural)
      }
    }
    return derivativeUnits
  } else {
    return pluralUnits
  }
}

/**
 * Validate a unit and strip it from the value.
 * @param {string} originalTagUnitValue The unformatted version of the value.
 * @param {string[]} tagUnitClassUnits The list of valid units for this tag.
 * @param {SchemaAttributes} hedSchemaAttributes The collection of schema attributes.
 * @return {[boolean, boolean, string]} Whether a unit was found, whether it was valid, and the stripped value.
 */
const validateUnits = function (
  originalTagUnitValue,
  tagUnitClassUnits,
  hedSchemaAttributes,
) {
  const validUnits = getAllUnits(hedSchemaAttributes)
  validUnits.sort((first, second) => {
    return second.length - first.length
  })
  let actualUnit = getTagName(originalTagUnitValue, ' ')
  let noUnitFound = false
  if (actualUnit === originalTagUnitValue) {
    actualUnit = ''
    noUnitFound = true
  }
  let foundUnit, foundWrongCaseUnit, strippedValue
  for (const unit of validUnits) {
    const isUnitSymbol =
      hedSchemaAttributes.unitAttributes[unitSymbolType][unit] !== undefined
    const derivativeUnits = getValidDerivativeUnits(unit, hedSchemaAttributes)
    for (const derivativeUnit of derivativeUnits) {
      if (
        isPrefixUnit(unit, hedSchemaAttributes) &&
        originalTagUnitValue.startsWith(derivativeUnit)
      ) {
        foundUnit = true
        noUnitFound = false
        strippedValue = originalTagUnitValue
          .substring(derivativeUnit.length)
          .trim()
      }
      if (actualUnit === derivativeUnit) {
        foundUnit = true
        strippedValue = getParentTag(originalTagUnitValue, ' ')
      } else if (actualUnit.toLowerCase() === derivativeUnit.toLowerCase()) {
        if (isUnitSymbol) {
          foundWrongCaseUnit = true
        } else {
          foundUnit = true
        }
        strippedValue = getParentTag(originalTagUnitValue, ' ')
      }
      if (foundUnit) {
        const unitIsValid = tagUnitClassUnits.includes(unit)
        return [true, unitIsValid, strippedValue]
      }
    }
    if (foundWrongCaseUnit) {
      return [true, false, strippedValue]
    }
  }
  return [!noUnitFound, false, originalTagUnitValue]
}

/**
 * Determine if a HED tag is in the schema.
 */
const tagExistsInSchema = function (formattedTag, hedSchemaAttributes) {
  return hedSchemaAttributes.tags.includes(formattedTag)
}

/**
 * Checks if a HED tag has the 'takesValue' attribute.
 */
const tagTakesValue = function (formattedTag, hedSchemaAttributes, isHed3) {
  if (isHed3) {
    for (const ancestor of ancestorIterator(formattedTag)) {
      const takesValueTag = replaceTagNameWithPound(ancestor)
      if (hedSchemaAttributes.tagHasAttribute(takesValueTag, takesValueType)) {
        return true
      }
    }
    return false
  } else {
    const takesValueTag = replaceTagNameWithPound(formattedTag)
    return hedSchemaAttributes.tagHasAttribute(takesValueTag, takesValueType)
  }
}

/**
 * Checks if a HED tag has the 'unitClass' attribute.
 */
const isUnitClassTag = function (formattedTag, hedSchemaAttributes) {
  if (!hedSchemaAttributes.hasUnitClasses) {
    return false
  }
  const takesValueTag = replaceTagNameWithPound(formattedTag)
  return takesValueTag in hedSchemaAttributes.tagUnitClasses
}

/**
 * Get the default unit for a particular HED tag.
 */
const getUnitClassDefaultUnit = function (formattedTag, hedSchemaAttributes) {
  if (isUnitClassTag(formattedTag, hedSchemaAttributes)) {
    const unitClassTag = replaceTagNameWithPound(formattedTag)
    let hasDefaultAttribute = hedSchemaAttributes.tagHasAttribute(
      unitClassTag,
      defaultUnitForTagAttribute,
    )
    // TODO: New versions of the spec have defaultUnits instead of default.
    if (hasDefaultAttribute === null) {
      hasDefaultAttribute = hedSchemaAttributes.tagHasAttribute(
        unitClassTag,
        defaultUnitsForUnitClassAttribute,
      )
    }
    if (hasDefaultAttribute) {
      return hedSchemaAttributes.tagAttributes[defaultUnitForTagAttribute][
        unitClassTag
      ]
    } else if (unitClassTag in hedSchemaAttributes.tagUnitClasses) {
      const unitClasses = hedSchemaAttributes.tagUnitClasses[unitClassTag]
      const firstUnitClass = unitClasses[0]
      return hedSchemaAttributes.unitClassAttributes[firstUnitClass][
        defaultUnitsForUnitClassAttribute
      ][0]
    }
  } else {
    return ''
  }
}

/**
 * Get the unit classes for a particular HED tag.
 */
const getTagUnitClasses = function (formattedTag, hedSchemaAttributes) {
  if (isUnitClassTag(formattedTag, hedSchemaAttributes)) {
    const unitClassTag = replaceTagNameWithPound(formattedTag)
    return hedSchemaAttributes.tagUnitClasses[unitClassTag]
  } else {
    return []
  }
}

/**
 * Get the legal units for a particular HED tag.
 */
const getTagUnitClassUnits = function (formattedTag, hedSchemaAttributes) {
  const tagUnitClasses = getTagUnitClasses(formattedTag, hedSchemaAttributes)
  const units = []
  for (const unitClass of tagUnitClasses) {
    const unitClassUnits = hedSchemaAttributes.unitClasses[unitClass]
    Array.prototype.push.apply(units, unitClassUnits)
  }
  return units
}

/**
 * Get the legal units for a particular HED tag.
 */
const getAllUnits = function (hedSchemaAttributes) {
  const units = []
  for (const unitClass in hedSchemaAttributes.unitClasses) {
    const unitClassUnits = hedSchemaAttributes.unitClasses[unitClass]
    Array.prototype.push.apply(units, unitClassUnits)
  }
  return units
}

/**
 * Check if any level of a HED tag allows extensions.
 */
const isExtensionAllowedTag = function (formattedTag, hedSchemaAttributes) {
  if (
    hedSchemaAttributes.tagHasAttribute(formattedTag, extensionAllowedAttribute)
  ) {
    return true
  }
  const tagSlashIndices = getTagSlashIndices(formattedTag)
  for (const tagSlashIndex of tagSlashIndices) {
    const tagSubstring = formattedTag.slice(0, tagSlashIndex)
    if (
      hedSchemaAttributes.tagHasAttribute(
        tagSubstring,
        extensionAllowedAttribute,
      )
    ) {
      return true
    }
  }
  return false
}

module.exports = {
  replaceTagNameWithPound: replaceTagNameWithPound,
  getTagSlashIndices: getTagSlashIndices,
  getTagName: getTagName,
  getParentTag: getParentTag,
  ancestorIterator: ancestorIterator,
  isDescendantOf: isDescendantOf,
  getDefinitionName: getDefinitionName,
  validateValue: validateValue,
  validateUnits: validateUnits,
  tagExistsInSchema: tagExistsInSchema,
  tagTakesValue: tagTakesValue,
  isUnitClassTag: isUnitClassTag,
  getUnitClassDefaultUnit: getUnitClassDefaultUnit,
  getTagUnitClasses: getTagUnitClasses,
  getTagUnitClassUnits: getTagUnitClassUnits,
  isExtensionAllowedTag: isExtensionAllowedTag,
}
