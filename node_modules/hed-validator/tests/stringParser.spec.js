const assert = require('chai').assert
const { Schemas } = require('../utils/schema')
const { buildSchema } = require('../converter/schema')
const {
  ParsedHedTag,
  formatHedTag,
  hedStringIsAGroup,
  parseHedString,
  removeGroupParentheses,
  splitHedString,
} = require('../validator/stringParser')
const generateIssue = require('../utils/issues/issues').generateIssue

describe('HED string parsing', () => {
  const nullSchema = new Schemas(null)
  const originalMap = (parsedTag) => {
    return parsedTag.originalTag
  }

  const hedSchemaFile = 'tests/data/HED8.0.0-alpha.1.xml'
  let hedSchemaPromise

  beforeAll(() => {
    hedSchemaPromise = buildSchema({
      path: hedSchemaFile,
    })
  })

  const validatorWithoutIssues = function (
    testStrings,
    expectedResults,
    testFunction,
  ) {
    for (const testStringKey in testStrings) {
      const testResult = testFunction(testStrings[testStringKey])
      assert.deepStrictEqual(
        testResult,
        expectedResults[testStringKey],
        testStrings[testStringKey],
      )
    }
  }

  const validatorWithIssues = function (
    testStrings,
    expectedResults,
    expectedIssues,
    testFunction,
  ) {
    for (const testStringKey in testStrings) {
      const [testResult, testIssues] = testFunction(testStrings[testStringKey])
      assert.sameDeepMembers(
        testResult,
        expectedResults[testStringKey],
        testStrings[testStringKey],
      )
      assert.sameDeepMembers(
        testIssues,
        expectedIssues[testStringKey],
        testStrings[testStringKey],
      )
    }
  }

  describe('HED strings', () => {
    it('cannot have invalid characters', () => {
      const testStrings = {
        openingCurly:
          '/Attribute/Object side/Left,/Participant/Effect{/Body part/Arm',
        closingCurly:
          '/Attribute/Object side/Left,/Participant/Effect}/Body part/Arm',
        openingSquare:
          '/Attribute/Object side/Left,/Participant/Effect[/Body part/Arm',
        closingSquare:
          '/Attribute/Object side/Left,/Participant/Effect]/Body part/Arm',
        tilde: '/Attribute/Object side/Left,/Participant/Effect~/Body part/Arm',
      }
      const expectedResultList = [
        new ParsedHedTag(
          '/Attribute/Object side/Left',
          '/Attribute/Object side/Left',
          [0, 27],
          nullSchema,
        ),
        new ParsedHedTag(
          '/Participant/Effect',
          '/Participant/Effect',
          [28, 47],
          nullSchema,
        ),
        new ParsedHedTag(
          '/Body part/Arm',
          '/Body part/Arm',
          [48, 62],
          nullSchema,
        ),
      ]
      const expectedResults = {
        openingCurly: expectedResultList,
        closingCurly: expectedResultList,
        openingSquare: expectedResultList,
        closingSquare: expectedResultList,
        tilde: expectedResultList,
      }
      const expectedIssues = {
        openingCurly: [
          generateIssue('invalidCharacter', {
            character: '{',
            index: 47,
            string: testStrings.openingCurly,
          }),
        ],
        closingCurly: [
          generateIssue('invalidCharacter', {
            character: '}',
            index: 47,
            string: testStrings.closingCurly,
          }),
        ],
        openingSquare: [
          generateIssue('invalidCharacter', {
            character: '[',
            index: 47,
            string: testStrings.openingSquare,
          }),
        ],
        closingSquare: [
          generateIssue('invalidCharacter', {
            character: ']',
            index: 47,
            string: testStrings.closingSquare,
          }),
        ],
        tilde: [
          generateIssue('invalidCharacter', {
            character: '~',
            index: 47,
            string: testStrings.tilde,
          }),
        ],
      }
      validatorWithIssues(
        testStrings,
        expectedResults,
        expectedIssues,
        (string) => {
          return splitHedString(string, nullSchema)
        },
      )
    })
  })

  describe('HED tag groups', () => {
    it('must be surrounded by parentheses', () => {
      const testStrings = {
        group:
          '(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm)',
        nonGroup:
          '/Attribute/Object side/Left,/Participant/Effect/Body part/Arm',
      }
      const expectedResults = {
        group: true,
        nonGroup: false,
      }
      validatorWithoutIssues(testStrings, expectedResults, (string) => {
        return hedStringIsAGroup(string)
      })
    })

    it('can have its parentheses removed', () => {
      const testStrings = {
        group:
          '(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm)',
      }
      const expectedResults = {
        group: '/Attribute/Object side/Left,/Participant/Effect/Body part/Arm',
      }
      validatorWithoutIssues(testStrings, expectedResults, (string) => {
        return removeGroupParentheses(string)
      })
    })
  })

  describe('Lists of HED Tags', () => {
    it('should be an array', () => {
      const hedString =
        'Event/Category/Experimental stimulus,Item/Object/Vehicle/Train,Attribute/Visual/Color/Purple'
      const [result] = splitHedString(hedString, nullSchema)
      assert(result instanceof Array)
    })

    it('should include each top-level tag as its own single element', () => {
      const hedString =
        'Event/Category/Experimental stimulus,Item/Object/Vehicle/Train,Attribute/Visual/Color/Purple'
      const [result, issues] = splitHedString(hedString, nullSchema)
      assert.deepStrictEqual(issues, [])
      assert.deepStrictEqual(result, [
        new ParsedHedTag(
          'Event/Category/Experimental stimulus',
          'Event/Category/Experimental stimulus',
          [0, 36],
          nullSchema,
        ),
        new ParsedHedTag(
          'Item/Object/Vehicle/Train',
          'Item/Object/Vehicle/Train',
          [37, 62],
          nullSchema,
        ),
        new ParsedHedTag(
          'Attribute/Visual/Color/Purple',
          'Attribute/Visual/Color/Purple',
          [63, 92],
          nullSchema,
        ),
      ])
    })

    it('should include each group as its own single element', () => {
      const hedString =
        '/Action/Reach/To touch,(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm),/Attribute/Location/Screen/Top/70 px,/Attribute/Location/Screen/Left/23 px'
      const [result, issues] = splitHedString(hedString, nullSchema)
      assert.deepStrictEqual(issues, [])
      assert.deepStrictEqual(result, [
        new ParsedHedTag(
          '/Action/Reach/To touch',
          '/Action/Reach/To touch',
          [0, 22],
          nullSchema,
        ),
        new ParsedHedTag(
          '(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm)',
          '(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm)',
          [23, 86],
          nullSchema,
        ),
        new ParsedHedTag(
          '/Attribute/Location/Screen/Top/70 px',
          '/Attribute/Location/Screen/Top/70 px',
          [87, 123],
          nullSchema,
        ),
        new ParsedHedTag(
          '/Attribute/Location/Screen/Left/23 px',
          '/Attribute/Location/Screen/Left/23 px',
          [124, 161],
          nullSchema,
        ),
      ])
    })

    it('should not include double quotes', () => {
      const doubleQuoteString =
        'Event/Category/Experimental stimulus,"Item/Object/Vehicle/Train",Attribute/Visual/Color/Purple'
      const normalString =
        'Event/Category/Experimental stimulus,Item/Object/Vehicle/Train,Attribute/Visual/Color/Purple'
      const [doubleQuoteResult, doubleQuoteIssues] = splitHedString(
        doubleQuoteString,
        nullSchema,
      )
      const [normalResult, normalIssues] = splitHedString(
        normalString,
        nullSchema,
      )
      assert.deepStrictEqual(doubleQuoteIssues, [])
      assert.deepStrictEqual(normalIssues, [])
      const noBoundsMap = (parsedTag) => {
        return {
          canonicalTag: parsedTag.canonicalTag,
          formattedTag: parsedTag.formattedTag,
          originalTag: parsedTag.originalTag,
        }
      }
      const doubleQuoteResultNoBounds = doubleQuoteResult.map(noBoundsMap)
      const normalResultNoBounds = normalResult.map(noBoundsMap)
      assert.deepStrictEqual(doubleQuoteResultNoBounds, normalResultNoBounds)
    })

    it('should not include blanks', () => {
      const testStrings = {
        doubleComma:
          '/Item/Object/Vehicle/Car,,/Attribute/Object control/Perturb',
        doubleInvalidCharacter:
          '/Item/Object/Vehicle/Car[]/Attribute/Object control/Perturb',
        trailingBlank:
          '/Item/Object/Vehicle/Car, /Attribute/Object control/Perturb,',
      }
      const expectedList = [
        new ParsedHedTag(
          '/Item/Object/Vehicle/Car',
          '/Item/Object/Vehicle/Car',
          [0, 24],
          nullSchema,
        ),
        new ParsedHedTag(
          '/Attribute/Object control/Perturb',
          '/Attribute/Object control/Perturb',
          [26, 59],
          nullSchema,
        ),
      ]
      const expectedResults = {
        doubleComma: expectedList,
        doubleInvalidCharacter: expectedList,
        trailingBlank: expectedList,
      }
      const expectedIssues = {
        doubleComma: [],
        doubleInvalidCharacter: [
          generateIssue('invalidCharacter', {
            character: '[',
            index: 24,
            string: testStrings.doubleInvalidCharacter,
          }),
          generateIssue('invalidCharacter', {
            character: ']',
            index: 25,
            string: testStrings.doubleInvalidCharacter,
          }),
        ],
        trailingBlank: [],
      }
      validatorWithIssues(
        testStrings,
        expectedResults,
        expectedIssues,
        (string) => {
          return splitHedString(string, nullSchema)
        },
      )
    })
  })

  describe('Formatted HED Tags', () => {
    it('should be lowercase and not have leading or trailing double quotes or slashes', () => {
      // Correct formatting
      const formattedHedTag = 'event/category/experimental stimulus'
      const testStrings = {
        formatted: formattedHedTag,
        openingDoubleQuote: '"Event/Category/Experimental stimulus',
        closingDoubleQuote: 'Event/Category/Experimental stimulus"',
        openingAndClosingDoubleQuote: '"Event/Category/Experimental stimulus"',
        openingSlash: '/Event/Category/Experimental stimulus',
        closingSlash: 'Event/Category/Experimental stimulus/',
        openingAndClosingSlash: '/Event/Category/Experimental stimulus/',
        openingDoubleQuotedSlash: '"/Event/Category/Experimental stimulus',
        closingDoubleQuotedSlash: 'Event/Category/Experimental stimulus/"',
        openingSlashClosingDoubleQuote:
          '/Event/Category/Experimental stimulus"',
        closingSlashOpeningDoubleQuote:
          '"Event/Category/Experimental stimulus/',
        openingAndClosingDoubleQuotedSlash:
          '"/Event/Category/Experimental stimulus/"',
      }
      const expectedResults = {
        formatted: formattedHedTag,
        openingDoubleQuote: formattedHedTag,
        closingDoubleQuote: formattedHedTag,
        openingAndClosingDoubleQuote: formattedHedTag,
        openingSlash: formattedHedTag,
        closingSlash: formattedHedTag,
        openingAndClosingSlash: formattedHedTag,
        openingDoubleQuotedSlash: formattedHedTag,
        closingDoubleQuotedSlash: formattedHedTag,
        openingSlashClosingDoubleQuote: formattedHedTag,
        closingSlashOpeningDoubleQuote: formattedHedTag,
        openingAndClosingDoubleQuotedSlash: formattedHedTag,
      }
      validatorWithoutIssues(testStrings, expectedResults, (string) => {
        const parsedTag = new ParsedHedTag(string, string, [], nullSchema)
        formatHedTag(parsedTag)
        return parsedTag.formattedTag
      })
    })
  })

  describe('Parsed HED Tags', () => {
    it('must have the correct number of tags, top-level tags, and groups', () => {
      const hedString =
        '/Action/Reach/To touch,(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm),/Attribute/Location/Screen/Top/70 px,/Attribute/Location/Screen/Left/23 px'
      const [parsedString, issues] = parseHedString(hedString, nullSchema)
      assert.deepStrictEqual(issues, [])
      assert.sameDeepMembers(parsedString.tags.map(originalMap), [
        '/Action/Reach/To touch',
        '/Attribute/Object side/Left',
        '/Participant/Effect/Body part/Arm',
        '/Attribute/Location/Screen/Top/70 px',
        '/Attribute/Location/Screen/Left/23 px',
      ])
      assert.sameDeepMembers(parsedString.topLevelTags.map(originalMap), [
        '/Action/Reach/To touch',
        '/Attribute/Location/Screen/Top/70 px',
        '/Attribute/Location/Screen/Left/23 px',
      ])
      assert.sameDeepMembers(
        parsedString.tagGroups.map((group) => group.tags.map(originalMap)),
        [['/Attribute/Object side/Left', '/Participant/Effect/Body part/Arm']],
      )
    })

    it('must include properly formatted tags', () => {
      const hedString =
        '/Action/Reach/To touch,(/Attribute/Object side/Left,/Participant/Effect/Body part/Arm),/Attribute/Location/Screen/Top/70 px,/Attribute/Location/Screen/Left/23 px'
      const formattedHedString =
        'action/reach/to touch,(attribute/object side/left,participant/effect/body part/arm),attribute/location/screen/top/70 px,attribute/location/screen/left/23 px'
      const [parsedString, issues] = parseHedString(hedString, nullSchema)
      const [parsedFormattedString, formattedIssues] = parseHedString(
        formattedHedString,
        nullSchema,
      )
      const formattedMap = (parsedTag) => {
        return parsedTag.formattedTag
      }
      assert.deepStrictEqual(issues, [])
      assert.deepStrictEqual(formattedIssues, [])
      assert.deepStrictEqual(
        parsedString.tags.map(formattedMap),
        parsedFormattedString.tags.map(originalMap),
      )
      assert.deepStrictEqual(
        parsedString.topLevelTags.map(formattedMap),
        parsedFormattedString.topLevelTags.map(originalMap),
      )
    })
  })

  describe('Canonical HED tags', () => {
    it('should convert HED 3 tags into canonical form', () => {
      const testStrings = {
        simple: 'Car',
        groupAndTag: '(Train, RGB-red/0.5), Car',
      }
      const expectedResults = {
        simple: ['Item/Object/Man-made-object/Vehicle/Car'],
        groupAndTag: [
          'Item/Object/Man-made-object/Vehicle/Train',
          'Attribute/Sensory/Visual/Color/RGB-color/RGB-red/0.5',
          'Item/Object/Man-made-object/Vehicle/Car',
        ],
      }
      const expectedIssues = {
        simple: [],
        groupAndTag: [],
      }
      return hedSchemaPromise.then((hedSchema) => {
        return validatorWithIssues(
          testStrings,
          expectedResults,
          expectedIssues,
          (string) => {
            const [parsedString, issues] = parseHedString(string, hedSchema)
            const canonicalTags = parsedString.tags.map((parsedTag) => {
              return parsedTag.canonicalTag
            })
            return [canonicalTags, issues]
          },
        )
      })
    })
  })
})
