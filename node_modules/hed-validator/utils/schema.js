const isEmpty = require('lodash/isEmpty')
const semver = require('semver')
const xml2js = require('xml2js')

const files = require('./files')
const { stringTemplate } = require('./string')

const fallbackFilePath = 'data/HED8.0.0.xml'

/**
 * Load schema XML data from a schema version or path description.
 *
 * @param {{path: string?, library: string?, version: string?}} schemaDef The description of which schema to use.
 * @param {boolean} useFallback Whether to use a bundled fallback schema if the requested schema cannot be loaded.
 * @return {Promise<never>|Promise<object>} The schema XML data or an error.
 */
const loadSchema = function (schemaDef = {}, useFallback = true) {
  if (isEmpty(schemaDef)) {
    schemaDef.version = 'Latest'
  }
  let schemaPromise
  if (schemaDef.path) {
    schemaPromise = loadLocalSchema(schemaDef.path)
  } /* else if (schemaDef.library) {
    return loadRemoteLibrarySchema(schemaDef.library, schemaDef.version)
  } */ else if (schemaDef.version) {
    schemaPromise = loadRemoteBaseSchema(schemaDef.version)
  } else {
    return Promise.reject(new Error('Invalid schema definition format.'))
  }
  return schemaPromise.catch((error) => {
    if (useFallback) {
      return loadLocalSchema(fallbackFilePath)
    } else {
      throw error
    }
  })
}

/**
 * Load base schema XML data from the HED specification GitHub repository.
 *
 * @param {string} version The base schema version to load.
 * @return {Promise<object>} The schema XML data.
 */
const loadRemoteBaseSchema = function (version = 'Latest') {
  const url = `https://raw.githubusercontent.com/hed-standard/hed-specification/master/hedxml/HED${version}.xml`
  return loadSchemaFile(
    files.readHTTPSFile(url),
    stringTemplate`Could not load HED base schema, version "${1}", from remote repository - "${0}".`,
    ...arguments,
  )
}

/**
 * Load library schema XML data from the HED specification GitHub repository.
 *
 * @param {string} library The library schema to load.
 * @param {string} version The schema version to load.
 * @return {Promise<object>} The library schema XML data.
 */
const loadRemoteLibrarySchema = function (library, version = 'Latest') {
  const url = `https://raw.githubusercontent.com/hed-standard/hed-schema-library/master/hedxml/HED_${library}_${version}.xml`
  return loadSchemaFile(
    files.readHTTPSFile(url),
    stringTemplate`Could not load HED library schema ${1}, version "${2}", from remote repository - "${0}".`,
    ...arguments,
  )
}

/**
 * Load schema XML data from a local file.
 *
 * @param {string} path The path to the schema XML data.
 * @return {Promise<object>} The schema XML data.
 */
const loadLocalSchema = function (path) {
  return loadSchemaFile(
    files.readFile(path),
    stringTemplate`Could not load HED schema from path "${1}" - "${0}".`,
    ...arguments,
  )
}

/**
 * Actually load the schema XML file.
 *
 * @param {Promise<string>} xmlDataPromise The Promise containing the unparsed XML data.
 * @param {function(...[*]): string} errorMessage A tagged template literal containing the error message.
 * @param {Array} errorArgs The error arguments passed from the calling function.
 * @return {Promise<object>} The parsed schema XML data.
 */
const loadSchemaFile = function (xmlDataPromise, errorMessage, ...errorArgs) {
  return xmlDataPromise.then(parseSchemaXML).catch((error) => {
    throw new Error(errorMessage(error, ...errorArgs))
  })
}

/**
 * Parse the schema XML data.
 *
 * @param {string} data The XML data.
 * @return {Promise<object>} The schema XML data.
 */
const parseSchemaXML = function (data) {
  return xml2js.parseStringPromise(data, { explicitCharkey: true })
}

/**
 * Recursively set a field on each node of the tree pointing to the node's parent.
 *
 * @param {object} node The child node.
 * @param {object} parent The parent node.
 */
const setNodeParent = function (node, parent) {
  // Assume that we've already run this function if so.
  if ('$parent' in node) {
    return
  }
  node.$parent = parent
  const childNodes = node.node || []
  for (const child of childNodes) {
    setNodeParent(child, node)
  }
}

/**
 * Handle top level of parent-setting recursion before passing to setNodeParent.
 *
 * @param {object} node The child node.
 * @param {object} parent The parent node.
 */
const setParent = function (node, parent) {
  if (node.schema) {
    node.$parent = null
    setNodeParent(node.schema[0], null)
  } else {
    setNodeParent(node, parent)
  }
}

/**
 * An imported HED schema object.
 */
class Schema {
  /**
   * Constructor.
   * @param {object} xmlData The schema XML data.
   * @param {SchemaAttributes} attributes A description of tag attributes.
   * @param {Mapping} mapping A mapping between short and long tags.
   */
  constructor(xmlData, attributes, mapping) {
    /**
     * The schema XML data.
     * @type {Object}
     */
    this.xmlData = xmlData
    const rootElement = xmlData.HED
    /**
     * The HED schema version.
     * @type {string}
     */
    this.version = rootElement.$.version
    /**
     * The HED library schema name.
     * @type {string|undefined}
     */
    this.library = rootElement.$.library
    /**
     * The description of tag attributes.
     * @type {SchemaAttributes}
     */
    this.attributes = attributes
    /**
     * The mapping between short and long tags.
     * @type {Mapping}
     */
    this.mapping = mapping
    /**
     * Whether this is a HED 3 schema.
     * @type {boolean}
     */
    this.isHed3 =
      this.library !== undefined || semver.gte(this.version, '8.0.0-alpha')
  }
}

/**
 * The collection of active HED schemas.
 */
class Schemas {
  /**
   * Constructor.
   * @param {Schema} baseSchema The base HED schema.
   */
  constructor(baseSchema) {
    /**
     * The base HED schema.
     * @type {Schema}
     */
    this.baseSchema = baseSchema
    /**
     * The imported library HED schemas.
     * @type {Object<string, Schema>}
     */
    this.librarySchemas = {}
    /**
     * Whether this is a HED 3 schema collection.
     * @type {boolean}
     */
    this.isHed3 = baseSchema && baseSchema.isHed3
  }
}

module.exports = {
  loadSchema: loadSchema,
  setParent: setParent,
  Schema: Schema,
  Schemas: Schemas,
  fallbackFilePath: fallbackFilePath,
}
