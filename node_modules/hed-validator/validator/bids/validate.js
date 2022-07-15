const { validateHedDataset } = require('../dataset')
const { validateHedString } = require('../event')
const { buildSchema } = require('../schema')
const { sidecarValueHasHed } = require('../../utils/bids')
const { generateIssue } = require('../../utils/issues/issues')
const { fallbackFilePath } = require('../../utils/schema')
const { BidsDataset, BidsHedIssue, BidsIssue } = require('./types')

function generateInternalErrorBidsIssue(error) {
  return Promise.resolve([new BidsIssue(107, null, error.message)])
}

/**
 * Validate a BIDS dataset.
 *
 * @param {BidsDataset} dataset The BIDS dataset.
 * @param {object} schemaDefinition The version spec for the schema to be loaded.
 * @return {Promise<Array<BidsIssue>>} Any issues found.
 */
function validateBidsDataset(dataset, schemaDefinition) {
  // loop through event data files
  const schemaLoadIssues = []
  return buildBidsSchema(dataset, schemaDefinition)
    .catch((error) => {
      schemaLoadIssues.push(
        new BidsHedIssue(
          generateIssue('requestedSchemaLoadFailed', {
            schemaDefinition: JSON.stringify(schemaDefinition),
            error: error.message,
          }),
          dataset.datasetDescription.file,
        ),
      )
      return buildBidsSchema(dataset, { path: fallbackFilePath }).catch(
        (error) => {
          schemaLoadIssues.push(
            new BidsHedIssue(
              generateIssue('fallbackSchemaLoadFailed', {
                error: error.message,
              }),
              dataset.datasetDescription.file,
            ),
          )
          return []
        },
      )
    })
    .then((datasetIssues) => {
      return Promise.resolve(datasetIssues.concat(schemaLoadIssues))
    })
}

function buildBidsSchema(dataset, schemaDefinition) {
  return buildSchema(schemaDefinition, false).then((hedSchemas) => {
    return validateDataset(dataset, hedSchemas).catch(
      generateInternalErrorBidsIssue,
    )
  })
}

function validateDataset(dataset, hedSchemas) {
  const [sidecarErrorsFound, sidecarIssues] = validateSidecars(
    dataset.sidecarData,
    hedSchemas,
  )
  if (sidecarErrorsFound) {
    return Promise.resolve(sidecarIssues)
  }
  const eventFileIssues = dataset.eventData.map((eventFileData) => {
    return validateBidsEventFile(eventFileData, hedSchemas)
  })
  return Promise.resolve([].concat(sidecarIssues, ...eventFileIssues))
}

function validateBidsEventFile(eventFileData, hedSchema) {
  // get the json sidecar dictionary associated with the event data

  const [hedStrings, tsvIssues] = parseTsvHed(eventFileData)
  if (!hedStrings) {
    return []
  } else {
    const datasetIssues = validateCombinedDataset(
      hedStrings,
      hedSchema,
      eventFileData,
    )
    return [].concat(tsvIssues, datasetIssues)
  }
}

function validateSidecars(sidecarData, hedSchema) {
  let issues = []
  let sidecarErrorsFound = false
  // validate the HED strings in the json sidecars
  for (const sidecar of sidecarData) {
    const sidecarDictionary = sidecar.sidecarData
    const sidecarHedValueStrings = []
    let sidecarHedCategoricalStrings = []
    const sidecarHedData =
      Object.values(sidecarDictionary).filter(sidecarValueHasHed)
    for (const sidecarValue of sidecarHedData) {
      if (typeof sidecarValue.HED === 'string') {
        sidecarHedValueStrings.push(sidecarValue.HED)
      } else {
        sidecarHedCategoricalStrings = sidecarHedCategoricalStrings.concat(
          Object.values(sidecarValue.HED),
        )
      }
    }
    const valueStringIssues = validateSidecarStrings(
      sidecarHedValueStrings,
      hedSchema,
      sidecar.file,
      true,
    )
    const categoricalStringIssues = validateSidecarStrings(
      sidecarHedCategoricalStrings,
      hedSchema,
      sidecar.file,
      false,
    )
    const fileIssues = [].concat(valueStringIssues, categoricalStringIssues)
    sidecarErrorsFound =
      sidecarErrorsFound ||
      fileIssues.some((fileIssue) => {
        return fileIssue.isError()
      })
    issues = issues.concat(fileIssues)
  }
  return [sidecarErrorsFound, issues]
}

function validateSidecarStrings(
  sidecarHedStrings,
  hedSchema,
  jsonFileObject,
  areValueStrings,
) {
  let sidecarIssues = []
  for (const hedString of sidecarHedStrings) {
    const [isHedStringValid, hedIssues] = validateHedString(
      hedString,
      hedSchema,
      true,
      areValueStrings,
    )
    if (!isHedStringValid) {
      const convertedIssues = convertHedIssuesToBidsIssues(
        hedIssues,
        jsonFileObject,
      )
      sidecarIssues = sidecarIssues.concat(convertedIssues)
    }
  }
  return sidecarIssues
}

function parseTsvHed(eventFileData) {
  const hedStrings = []
  const issues = []
  const hedColumnIndex = eventFileData.parsedTsv.headers.indexOf('HED')
  const sidecarHedColumnIndices = {}
  for (const sidecarHedColumn of eventFileData.sidecarHedData.keys()) {
    const sidecarHedColumnHeader =
      eventFileData.parsedTsv.headers.indexOf(sidecarHedColumn)
    if (sidecarHedColumnHeader > -1) {
      sidecarHedColumnIndices[sidecarHedColumn] = sidecarHedColumnHeader
    }
  }
  if (hedColumnIndex === -1 && sidecarHedColumnIndices.length === 0) {
    return [[], []]
  }

  for (const rowCells of eventFileData.parsedTsv.rows.slice(1)) {
    // get the 'HED' field
    const hedStringParts = []
    if (rowCells[hedColumnIndex] && rowCells[hedColumnIndex] !== 'n/a') {
      hedStringParts.push(rowCells[hedColumnIndex])
    }
    for (const sidecarHedColumn in sidecarHedColumnIndices) {
      const sidecarHedIndex = sidecarHedColumnIndices[sidecarHedColumn]
      const sidecarHedData = eventFileData.sidecarHedData.get(sidecarHedColumn)
      const rowCell = rowCells[sidecarHedIndex]
      if (rowCell && rowCell !== 'n/a') {
        let sidecarHedString
        if (!sidecarHedData) {
          continue
        }
        if (typeof sidecarHedData === 'string') {
          sidecarHedString = sidecarHedData.replace('#', rowCell)
        } else {
          sidecarHedString = sidecarHedData[rowCell]
        }
        if (sidecarHedString !== undefined) {
          hedStringParts.push(sidecarHedString)
        } else {
          issues.push(new BidsIssue(108, eventFileData.file, rowCell))
        }
      }
    }

    if (hedStringParts.length === 0) {
      continue
    }
    hedStrings.push(hedStringParts.join(','))
  }
  return [hedStrings, issues]
}

function validateCombinedDataset(hedStrings, hedSchema, eventFileData) {
  const [isHedDatasetValid, hedIssues] = validateHedDataset(
    hedStrings,
    hedSchema,
    true,
  )
  if (!isHedDatasetValid) {
    return convertHedIssuesToBidsIssues(hedIssues, eventFileData.file)
  } else {
    return []
  }
}

function convertHedIssuesToBidsIssues(hedIssues, file) {
  return hedIssues.map((hedIssue) => {
    return new BidsHedIssue(hedIssue, file)
  })
}

module.exports = validateBidsDataset
