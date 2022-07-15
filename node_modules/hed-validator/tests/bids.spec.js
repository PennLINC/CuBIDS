const assert = require('chai').assert
const converterGenerateIssue = require('../converter/issues')
const { generateIssue } = require('../utils/issues/issues')
const {
  BidsDataset,
  BidsEventFile,
  BidsHedIssue,
  BidsIssue,
  BidsSidecar,
  validateBidsDataset,
} = require('../validator/bids')

describe('BIDS datasets', () => {
  const sidecars = [
    // sub01 - Valid sidecars
    [
      {
        color: {
          HED: {
            red: 'RGB-red',
            green: 'RGB-green',
            blue: 'RGB-blue',
          },
        },
      },
      {
        vehicle: {
          HED: {
            car: 'Car',
            train: 'Train',
            boat: 'Boat',
          },
        },
        speed: {
          HED: 'Speed/# mph',
        },
      },
      {
        duration: {
          HED: 'Duration/# s',
        },
        age: {
          HED: 'Age/#',
        },
      },
    ],
    // sub02 - Invalid sidecars
    [
      {
        transport: {
          HED: {
            car: 'Car',
            train: 'Train',
            boat: 'Boat',
            maglev: 'Train/Maglev', // Extension.
          },
        },
      },
      {
        emotion: {
          HED: {
            happy: 'Happy',
            sad: 'Sad',
            angry: 'Angry',
            confused: 'Confused', // Not in schema.
          },
        },
      },
    ],
    // sub03 - Placeholders
    [
      {
        valid_definition: {
          HED: { definition: '(Definition/ValidDefinition, (Square))' },
        },
      },
      {
        valid_placeholder_definition: {
          HED: {
            definition:
              '(Definition/ValidPlaceholderDefinition/#, (RGB-red/#))',
          },
        },
      },
      {
        valid_value_and_definition: {
          HED: 'Duration/# ms, (Definition/ValidValueAndDefinition/#, (Age/#))',
        },
      },
      {
        invalid_definition_group: {
          HED: { definition: '(Definition/InvalidDefinitionGroup, (Age/#))' },
        },
      },
      {
        invalid_definition_tag: {
          HED: { definition: '(Definition/InvalidDefinitionTag/#, (Age))' },
        },
      },
      {
        multiple_placeholders_in_group: {
          HED: {
            definition:
              '(Definition/MultiplePlaceholdersInGroupDefinition/#, (Age/#, Duration/# s))',
          },
        },
      },
      {
        multiple_value_tags: {
          HED: 'Duration/# s, RGB-blue/#',
        },
      },
      {
        no_value_tags: {
          HED: 'Sad',
        },
      },
      {
        value_in_categorical: {
          HED: {
            purple: 'Purple',
            yellow: 'Yellow',
            orange: 'Orange',
            green: 'RGB-green/#',
          },
        },
      },
    ],
    // sub04 - HED 2 sidecars
    [
      {
        test: {
          HED: {
            first:
              'Event/Label/Test,Event/Category/Miscellaneous/Test,Event/Description/Test',
          },
        },
      },
    ],
  ]
  const hedColumnOnlyHeader = ['onset', 'duration', 'HED']
  const bidsTsvFiles = [
    // sub01 - Valid TSV-only data
    [
      new BidsEventFile(
        '/sub01/sub01_task-test_run-1_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [hedColumnOnlyHeader, ['7', 'something', 'Cellphone']],
        },
        {
          relativePath: '/sub01/sub01_task-test_run-1_events.tsv',
          path: '/sub01/sub01_task-test_run-1_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub01/sub01_task-test_run-2_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [
            hedColumnOnlyHeader,
            ['7', 'something', 'Cellphone'],
            ['11', 'else', 'Desktop-computer'],
          ],
        },
        {
          relativePath: '/sub01/sub01_task-test_run-2_events.tsv',
          path: '/sub01/sub01_task-test_run-2_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub01/sub01_task-test_run-3_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [hedColumnOnlyHeader, ['7', 'something', 'Ceramic, Pink']],
        },
        {
          relativePath: '/sub01/sub01_task-test_run-3_events.tsv',
          path: '/sub01/sub01_task-test_run-3_events.tsv',
        },
      ),
    ],
    // sub02 - Invalid TSV-only data
    [
      new BidsEventFile(
        '/sub02/sub02_task-test_run-1_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [hedColumnOnlyHeader, ['11', 'else', 'Speed/300 miles']],
        },
        {
          relativePath: '/sub02/sub02_task-test_run-1_events.tsv',
          path: '/sub02/sub02_task-test_run-1_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub02/sub02_task-test_run-2_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [hedColumnOnlyHeader, ['7', 'something', 'Train/Maglev']],
        },
        {
          relativePath: '/sub01/sub01_task-test_run-2_events.tsv',
          path: '/sub01/sub01_task-test_run-2_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub02/sub02_task-test_run-3_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [
            hedColumnOnlyHeader,
            ['7', 'something', 'Train'],
            ['11', 'else', 'Speed/300 miles'],
          ],
        },
        {
          relativePath: '/sub02/sub02_task-test_run-3_events.tsv',
          path: '/sub02/sub02_task-test_run-3_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub02/sub02_task-test_run-4_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [
            hedColumnOnlyHeader,
            ['7', 'something', 'Maglev'],
            ['11', 'else', 'Speed/300 miles'],
          ],
        },
        {
          relativePath: '/sub02/sub02_task-test_run-4_events.tsv',
          path: '/sub02/sub02_task-test_run-4_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub02/sub02_task-test_run-5_events.tsv',
        [],
        {},
        {
          headers: hedColumnOnlyHeader,
          rows: [
            hedColumnOnlyHeader,
            ['7', 'something', 'Train/Maglev'],
            ['11', 'else', 'Speed/300 miles'],
          ],
        },
        {
          relativePath: '/sub02/sub02_task-test_run-5_events.tsv',
          path: '/sub02/sub02_task-test_run-5_events.tsv',
        },
      ),
    ],
    // sub03 - Valid combined sidecar/TSV data
    [
      new BidsEventFile(
        '/sub03/sub03_task-test_run-1_events.tsv',
        ['/sub03/sub03_task-test_run-1_events.json'],
        sidecars[2][0],
        {
          headers: ['onset', 'duration'],
          rows: [
            ['onset', 'duration'],
            ['7', 'something'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-1_events.tsv',
          path: '/sub03/sub03_task-test_run-1_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-2_events.tsv',
        ['/sub01/sub01_task-test_run-1_events.json'],
        sidecars[0][0],
        {
          headers: ['onset', 'duration', 'color'],
          rows: [
            ['onset', 'duration', 'color'],
            ['7', 'something', 'red'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-2_events.tsv',
          path: '/sub03/sub03_task-test_run-2_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-3_events.tsv',
        ['/sub01/sub01_task-test_run-2_events.json'],
        sidecars[0][1],
        {
          headers: ['onset', 'duration', 'speed'],
          rows: [
            ['onset', 'duration', 'speed'],
            ['7', 'something', '60'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-3_events.tsv',
          path: '/sub03/sub03_task-test_run-3_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-4_events.tsv',
        ['/sub03/sub03_task-test_run-1_events.json'],
        sidecars[2][0],
        {
          headers: hedColumnOnlyHeader,
          rows: [hedColumnOnlyHeader, ['7', 'something', 'Laptop-computer']],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-4_events.tsv',
          path: '/sub03/sub03_task-test_run-4_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-5_events.tsv',
        ['/sub01/sub01_task-test_run-1_events.json'],
        sidecars[0][0],
        {
          headers: ['onset', 'duration', 'color', 'HED'],
          rows: [
            ['onset', 'duration', 'color', 'HED'],
            ['7', 'something', 'green', 'Laptop-computer'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-5_events.tsv',
          path: '/sub03/sub03_task-test_run-5_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-6_events.tsv',
        [
          '/sub01/sub01_task-test_run-1_events.json',
          '/sub01/sub01_task-test_run-2_events.json',
        ],
        Object.assign({}, sidecars[0][0], sidecars[0][1]),
        {
          headers: ['onset', 'duration', 'color', 'vehicle', 'speed'],
          rows: [
            ['onset', 'duration', 'color', 'vehicle', 'speed'],
            ['7', 'something', 'blue', 'train', '150'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-6_events.tsv',
          path: '/sub03/sub03_task-test_run-6_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub03/sub03_task-test_run-7_events.tsv',
        [
          '/sub01/sub01_task-test_run-1_events.json',
          '/sub01/sub01_task-test_run-2_events.json',
        ],
        Object.assign({}, sidecars[0][0], sidecars[0][1]),
        {
          headers: ['onset', 'duration', 'color', 'vehicle', 'speed'],
          rows: [
            ['onset', 'duration', 'color', 'vehicle', 'speed'],
            ['7', 'something', 'red', 'train', '150'],
            ['11', 'else', 'blue', 'boat', '15'],
            ['15', 'another', 'green', 'car', '70'],
          ],
        },
        {
          relativePath: '/sub03/sub03_task-test_run-7_events.tsv',
          path: '/sub03/sub03_task-test_run-7_events.tsv',
        },
      ),
    ],
    // sub04 - Invalid combined sidecar/TSV data
    [
      new BidsEventFile(
        '/sub04/sub04_task-test_run-1_events.tsv',
        ['/sub02/sub02_task-test_run-2_events.json'],
        sidecars[1][1],
        {
          headers: ['onset', 'duration', 'emotion', 'HED'],
          rows: [
            ['onset', 'duration', 'emotion', 'HED'],
            ['7', 'high', 'happy', 'Yellow'],
            ['11', 'low', 'sad', 'Blue'],
            ['15', 'mad', 'angry', 'Red'],
            ['19', 'huh', 'confused', 'Gray'],
          ],
        },
        {
          relativePath: '/sub04/sub04_task-test_run-1_events.tsv',
          path: '/sub04/sub04_task-test_run-1_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub04/sub04_task-test_run-2_events.tsv',
        ['/sub02/sub02_task-test_run-1_events.json'],
        sidecars[1][0],
        {
          headers: ['onset', 'duration', 'transport'],
          rows: [
            ['onset', 'duration', 'transport'],
            ['7', 'wet', 'boat'],
            ['11', 'steam', 'train'],
            ['15', 'tires', 'car'],
            ['19', 'speedy', 'maglev'],
          ],
        },
        {
          relativePath: '/sub04/sub04_task-test_run-2_events.tsv',
          path: '/sub04/sub04_task-test_run-2_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub04/sub04_task-test_run-3_events.tsv',
        [
          '/sub01/sub01_task-test_run-2_events.json',
          '/sub02/sub02_task-test_run-1_events.json',
        ],
        Object.assign({}, sidecars[0][1], sidecars[1][0]),
        {
          headers: ['onset', 'duration', 'vehicle', 'transport', 'speed'],
          rows: [
            ['onset', 'duration', 'vehicle', 'transport', 'speed'],
            ['7', 'ferry', 'train', 'boat', '20'],
            ['11', 'autotrain', 'car', 'train', '79'],
            ['15', 'towing', 'boat', 'car', '30'],
            ['19', 'tugboat', 'boat', 'boat', '5'],
          ],
        },
        {
          relativePath: '/sub04/sub04_task-test_run-3_events.tsv',
          path: '/sub04/sub04_task-test_run-3_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub04/sub04_task-test_run-4_events.tsv',
        ['/sub01/sub01_task-test_run-3_events.json'],
        sidecars[0][2],
        {
          headers: ['onset', 'duration', 'age', 'HED'],
          rows: [
            ['onset', 'duration', 'age', 'HED'],
            ['7', 'ferry', '30', 'Age/30'],
          ],
        },
        {
          relativePath: '/sub04/sub04_task-test_run-4_events.tsv',
          path: '/sub04/sub04_task-test_run-4_events.tsv',
        },
      ),
      new BidsEventFile(
        '/sub04/sub04_task-test_run-5_events.tsv',
        ['/sub01/sub01_task-test_run-1_events.json'],
        sidecars[0][0],
        {
          headers: ['onset', 'duration', 'color'],
          rows: [
            ['onset', 'duration', 'color'],
            ['7', 'royal', 'purple'],
          ],
        },
        {
          relativePath: '/sub04/sub04_task-test_run-5_events.tsv',
          path: '/sub04/sub04_task-test_run-5_events.tsv',
        },
      ),
    ],
    // sub05 - Valid combined sidecar/TSV data from HED 2
    [
      new BidsEventFile(
        '/sub05/sub05_task-test_run-1_events.tsv',
        ['/sub04/sub04_task-test_run-1_events.json'],
        sidecars[3][0],
        {
          headers: ['onset', 'duration', 'test', 'HED'],
          rows: [
            ['onset', 'duration', 'test', 'HED'],
            ['7', 'something', 'first', 'Event/Duration/55 ms'],
          ],
        },
        {
          relativePath: '/sub05/sub05_task-test_run-1_events.tsv',
          path: '/sub05/sub05_task-test_run-1_events.tsv',
        },
      ),
    ],
  ]
  /**
   * @type {object[][]}
   */
  let bidsSidecars

  beforeAll(() => {
    bidsSidecars = sidecars.map((sub_data, sub) => {
      return sub_data.map((run_data, run) => {
        const name = `/sub0${sub + 1}/sub0${sub + 1}_task-test_run-${
          run + 1
        }_events.json`
        return new BidsSidecar(name, run_data, {
          relativePath: name,
          path: name,
        })
      })
    })
  })

  /**
   * Validate the test datasets.
   * @param {object<string,BidsDataset>} testDatasets The datasets to test with.
   * @param {object<string,BidsIssue[]>} expectedIssues The expected issues.
   * @param {object} versionSpec The schema version to test with.
   * @return {Promise}
   */
  const validator = (testDatasets, expectedIssues, versionSpec) => {
    return Promise.all(
      Object.entries(testDatasets).map(([datasetName, dataset]) => {
        return validateBidsDataset(dataset, versionSpec).then((issues) => {
          assert.sameDeepMembers(
            issues,
            expectedIssues[datasetName],
            datasetName,
          )
        })
      }),
    )
  }

  describe('Sidecar-only datasets', () => {
    it('should validate non-placeholder HED strings in BIDS sidecars', () => {
      const goodDatasets = bidsSidecars[0]
      const testDatasets = {
        single: new BidsDataset([], [bidsSidecars[0][0]]),
        all_good: new BidsDataset([], goodDatasets),
        warning_and_good: new BidsDataset(
          [],
          goodDatasets.concat([bidsSidecars[1][0]]),
        ),
        error_and_good: new BidsDataset(
          [],
          goodDatasets.concat([bidsSidecars[1][1]]),
        ),
      }
      const expectedIssues = {
        single: [],
        all_good: [],
        warning_and_good: [
          new BidsHedIssue(
            generateIssue('extension', { tag: 'Train/Maglev' }),
            bidsSidecars[1][0].file,
          ),
        ],
        error_and_good: [
          new BidsHedIssue(
            converterGenerateIssue('invalidTag', 'Confused', {}, [0, 8]),
            bidsSidecars[1][1].file,
          ),
        ],
      }
      return validator(testDatasets, expectedIssues, { version: '8.0.0' })
    })

    it('should validate placeholders in BIDS sidecars', () => {
      const placeholderDatasets = bidsSidecars[2]
      const testDatasets = {
        placeholders: new BidsDataset([], placeholderDatasets),
      }
      const expectedIssues = {
        placeholders: [
          new BidsHedIssue(
            generateIssue('invalidPlaceholderInDefinition', {
              definition: 'InvalidDefinitionGroup',
            }),
            bidsSidecars[2][3].file,
          ),
          new BidsHedIssue(
            generateIssue('invalidPlaceholderInDefinition', {
              definition: 'InvalidDefinitionTag',
            }),
            bidsSidecars[2][4].file,
          ),
          new BidsHedIssue(
            generateIssue('invalidPlaceholderInDefinition', {
              definition: 'MultiplePlaceholdersInGroupDefinition',
            }),
            bidsSidecars[2][5].file,
          ),
          new BidsHedIssue(
            generateIssue('invalidPlaceholder', { tag: 'Duration/# s' }),
            bidsSidecars[2][6].file,
          ),
          new BidsHedIssue(
            generateIssue('invalidPlaceholder', { tag: 'RGB-blue/#' }),
            bidsSidecars[2][6].file,
          ),
          new BidsHedIssue(
            generateIssue('missingPlaceholder', { string: 'Sad' }),
            bidsSidecars[2][7].file,
          ),
          new BidsHedIssue(
            generateIssue('invalidPlaceholder', { tag: 'RGB-green/#' }),
            bidsSidecars[2][8].file,
          ),
        ],
      }
      return validator(testDatasets, expectedIssues, { version: '8.0.0' })
    })
  })

  describe('TSV-only datasets', () => {
    it('should validate HED strings in BIDS event files', () => {
      const goodDatasets = bidsTsvFiles[0]
      const badDatasets = bidsTsvFiles[1]
      const testDatasets = {
        all_good: new BidsDataset(goodDatasets, []),
        all_bad: new BidsDataset(badDatasets, []),
      }
      const legalSpeedUnits = ['m-per-s', 'kph', 'mph']
      const speedIssue = generateIssue('unitClassInvalidUnit', {
        tag: 'Speed/300 miles',
        unitClassUnits: legalSpeedUnits.sort().join(','),
      })
      const maglevError = generateIssue('invalidTag', { tag: 'Maglev' })
      const maglevWarning = generateIssue('extension', { tag: 'Train/Maglev' })
      const expectedIssues = {
        all_good: [],
        all_bad: [
          new BidsHedIssue(speedIssue, badDatasets[0].file),
          new BidsHedIssue(maglevWarning, badDatasets[1].file),
          new BidsHedIssue(speedIssue, badDatasets[2].file),
          new BidsHedIssue(speedIssue, badDatasets[3].file),
          new BidsHedIssue(maglevError, badDatasets[3].file),
          new BidsHedIssue(speedIssue, badDatasets[4].file),
          new BidsHedIssue(maglevWarning, badDatasets[4].file),
        ],
      }
      return validator(testDatasets, expectedIssues, { version: '8.0.0' })
    })
  })

  describe('Combined datasets', () => {
    it('should validate BIDS event files combined with JSON sidecar data', () => {
      const goodDatasets = bidsTsvFiles[2]
      const badDatasets = bidsTsvFiles[3]
      const testDatasets = {
        all_good: new BidsDataset(goodDatasets, []),
        all_bad: new BidsDataset(badDatasets, []),
      }
      const expectedIssues = {
        all_good: [],
        all_bad: [
          new BidsHedIssue(
            generateIssue('invalidTag', { tag: 'Confused' }),
            badDatasets[0].file,
          ),
          new BidsHedIssue(
            generateIssue('extension', { tag: 'Train/Maglev' }),
            badDatasets[1].file,
          ),
          new BidsHedIssue(
            generateIssue('duplicateTag', {
              tag: 'Boat',
              bounds: [0, 4],
            }),
            badDatasets[2].file,
          ),
          new BidsHedIssue(
            generateIssue('duplicateTag', {
              tag: 'Boat',
              bounds: [17, 21],
            }),
            badDatasets[2].file,
          ),
          new BidsHedIssue(
            generateIssue('duplicateTag', {
              tag: 'Age/30',
              bounds: [0, 6],
            }),
            badDatasets[3].file,
          ),
          new BidsHedIssue(
            generateIssue('duplicateTag', {
              tag: 'Age/30',
              bounds: [24, 30],
            }),
            badDatasets[3].file,
          ),
          new BidsIssue(108, badDatasets[4].file, 'purple'),
        ],
      }
      return validator(testDatasets, expectedIssues, { version: '8.0.0' })
    })
  })

  describe('HED 2 combined datasets', () => {
    it('should validate HED 2 data in BIDS event files combined with JSON sidecar data', () => {
      const goodDatasets = bidsTsvFiles[4]
      const testDatasets = {
        all_good: new BidsDataset(goodDatasets, []),
      }
      const expectedIssues = {
        all_good: [],
      }
      return validator(testDatasets, expectedIssues, { version: '7.2.0' })
    })
  })
})
