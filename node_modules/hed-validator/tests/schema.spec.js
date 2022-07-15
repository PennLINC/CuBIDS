const assert = require('chai').assert
const schema = require('../validator/schema')
const schemaUtils = require('../utils/schema')

const fallbackHedSchemaVersion = '8.0.0'

describe('HED schemas', () => {
  describe('Remote HED schemas', () => {
    it('can be loaded from a central GitHub repository', () => {
      const remoteHedSchemaVersion = fallbackHedSchemaVersion
      return schema
        .buildSchema({ version: remoteHedSchemaVersion })
        .then((hedSchemas) => {
          const hedSchemaVersion = hedSchemas.baseSchema.version
          assert.strictEqual(hedSchemaVersion, remoteHedSchemaVersion)
        })
    })
  })

  describe('Local HED schemas', () => {
    const localHedSchemaFile = 'tests/data/HED7.1.1.xml'
    const localHedSchemaVersion = '7.1.1'
    it('can be loaded from a file', () => {
      return schema
        .buildSchema({ path: localHedSchemaFile })
        .then((hedSchemas) => {
          const hedSchemaVersion = hedSchemas.baseSchema.version
          assert.strictEqual(hedSchemaVersion, localHedSchemaVersion)
        })
    })
  })

  /*
  describe('Remote HED library schemas', function() {
    it('can be loaded from a central GitHub repository', function() {
      const remoteHedSchemaLibrary = 'test'
      const remoteHedSchemaVersion = '0.0.1'
      return schemaUtils
        .loadSchema({
          library: remoteHedSchemaLibrary,
          version: remoteHedSchemaVersion,
        })
        .then(hedSchema => {
          const schema = new schemaUtils.Schema(hedSchema)
          assert.strictEqual(schema.library, remoteHedSchemaLibrary)
          assert.strictEqual(schema.version, remoteHedSchemaVersion)
        })
    })
  })
  */

  describe('Fallback HED schemas', () => {
    it('loads the fallback schema if a remote schema cannot be found', () => {
      // Invalid base schema version
      const remoteHedSchemaVersion = '0.0.1'
      return schema
        .buildSchema({ version: remoteHedSchemaVersion })
        .then((hedSchemas) => {
          const hedSchemaVersion = hedSchemas.baseSchema.version
          assert.strictEqual(hedSchemaVersion, fallbackHedSchemaVersion)
        })
    })

    it('loads the fallback schema if a local schema cannot be found', () => {
      // Invalid base schema path
      const localHedSchemaFile = 'tests/data/HEDNotFound.xml'
      return schema
        .buildSchema({ path: localHedSchemaFile })
        .then((hedSchemas) => {
          const hedSchemaVersion = hedSchemas.baseSchema.version
          assert.strictEqual(hedSchemaVersion, fallbackHedSchemaVersion)
        })
    })
  })

  describe('HED-2G schemas', () => {
    const localHedSchemaFile = 'tests/data/HED7.1.1.xml'
    let hedSchemaPromise

    beforeAll(() => {
      hedSchemaPromise = schema.buildSchema({
        path: localHedSchemaFile,
      })
    })

    it('should have tag dictionaries for all required tag attributes', () => {
      const tagDictionaryKeys = [
        'default',
        'extensionAllowed',
        'isNumeric',
        'position',
        'predicateType',
        'recommended',
        'required',
        'requireChild',
        'takesValue',
        'unique',
      ]
      return hedSchemaPromise.then((hedSchemas) => {
        const dictionaries = hedSchemas.baseSchema.attributes.tagAttributes
        assert.hasAllKeys(dictionaries, tagDictionaryKeys)
      })
    })

    it('should have unit dictionaries for all required unit attributes', () => {
      const unitDictionaryKeys = ['SIUnit', 'unitSymbol']
      return hedSchemaPromise.then((hedSchemas) => {
        const dictionaries = hedSchemas.baseSchema.attributes.unitAttributes
        assert.hasAllKeys(dictionaries, unitDictionaryKeys)
      })
    })

    it('should contain all of the required tags', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const requiredTags = [
          'event/category',
          'event/description',
          'event/label',
        ]
        const dictionariesRequiredTags =
          hedSchemas.baseSchema.attributes.tagAttributes['required']
        assert.hasAllKeys(dictionariesRequiredTags, requiredTags)
      })
    })

    it('should contain all of the positioned tags', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const positionedTags = [
          'event/category',
          'event/description',
          'event/label',
          'event/long name',
        ]
        const dictionariesPositionedTags =
          hedSchemas.baseSchema.attributes.tagAttributes['position']
        assert.hasAllKeys(dictionariesPositionedTags, positionedTags)
      })
    })

    it('should contain all of the unique tags', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const uniqueTags = [
          'event/description',
          'event/label',
          'event/long name',
        ]
        const dictionariesUniqueTags =
          hedSchemas.baseSchema.attributes.tagAttributes['unique']
        assert.hasAllKeys(dictionariesUniqueTags, uniqueTags)
      })
    })

    it('should contain all of the tags with default units', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const defaultUnitTags = {
          'attribute/blink/time shut/#': 's',
          'attribute/blink/duration/#': 's',
          'attribute/blink/pavr/#': 'centiseconds',
          'attribute/blink/navr/#': 'centiseconds',
        }
        const dictionariesDefaultUnitTags =
          hedSchemas.baseSchema.attributes.tagAttributes['default']
        assert.deepStrictEqual(dictionariesDefaultUnitTags, defaultUnitTags)
      })
    })

    it('should contain all of the unit classes with their units and default units', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const defaultUnits = {
          acceleration: 'm-per-s^2',
          currency: '$',
          angle: 'radian',
          frequency: 'Hz',
          intensity: 'dB',
          jerk: 'm-per-s^3',
          luminousIntensity: 'cd',
          memorySize: 'B',
          physicalLength: 'm',
          pixels: 'px',
          speed: 'm-per-s',
          time: 's',
          clockTime: 'hour:min',
          dateTime: 'YYYY-MM-DDThh:mm:ss',
          area: 'm^2',
          volume: 'm^3',
        }
        const allUnits = {
          acceleration: ['m-per-s^2'],
          currency: ['dollar', '$', 'point', 'fraction'],
          angle: ['radian', 'rad', 'degree'],
          frequency: ['hertz', 'Hz'],
          intensity: ['dB'],
          jerk: ['m-per-s^3'],
          luminousIntensity: ['candela', 'cd'],
          memorySize: ['byte', 'B'],
          physicalLength: ['metre', 'm', 'foot', 'mile'],
          pixels: ['pixel', 'px'],
          speed: ['m-per-s', 'mph', 'kph'],
          time: ['second', 's', 'day', 'minute', 'hour'],
          clockTime: ['hour:min', 'hour:min:sec'],
          dateTime: ['YYYY-MM-DDThh:mm:ss'],
          area: ['m^2', 'px^2', 'pixel^2'],
          volume: ['m^3'],
        }

        const dictionariesUnitAttributes =
          hedSchemas.baseSchema.attributes.unitClassAttributes
        const dictionariesAllUnits =
          hedSchemas.baseSchema.attributes.unitClasses
        for (const unitClass in dictionariesUnitAttributes) {
          const defaultUnit = dictionariesUnitAttributes[unitClass].defaultUnits
          assert.deepStrictEqual(
            defaultUnit[0],
            defaultUnits[unitClass],
            `Default unit for unit class ${unitClass}`,
          )
        }
        assert.deepStrictEqual(dictionariesAllUnits, allUnits, 'All units')
      })
    })

    it('should contain the correct (large) numbers of tags with certain attributes', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const expectedAttributeTagCount = {
          isNumeric: 80,
          predicateType: 20,
          recommended: 0,
          requireChild: 64,
          takesValue: 119,
        }

        const dictionaries = hedSchemas.baseSchema.attributes.tagAttributes
        for (const attribute in expectedAttributeTagCount) {
          assert.lengthOf(
            Object.keys(dictionaries[attribute]),
            expectedAttributeTagCount[attribute],
            'Mismatch on attribute ' + attribute,
          )
        }

        const expectedTagCount = 1116 - 119 + 2
        const expectedUnitClassCount = 63
        assert.lengthOf(
          Object.keys(hedSchemas.baseSchema.attributes.tags),
          expectedTagCount,
          'Mismatch on overall tag count',
        )
        assert.lengthOf(
          Object.keys(hedSchemas.baseSchema.attributes.tagUnitClasses),
          expectedUnitClassCount,
          'Mismatch on unit class tag count',
        )
      })
    })

    it('should identify if a tag has a certain attribute', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const testStrings = {
          value:
            'Attribute/Location/Reference frame/Relative to participant/Azimuth/#',
          valueParent:
            'Attribute/Location/Reference frame/Relative to participant/Azimuth',
          extensionAllowed: 'Item/Object/Road sign',
        }
        const expectedResults = {
          value: {
            default: false,
            extensionAllowed: false,
            isNumeric: true,
            position: false,
            predicateType: false,
            recommended: false,
            required: false,
            requireChild: false,
            tags: false,
            takesValue: true,
            unique: false,
            unitClass: true,
          },
          valueParent: {
            default: false,
            extensionAllowed: true,
            isNumeric: false,
            position: false,
            predicateType: false,
            recommended: false,
            required: false,
            requireChild: true,
            tags: true,
            takesValue: false,
            unique: false,
            unitClass: false,
          },
          extensionAllowed: {
            default: false,
            extensionAllowed: true,
            isNumeric: false,
            position: false,
            predicateType: false,
            recommended: false,
            required: false,
            requireChild: false,
            tags: true,
            takesValue: false,
            unique: false,
            unitClass: false,
          },
        }

        for (const testStringKey in testStrings) {
          const testString = testStrings[testStringKey].toLowerCase()
          const expected = expectedResults[testStringKey]
          for (const expectedKey in expected) {
            if (expectedKey === 'tags') {
              assert.strictEqual(
                hedSchemas.baseSchema.attributes.tags.includes(testString),
                expected[expectedKey],
                `Test string: ${testString}. Attribute: ${expectedKey}`,
              )
            } else if (expectedKey === 'unitClass') {
              assert.strictEqual(
                testString in hedSchemas.baseSchema.attributes.tagUnitClasses,
                expected[expectedKey],
                `Test string: ${testString}. Attribute: ${expectedKey}`,
              )
            } else {
              assert.strictEqual(
                hedSchemas.baseSchema.attributes.tagHasAttribute(
                  testString,
                  expectedKey,
                ),
                expected[expectedKey],
                `Test string: ${testString}. Attribute: ${expectedKey}.`,
              )
            }
          }
        }
      })
    })
  })

  describe('HED-3G schemas', () => {
    const localHedSchemaFile = 'tests/data/HED8.0.0-alpha.3.xml'
    let hedSchemaPromise

    beforeAll(() => {
      hedSchemaPromise = schema.buildSchema({
        path: localHedSchemaFile,
      })
    })

    it('should have tag dictionaries for all defined tag attributes', () => {
      const tagDictionaryKeys = [
        'extensionAllowed',
        'isNumeric',
        'recommended',
        'relatedTag',
        'requireChild',
        'required',
        'suggestedTag',
        'tagGroup',
        'takesValue',
        'topLevelTagGroup',
        'unique',
      ]
      return hedSchemaPromise.then((hedSchemas) => {
        const dictionaries = hedSchemas.baseSchema.attributes.tagAttributes
        assert.hasAllKeys(dictionaries, tagDictionaryKeys)
      })
    })

    it('should have unit dictionaries for all defined unit attributes', () => {
      const unitDictionaryKeys = ['SIUnit', 'unitPrefix', 'unitSymbol']
      return hedSchemaPromise.then((hedSchemas) => {
        const dictionaries = hedSchemas.baseSchema.attributes.unitAttributes
        assert.hasAllKeys(dictionaries, unitDictionaryKeys)
      })
    })

    it('should contain all of the tag group tags', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const tagGroupTags = ['attribute/informational/def-expand']
        const dictionariesTagGroupTags =
          hedSchemas.baseSchema.attributes.tagAttributes['tagGroup']
        assert.hasAllKeys(dictionariesTagGroupTags, tagGroupTags)
      })
    })

    it('should contain all of the top-level tag group tags', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const tagGroupTags = [
          'attribute/informational/definition',
          'attribute/organizational/event-context',
          'data-property/spatiotemporal-property/temporal-property/onset',
          'data-property/spatiotemporal-property/temporal-property/offset',
        ]
        const dictionariesTopLevelTagGroupTags =
          hedSchemas.baseSchema.attributes.tagAttributes['topLevelTagGroup']
        assert.hasAllKeys(dictionariesTopLevelTagGroupTags, tagGroupTags)
      })
    })

    it('should contain all of the unit classes with their units and default units', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const defaultUnits = {
          acceleration: 'm-per-s^2',
          angle: 'radian',
          area: 'm^2',
          currency: '$',
          dateTime: 'YYYY-MM-DDThh:mm:ss',
          frequency: 'Hz',
          intensity: 'dB',
          jerk: 'm-per-s^3',
          luminousIntensity: 'cd',
          memorySize: 'B',
          posixPath: undefined,
          physicalLength: 'm',
          pixels: 'px',
          speed: 'm-per-s',
          time: 's',
          volume: 'm^3',
        }
        const allUnits = {
          acceleration: ['m-per-s^2'],
          angle: ['radian', 'rad', 'degree'],
          area: ['m^2', 'px^2', 'pixel^2'],
          currency: ['dollar', '$', 'point'],
          dateTime: ['YYYY-MM-DDThh:mm:ss'],
          frequency: ['hertz', 'Hz'],
          intensity: ['dB'],
          jerk: ['m-per-s^3'],
          luminousIntensity: ['candela', 'cd'],
          memorySize: ['byte', 'B'],
          posixPath: [],
          physicalLength: ['metre', 'm', 'foot', 'mile'],
          pixels: ['pixel', 'px'],
          speed: ['m-per-s', 'mph', 'kph'],
          time: ['second', 's', 'day', 'minute', 'hour'],
          volume: ['m^3'],
        }

        const dictionariesUnitAttributes =
          hedSchemas.baseSchema.attributes.unitClassAttributes
        const dictionariesAllUnits =
          hedSchemas.baseSchema.attributes.unitClasses
        for (const unitClass in dictionariesUnitAttributes) {
          const defaultUnit = dictionariesUnitAttributes[unitClass].defaultUnits
          if (defaultUnit === undefined) {
            assert.isUndefined(
              defaultUnits[unitClass],
              `Default unit for unit class ${unitClass}`,
            )
            continue
          }
          assert.deepStrictEqual(
            defaultUnit[0],
            defaultUnits[unitClass],
            `Default unit for unit class ${unitClass}`,
          )
        }
        assert.deepStrictEqual(dictionariesAllUnits, allUnits, 'All units')
      })
    })

    it('should contain the correct (large) numbers of tags with certain attributes', () => {
      return hedSchemaPromise.then((hedSchemas) => {
        const expectedAttributeTagCount = {
          isNumeric: 41,
          requireChild: 7,
          takesValue: 74,
        }

        const dictionaries = hedSchemas.baseSchema.attributes.tagAttributes
        for (const attribute in expectedAttributeTagCount) {
          assert.lengthOf(
            Object.keys(dictionaries[attribute]),
            expectedAttributeTagCount[attribute],
            'Mismatch on attribute ' + attribute,
          )
        }

        const expectedTagCount = 1042
        const expectedUnitClassCount = 19
        assert.lengthOf(
          Object.keys(hedSchemas.baseSchema.attributes.tags),
          expectedTagCount,
          'Mismatch on overall tag count',
        )
        assert.lengthOf(
          Object.keys(hedSchemas.baseSchema.attributes.tagUnitClasses),
          expectedUnitClassCount,
          'Mismatch on unit class tag count',
        )
      })
    })
  })
})
