// TODO: Switch require once upstream bugs are fixed.
// const xpath = require('xml2js-xpath')
// Temporary
const xpath = require('../utils/xpath')

const schemaUtils = require('../utils/schema')
const { asArray } = require('../utils/array')

const types = require('./types')
const TagEntry = types.TagEntry
const Mapping = types.Mapping

/**
 * Build a short-long mapping object from schema XML data.
 *
 * @param {object} xmlData The schema XML data.
 * @return {Mapping} The mapping object.
 */
const buildMappingObject = function (xmlData) {
  const nodeData = {}
  let hasNoDuplicates = true
  const rootElement = xmlData.HED
  schemaUtils.setParent(rootElement, null)
  const tagElements = xpath.find(rootElement, '//node')
  for (const tagElement of tagElements) {
    if (getElementTagValue(tagElement) === '#') {
      continue
    }
    const tagPath = getTagPathFromTagElement(tagElement)
    const shortPath = tagPath[0]
    const cleanedShortPath = shortPath.toLowerCase()
    tagPath.reverse()
    const longPath = tagPath.join('/')
    const tagObject = new TagEntry(shortPath, longPath)
    if (!(cleanedShortPath in nodeData)) {
      nodeData[cleanedShortPath] = tagObject
    } else {
      hasNoDuplicates = false
      nodeData[cleanedShortPath] = asArray(nodeData[cleanedShortPath])
      nodeData[cleanedShortPath].push(tagObject)
    }
  }
  return new Mapping(nodeData, hasNoDuplicates)
}

const getTagPathFromTagElement = function (tagElement) {
  const ancestorTags = [getElementTagValue(tagElement)]
  let parentTagName = getParentTagName(tagElement)
  let parentElement = tagElement.$parent
  while (parentTagName) {
    ancestorTags.push(parentTagName)
    parentTagName = getParentTagName(parentElement)
    parentElement = parentElement.$parent
  }
  return ancestorTags
}

const getElementTagValue = function (element, tagName = 'name') {
  return element[tagName][0]._
}

const getParentTagName = function (tagElement) {
  const parentTagElement = tagElement.$parent
  if (parentTagElement && 'name' in parentTagElement) {
    return parentTagElement.name[0]._
  } else {
    return ''
  }
}

/**
 * Build a schema container object containing a short-long mapping from a base schema version or path description.
 *
 * @param {{path: string?, version: string?}} schemaDef The description of which schema to use.
 * @return {Promise<never>|Promise<Schemas>} The schema container object or an error.
 */
const buildSchema = function (schemaDef = {}) {
  return schemaUtils.loadSchema(schemaDef).then((xmlData) => {
    const mapping = buildMappingObject(xmlData)
    const baseSchema = new schemaUtils.Schema(xmlData, undefined, mapping)
    return new schemaUtils.Schemas(baseSchema)
  })
}

module.exports = {
  buildSchema: buildSchema,
  buildMappingObject: buildMappingObject,
}
