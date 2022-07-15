const assert = require('chai').assert
const hed = require('../hed')
const schema = require('../../validator/schema')

describe('HED tag string utility functions', () => {
  describe('Syntactic utility functions', () => {
    const validator = function (testStrings, expectedResults, testFunction) {
      for (const testStringKey in testStrings) {
        const testResult = testFunction(testStrings[testStringKey])
        assert.deepStrictEqual(
          testResult,
          expectedResults[testStringKey],
          testStrings[testStringKey],
        )
      }
    }

    it('should properly replace tag values with the pound character', () => {
      const testStrings = {
        slash: 'Event/Duration/4 ms',
        noSlash: 'Something',
      }
      const expectedResults = {
        slash: 'Event/Duration/#',
        noSlash: '#',
      }
      validator(testStrings, expectedResults, (string) => {
        return hed.replaceTagNameWithPound(string)
      })
    })

    it('should detect the locations of slashes in a tag', () => {
      const testStrings = {
        description: 'Event/Description/Something',
        direction: 'Attribute/Direction/Left',
        noSlash: 'Something',
      }
      const expectedResults = {
        description: [5, 17],
        direction: [9, 19],
        noSlash: [],
      }
      validator(testStrings, expectedResults, (string) => {
        return hed.getTagSlashIndices(string)
      })
    })

    it('should extract the last part of a tag', () => {
      const testStrings = {
        description: 'Event/Description/Something',
        direction: 'Attribute/Direction/Left',
        noSlash: 'Participant',
      }
      const expectedResults = {
        description: 'Something',
        direction: 'Left',
        noSlash: 'Participant',
      }
      validator(testStrings, expectedResults, (string) => {
        return hed.getTagName(string)
      })
    })

    it('should extract the parent part of a tag', () => {
      const testStrings = {
        description: 'Event/Description/Something',
        direction: 'Attribute/Direction/Left',
        noSlash: 'Participant',
      }
      const expectedResults = {
        description: 'Event/Description',
        direction: 'Attribute/Direction',
        noSlash: 'Participant',
      }
      validator(testStrings, expectedResults, (string) => {
        return hed.getParentTag(string)
      })
    })

    it('should properly determine valid values', () => {
      const testStrings = {
        integer: '4',
        decimal: '21.2',
        scientific: '3.4e2',
        negative: '-9.5e-1',
        placeholder: '#',
        time: '22:45',
        name: 'abc',
        word: 'one',
        space: 'spaced out',
      }
      const expectedResultsHed2 = {
        integer: true,
        decimal: true,
        scientific: true,
        negative: true,
        placeholder: true,
        time: true,
        name: true,
        word: true,
        space: true,
      }
      const expectedResultsHed2Numeric = {
        integer: true,
        decimal: true,
        scientific: true,
        negative: true,
        placeholder: true,
        time: false,
        name: false,
        word: false,
        space: false,
      }
      const expectedResultsHed3 = {
        integer: true,
        decimal: true,
        scientific: true,
        negative: true,
        placeholder: true,
        time: false,
        name: true,
        word: true,
        space: true,
      }
      const expectedResultsHed3Numeric = {
        integer: true,
        decimal: true,
        scientific: true,
        negative: true,
        placeholder: true,
        time: false,
        name: false,
        word: false,
        space: false,
      }
      validator(testStrings, expectedResultsHed2, (string) => {
        return hed.validateValue(string, false, false)
      })
      validator(testStrings, expectedResultsHed2Numeric, (string) => {
        return hed.validateValue(string, true, false)
      })
      validator(testStrings, expectedResultsHed3, (string) => {
        return hed.validateValue(string, false, true)
      })
      validator(testStrings, expectedResultsHed3Numeric, (string) => {
        return hed.validateValue(string, true, true)
      })
    })
  })

  const localHedSchemaFile = 'tests/data/HED7.1.1.xml'

  describe('HED tag schema-based utility functions', () => {
    let hedSchemaPromise

    beforeAll(() => {
      hedSchemaPromise = schema.buildSchema({
        path: localHedSchemaFile,
      })
    })

    const validatorString = function (
      testStrings,
      expectedResults,
      testFunction,
    ) {
      return hedSchemaPromise.then((schema) => {
        for (const testStringKey in testStrings) {
          const testResult = testFunction(testStrings[testStringKey], schema)
          assert.strictEqual(
            testResult,
            expectedResults[testStringKey],
            testStrings[testStringKey],
          )
        }
      })
    }

    const validatorList = function (
      testStrings,
      expectedResults,
      testFunction,
    ) {
      return hedSchemaPromise.then((schema) => {
        for (const testStringKey in testStrings) {
          const testResult = testFunction(testStrings[testStringKey], schema)
          assert.sameDeepMembers(
            testResult,
            expectedResults[testStringKey],
            testStrings[testStringKey],
          )
        }
      })
    }

    it('should correctly determine if a tag exists', () => {
      const testStrings = {
        direction: 'attribute/direction/left',
        person: 'item/object/person',
        validPound: 'event/duration/#',
        missingTopLevel: 'something',
        missingSub: 'attribute/nothing',
        missingValue: 'participant/#',
      }
      const expectedResults = {
        direction: true,
        person: true,
        validPound: false,
        missingTopLevel: false,
        missingSub: false,
        missingValue: false,
      }
      return validatorString(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.tagExistsInSchema(string, hedSchemas.baseSchema.attributes)
        },
      )
    })

    it('should correctly determine if a tag takes a value', () => {
      const testStrings = {
        direction: 'attribute/direction/left/35 px',
        eventId: 'event/id/35',
        validPound: 'event/duration/#',
        topLevel: 'something',
        noValueSub: 'attribute/color/black',
        noValuePound: 'participant/#',
      }
      const expectedResults = {
        direction: true,
        eventId: true,
        validPound: true,
        topLevel: false,
        noValueSub: false,
        noValuePound: false,
      }
      return validatorString(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.tagTakesValue(
            string,
            hedSchemas.baseSchema.attributes,
            false,
          )
        },
      )
    })

    it('should correctly determine if a tag has a unit class', () => {
      const testStrings = {
        suffixed: 'attribute/direction/left/35 px',
        prefixed: 'participant/effect/cognitive/reward/$10.55',
        unitClassPound: 'event/duration/#',
        topLevel: 'something',
        noUnitClassValue: 'attribute/color/red/0.5',
        noUnitClassPound: 'participant/#',
      }
      const expectedResults = {
        suffixed: true,
        prefixed: true,
        unitClassPound: true,
        topLevel: false,
        noUnitClassValue: false,
        noUnitClassPound: false,
      }
      return validatorString(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.isUnitClassTag(string, hedSchemas.baseSchema.attributes)
        },
      )
    })

    it("should correctly determine a tag's default unit, if any", () => {
      const testStrings = {
        suffixed: 'attribute/blink/duration/35 ms',
        prefixed: 'participant/effect/cognitive/reward/$10.55',
        suffixedWithPrefixDefault:
          'participant/effect/cognitive/reward/11 dollars',
        unitClassPound: 'event/duration/#',
        noUnitClassValue: 'attribute/color/red/0.5',
        noValue: 'attribute/color/black',
        noValuePound: 'participant/#',
      }
      const expectedResults = {
        suffixed: 's',
        prefixed: '$',
        suffixedWithPrefixDefault: '$',
        unitClassPound: 's',
        noUnitClassValue: '',
        noValue: '',
        noValuePound: '',
      }
      return validatorString(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.getUnitClassDefaultUnit(
            string,
            hedSchemas.baseSchema.attributes,
          )
        },
      )
    })

    it("should correctly determine a tag's unit classes, if any", () => {
      const testStrings = {
        suffixed: 'attribute/direction/left/35 px',
        prefixed: 'participant/effect/cognitive/reward/$10.55',
        suffixedWithPrefixDefault:
          'participant/effect/cognitive/reward/11 dollars',
        unitClassPound: 'event/duration/#',
        noUnitClassValue: 'attribute/color/red/0.5',
        noValue: 'attribute/color/black',
        noValuePound: 'participant/#',
      }
      const expectedResults = {
        suffixed: ['angle', 'physicalLength', 'pixels'],
        prefixed: ['currency'],
        suffixedWithPrefixDefault: ['currency'],
        unitClassPound: ['time'],
        noUnitClassValue: [],
        noValue: [],
        noValuePound: [],
      }
      return validatorList(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.getTagUnitClasses(string, hedSchemas.baseSchema.attributes)
        },
      )
    })

    it("should correctly determine a tag's legal units, if any", () => {
      const testStrings = {
        suffixed: 'attribute/direction/left/35 px',
        prefixed: 'participant/effect/cognitive/reward/$10.55',
        suffixedWithPrefixDefault:
          'participant/effect/cognitive/reward/11 dollars',
        unitClassPound: 'event/duration/#',
        noUnitClassValue: 'attribute/color/red/0.5',
        noValue: 'attribute/color/black',
        noValuePound: 'participant/#',
      }
      const directionUnits = [
        'degree',
        'radian',
        'rad',
        'm',
        'foot',
        'metre',
        'mile',
        'px',
        'pixel',
      ]
      const currencyUnits = ['dollar', '$', 'point', 'fraction']
      const timeUnits = ['second', 's', 'day', 'minute', 'hour']
      const expectedResults = {
        suffixed: directionUnits,
        prefixed: currencyUnits,
        suffixedWithPrefixDefault: currencyUnits,
        unitClassPound: timeUnits,
        noUnitClassValue: [],
        noValue: [],
        noValuePound: [],
      }
      return validatorList(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.getTagUnitClassUnits(
            string,
            hedSchemas.baseSchema.attributes,
          )
        },
      )
    })

    it('should strip valid units from a value', () => {
      const dollarsString = '$25.99'
      const volumeString = '100 m^3'
      const prefixedVolumeString = '100 cm^3'
      const invalidVolumeString = '200 cm'
      const currencyUnits = ['dollars', '$', 'points', 'fraction']
      const volumeUnits = ['m^3']
      return hedSchemaPromise.then((hedSchemas) => {
        const strippedDollarsString = hed.validateUnits(
          dollarsString,
          currencyUnits,
          hedSchemas.baseSchema.attributes,
        )
        const strippedVolumeString = hed.validateUnits(
          volumeString,
          volumeUnits,
          hedSchemas.baseSchema.attributes,
        )
        const strippedPrefixedVolumeString = hed.validateUnits(
          prefixedVolumeString,
          volumeUnits,
          hedSchemas.baseSchema.attributes,
        )
        const strippedInvalidVolumeString = hed.validateUnits(
          invalidVolumeString,
          volumeUnits,
          hedSchemas.baseSchema.attributes,
        )
        assert.sameOrderedMembers(strippedDollarsString, [true, true, '25.99'])
        assert.sameOrderedMembers(strippedVolumeString, [true, true, '100'])
        assert.sameOrderedMembers(strippedPrefixedVolumeString, [
          true,
          true,
          '100',
        ])
        assert.sameOrderedMembers(strippedInvalidVolumeString, [
          true,
          false,
          '200',
        ])
      })
    })

    it('should correctly determine if a tag allows extensions', () => {
      const testStrings = {
        vehicle: 'item/object/vehicle/boat',
        color: 'attribute/color/red/0.5',
        noExtension: 'event/nonsense',
      }
      const expectedResults = {
        vehicle: true,
        color: true,
        noExtension: false,
      }
      return validatorString(
        testStrings,
        expectedResults,
        (string, hedSchemas) => {
          return hed.isExtensionAllowedTag(
            string,
            hedSchemas.baseSchema.attributes,
          )
        },
      )
    })
  })
})
