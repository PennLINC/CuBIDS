const assert = require('assert')
const utils = require('../')

describe('String utility functions', () => {
  describe('Blank strings', () => {
    it('may be empty', () => {
      const emptyString = ''
      const result = utils.string.stringIsEmpty(emptyString)
      assert.strictEqual(result, true)
    })

    it('may have only whitespace', () => {
      const spaceString = ' \n  \t  '
      const result = utils.string.stringIsEmpty(spaceString)
      assert.strictEqual(result, true)
    })

    it('may not contain letters', () => {
      const aString = 'a'
      const result = utils.string.stringIsEmpty(aString)
      assert.strictEqual(result, false)
    })

    it('may not contain numbers', () => {
      const oneString = '1'
      const result = utils.string.stringIsEmpty(oneString)
      assert.strictEqual(result, false)
    })

    it('may not contain punctuation', () => {
      const slashString = '/'
      const result = utils.string.stringIsEmpty(slashString)
      assert.strictEqual(result, false)
    })
  })

  describe('Capitalized strings', () => {
    it('must have a capitalized first letter', () => {
      const testString = 'to be'
      const result = utils.string.capitalizeString(testString)
      assert.strictEqual(result, 'To be')
    })

    it('must not change letters after the first letter', () => {
      const testString = 'to BE or NOT to BE'
      const result = utils.string.capitalizeString(testString)
      assert.strictEqual(result, 'To BE or NOT to BE')
    })
  })

  describe('Character counts', () => {
    it('must be correct', () => {
      const testString = 'abcabcaaabccccdddfdddd'
      const resultA = utils.string.getCharacterCount(testString, 'a')
      const resultB = utils.string.getCharacterCount(testString, 'b')
      const resultC = utils.string.getCharacterCount(testString, 'c')
      const resultD = utils.string.getCharacterCount(testString, 'd')
      const resultE = utils.string.getCharacterCount(testString, 'e')
      const resultF = utils.string.getCharacterCount(testString, 'f')
      assert.strictEqual(resultA, 5)
      assert.strictEqual(resultB, 3)
      assert.strictEqual(resultC, 6)
      assert.strictEqual(resultD, 7)
      assert.strictEqual(resultE, 0)
      assert.strictEqual(resultF, 1)
    })
  })

  describe('Valid HED times', () => {
    it('must be of the form HH:MM or HH:MM:SS', () => {
      const validTestStrings = {
        validPM: '23:52',
        validMidnight: '00:55',
        validHour: '11:00',
        validSingleDigitHour: '08:30',
        validSeconds: '19:33:47',
      }
      const invalidTestStrings = {
        invalidDate: '8/8/2019',
        invalidHour: '25:11',
        invalidSingleDigitHour: '8:30',
        invalidMinute: '12:65',
        invalidSecond: '15:45:82',
        invalidTimeZone: '16:25:51+00:00',
        invalidMilliseconds: '17:31:05.123',
        invalidMicroseconds: '09:21:16.123456',
        invalidDateTime: '2000-01-01T00:55:00',
        invalidString: 'not a time',
      }
      for (const key in validTestStrings) {
        const string = validTestStrings[key]
        const result = utils.string.isClockFaceTime(string)
        assert.strictEqual(result, true, string)
      }
      for (const key in invalidTestStrings) {
        const string = invalidTestStrings[key]
        const result = utils.string.isClockFaceTime(string)
        assert.strictEqual(result, false, string)
      }
    })
  })

  describe('Valid HED date-times', () => {
    it('must be in ISO 8601 format', () => {
      const validTestStrings = {
        validPM: '2000-01-01T23:52:00',
        validMidnight: '2000-01-01T00:55:00',
        validHour: '2000-01-01T11:00:00',
        validSingleDigitHour: '2000-01-01T08:30:00',
        validSeconds: '2000-01-01T19:33:47',
        validMilliseconds: '2000-01-01T17:31:05.123',
        validMicroseconds: '2000-01-01T09:21:16.123456',
      }
      const invalidTestStrings = {
        invalidDate: '8/8/2019',
        invalidTime: '00:55:00',
        invalidHour: '2000-01-01T25:11',
        invalidSingleDigitHour: '2000-01-01T8:30',
        invalidMinute: '2000-01-01T12:65',
        invalidSecond: '2000-01-01T15:45:82',
        invalidTimeZone: '2000-01-01T16:25:51+00:00',
        invalidString: 'not a time',
      }
      for (const key in validTestStrings) {
        const string = validTestStrings[key]
        const result = utils.string.isDateTime(string)
        assert.strictEqual(result, true, string)
      }
      for (const key in invalidTestStrings) {
        const string = invalidTestStrings[key]
        const result = utils.string.isDateTime(string)
        assert.strictEqual(result, false, string)
      }
    })
  })

  describe('Valid HED numbers', () => {
    it('must be in scientific notation', () => {
      const validTestStrings = {
        validPositiveInteger: '21',
        validNegativeInteger: '-500',
        validPositiveDecimal: '8520.63',
        validNegativeDecimal: '-945.61',
        validPositiveFractional: '0.84',
        validNegativeFractional: '-0.61',
        validPositiveScientificInteger: '21e10',
        validNegativeScientificInteger: '-500E-5',
        validPositiveScientificDecimal: '8520.63E15',
        validNegativeScientificDecimal: '-945.61e-3',
        validPositiveScientificFractional: '0.84e-2',
        validNegativeScientificFractional: '-0.61E5',
      }
      const invalidTestStrings = {
        invalidDecimalPoint: '.',
        invalidMultipleDecimalPoints: '22.88.66',
        invalidMultipleEs: '888ee66',
        invalidStartCharacter: 'e77e6',
        invalidBlankExponent: '432e',
        invalidBlankNegativeExponent: '1853e-',
        invalidStartingDecimalPoint: '.852',
        invalidEndingDecimalPoint: '851695.',
        invalidOtherCharacter: '81468g516',
      }
      for (const key in validTestStrings) {
        const string = validTestStrings[key]
        const result = utils.string.isNumber(string)
        assert.strictEqual(result, true, string)
      }
      for (const key in invalidTestStrings) {
        const string = invalidTestStrings[key]
        const result = utils.string.isNumber(string)
        assert.strictEqual(result, false, string)
      }
    })
  })
})
