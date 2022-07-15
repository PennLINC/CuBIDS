const types = require('./types')
const TagEntry = types.TagEntry

const generateIssue = require('./issues')
const splitHedString = require('./splitHedString')

const doubleSlashPattern = /[\s/]*\/+[\s/]*/g

/**
 * Remove extra slashes and spaces from a HED string.
 *
 * @param {string} hedString The HED string to clean.
 * @return {string} The cleaned HED string.
 */
const removeSlashesAndSpaces = function (hedString) {
  return hedString.replace(doubleSlashPattern, '/')
}

/**
 * Convert a HED tag to long form.
 *
 * The seemingly redundant code for duplicate tag entries (which are errored out
 * on for HED 3 schemas) allow for similar HED 2 validation with minimal code
 * duplication.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} hedTag The HED tag to convert.
 * @param {string} hedString The full HED string (for error messages).
 * @param {number} offset The offset of this tag within the HED string.
 * @return {[string, Issue[]]} The long-form tag and any issues.
 */
const convertTagToLong = function (schemas, hedTag, hedString, offset) {
  const mapping = schemas.baseSchema.mapping

  if (hedTag.startsWith('/')) {
    hedTag = hedTag.slice(1)
  }
  if (hedTag.endsWith('/')) {
    hedTag = hedTag.slice(0, -1)
  }

  const cleanedTag = hedTag.toLowerCase()
  const splitTag = cleanedTag.split('/')

  /**
   * @type {TagEntry}
   */
  let foundTagEntry = null
  let endingIndex = 0
  let foundUnknownExtension = false
  let foundEndingIndex = 0

  for (const tag of splitTag) {
    if (endingIndex !== 0) {
      endingIndex++
    }
    const startingIndex = endingIndex
    endingIndex += tag.length

    if (!foundUnknownExtension) {
      if (!(tag in mapping.mappingData)) {
        foundUnknownExtension = true
        if (foundTagEntry === null) {
          return [
            hedTag,
            [
              generateIssue('invalidTag', hedString, {}, [
                startingIndex + offset,
                endingIndex + offset,
              ]),
            ],
          ]
        }
        continue
      }

      let tagEntries
      if (Array.isArray(mapping.mappingData[tag])) {
        tagEntries = mapping.mappingData[tag]
      } else {
        tagEntries = [mapping.mappingData[tag]]
      }
      let tagFound = false
      for (const tagEntry of tagEntries) {
        const tagString = tagEntry.longFormattedTag
        const mainHedPortion = cleanedTag.slice(0, endingIndex)

        if (!tagString.endsWith(mainHedPortion)) {
          continue
        }

        tagFound = true
        foundEndingIndex = endingIndex
        foundTagEntry = tagEntry
        break
      }
      if (!tagFound) {
        return [
          hedTag,
          [
            generateIssue(
              'invalidParentNode',
              hedString,
              {
                parentTag: Array.isArray(mapping.mappingData[tag])
                  ? mapping.mappingData[tag].map((tagEntry) => {
                      return tagEntry.longTag
                    })
                  : mapping.mappingData[tag].longTag,
              },
              [startingIndex + offset, endingIndex + offset],
            ),
          ],
        ]
      }
    } else if (tag in mapping.mappingData) {
      return [
        hedTag,
        [
          generateIssue(
            'invalidParentNode',
            hedString,
            {
              parentTag: Array.isArray(mapping.mappingData[tag])
                ? mapping.mappingData[tag].map((tagEntry) => {
                    return tagEntry.longTag
                  })
                : mapping.mappingData[tag].longTag,
            },
            [startingIndex + offset, endingIndex + offset],
          ),
        ],
      ]
    }
  }

  const remainder = hedTag.slice(foundEndingIndex)
  const longTagString = foundTagEntry.longTag + remainder
  return [longTagString, []]
}

/**
 * Convert a HED tag to short form.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} hedTag The HED tag to convert.
 * @param {string} hedString The full HED string (for error messages).
 * @param {number} offset The offset of this tag within the HED string.
 * @return {[string, Issue[]]} The short-form tag and any issues.
 */
const convertTagToShort = function (schemas, hedTag, hedString, offset) {
  const mapping = schemas.baseSchema.mapping

  if (hedTag.startsWith('/')) {
    hedTag = hedTag.slice(1)
  }
  if (hedTag.endsWith('/')) {
    hedTag = hedTag.slice(0, -1)
  }

  const cleanedTag = hedTag.toLowerCase()
  const splitTag = cleanedTag.split('/')
  splitTag.reverse()

  /**
   * @type {TagEntry}
   */
  let foundTagEntry = null
  let index = hedTag.length
  let lastFoundIndex = index

  for (const tag of splitTag) {
    if (tag in mapping.mappingData) {
      foundTagEntry = mapping.mappingData[tag]
      lastFoundIndex = index
      index -= tag.length
      break
    }

    lastFoundIndex = index
    index -= tag.length

    if (index !== 0) {
      index--
    }
  }

  if (foundTagEntry === null) {
    return [
      hedTag,
      [
        generateIssue('invalidTag', hedString, {}, [
          index + offset,
          lastFoundIndex + offset,
        ]),
      ],
    ]
  }

  const mainHedPortion = cleanedTag.slice(0, lastFoundIndex)
  const tagString = foundTagEntry.longFormattedTag
  if (!tagString.endsWith(mainHedPortion)) {
    return [
      hedTag,
      [
        generateIssue(
          'invalidParentNode',
          hedString,
          { parentTag: foundTagEntry.longTag },
          [index + offset, lastFoundIndex + offset],
        ),
      ],
    ]
  }

  const remainder = hedTag.slice(lastFoundIndex)
  const shortTagString = foundTagEntry.shortTag + remainder
  return [shortTagString, []]
}

/**
 * Convert a partial HED string to long form.
 *
 * This is for the internal string parsing for the validation side.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} partialHedString The partial HED string to convert to long form.
 * @param {string} fullHedString The full HED string.
 * @param {number} offset The offset of the partial HED string within the full string.
 * @return {[string, Issue[]]} The converted string and any issues.
 */
const convertPartialHedStringToLong = function (
  schemas,
  partialHedString,
  fullHedString,
  offset,
) {
  let issues = []

  const hedString = removeSlashesAndSpaces(partialHedString)

  if (hedString === '') {
    issues.push(generateIssue('emptyTagFound', ''))
    return [hedString, issues]
  }

  const hedTags = splitHedString(hedString)
  let finalString = ''

  for (const [isHedTag, [startPosition, endPosition]] of hedTags) {
    const tag = hedString.slice(startPosition, endPosition)
    if (isHedTag) {
      const [shortTagString, singleError] = convertTagToLong(
        schemas,
        tag,
        fullHedString,
        startPosition + offset,
      )
      issues = issues.concat(singleError)
      finalString += shortTagString
    } else {
      finalString += tag
    }
  }

  return [finalString, issues]
}

/**
 * Convert a HED string.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} hedString The HED tag to convert.
 * @param {function (Schemas, string, string, number): [string, Issue[]]} conversionFn The conversion function for a tag.
 * @return {[string, Issue[]]} The converted string and any issues.
 */
const convertHedString = function (schemas, hedString, conversionFn) {
  let issues = []

  if (!schemas.baseSchema.mapping.hasNoDuplicates) {
    issues.push(generateIssue('duplicateTagsInSchema', ''))
    return [hedString, issues]
  }

  hedString = removeSlashesAndSpaces(hedString)

  if (hedString === '') {
    issues.push(generateIssue('emptyTagFound', ''))
    return [hedString, issues]
  }

  const hedTags = splitHedString(hedString)
  let finalString = ''

  for (const [isHedTag, [startPosition, endPosition]] of hedTags) {
    const tag = hedString.slice(startPosition, endPosition)
    if (isHedTag) {
      const [shortTagString, singleError] = conversionFn(
        schemas,
        tag,
        hedString,
        startPosition,
      )
      issues = issues.concat(singleError)
      finalString += shortTagString
    } else {
      finalString += tag
    }
  }

  return [finalString, issues]
}

/**
 * Convert a HED string to long form.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} hedString The HED tag to convert.
 * @return {[string, Issue[]]} The long-form string and any issues.
 */
const convertHedStringToLong = function (schemas, hedString) {
  return convertHedString(schemas, hedString, convertTagToLong)
}

/**
 * Convert a HED string to short form.
 *
 * @param {Schemas} schemas The schema container object containing short-to-long mappings.
 * @param {string} hedString The HED tag to convert.
 * @return {[string, Issue[]]} The short-form string and any issues.
 */
const convertHedStringToShort = function (schemas, hedString) {
  return convertHedString(schemas, hedString, convertTagToShort)
}

module.exports = {
  convertHedStringToShort: convertHedStringToShort,
  convertHedStringToLong: convertHedStringToLong,
  convertPartialHedStringToLong: convertPartialHedStringToLong,
  convertTagToShort: convertTagToShort,
  convertTagToLong: convertTagToLong,
  removeSlashesAndSpaces: removeSlashesAndSpaces,
}
