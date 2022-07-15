const assert = require('chai').assert
const splitHedString = require('../splitHedString')

describe('HED string delimiter splitting', () => {
  /**
   * Validation function.
   *
   * @param {Object<string, string>} testStrings The test strings.
   * @param {Object<string, string>} expectedResults The expected results.
   */
  const validator = function(testStrings, expectedResults) {
    for (const testStringKey in testStrings) {
      const testString = testStrings[testStringKey]
      const testResult = splitHedString(testString)
      const testResultParts = testResult.map(
        ([, [startPosition, endPosition]]) => {
          return testString.slice(startPosition, endPosition)
        },
      )
      assert.deepStrictEqual(
        testResultParts,
        expectedResults[testStringKey],
        testStrings[testStringKey],
      )
    }
  }

  it('should property split a HED string into tags and delimiters', () => {
    const testStrings = {
      single: 'Event',
      double: 'Event, Event/Extension',
      singleAndGroup: 'Event/Extension, (Event/Extension2, Event/Extension3)',
      singleAndGroupWithBlank: 'Event/Extension, (Event, ,Event/Extension3)',
      manyParens: 'Event/Extension,(((((Event/Extension2, )(Event)',
      manyParensEndingSpace: 'Event/Extension,(((((Event/Extension2, )(Event) ',
      manyParensOpeningSpace:
        ' Event/Extension,(((((Event/Extension2, )(Event)',
      manyParensBothSpace: ' Event/Extension,(((((Event/Extension2, )(Event ',
    }
    const expectedResults = {
      single: ['Event'],
      double: ['Event', ', ', 'Event/Extension'],
      singleAndGroup: [
        'Event/Extension',
        ', (',
        'Event/Extension2',
        ', ',
        'Event/Extension3',
        ')',
      ],
      singleAndGroupWithBlank: [
        'Event/Extension',
        ', (',
        'Event',
        ', ,',
        'Event/Extension3',
        ')',
      ],
      manyParens: [
        'Event/Extension',
        ',(((((',
        'Event/Extension2',
        ', )(',
        'Event',
        ')',
      ],
      manyParensEndingSpace: [
        'Event/Extension',
        ',(((((',
        'Event/Extension2',
        ', )(',
        'Event',
        ') ',
      ],
      manyParensOpeningSpace: [
        ' ',
        'Event/Extension',
        ',(((((',
        'Event/Extension2',
        ', )(',
        'Event',
        ')',
      ],
      manyParensBothSpace: [
        ' ',
        'Event/Extension',
        ',(((((',
        'Event/Extension2',
        ', )(',
        'Event',
        ' ',
      ],
    }
    return validator(testStrings, expectedResults)
  })
})
