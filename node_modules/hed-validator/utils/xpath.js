// Temporary XPath implementation until the xml2js-xpath package adds needed functionality.

const childToParent = {
  unitClass: 'unitClasses',
  unitModifier: 'unitModifiers',
  unitClassDefinition: 'unitClassDefinitions',
  unitModifierDefinition: 'unitModifierDefinitions',
  schemaAttributeDefinition: 'schemaAttributeDefinitions',
}

/**
 * Execute an XPath query on an xml2js object.
 *
 * @param {object} element An xml2js element.
 * @param {string} query An XPath query.
 * @return {object[]} An array of xml2js elements matching the query.
 */
const find = function (element, query) {
  const { elementName, attributeName } = parseXPath(query)

  const searchMap = (child) => {
    return search(child, elementName, attributeName)
  }

  if (elementName in childToParent && childToParent[elementName] in element) {
    return element[childToParent[elementName]][0][elementName]
  } else if (elementName === 'node') {
    const parentElement = element.schema ? element.schema[0] : element
    const nodeList = parentElement.node || []
    return nodeList.flatMap(searchMap)
  }

  return []
}

/**
 * Parse an XPath query.
 *
 * This is a minimal parser only suitable for this package.
 *
 * @param {string} query An XPath query.
 * @return {object} The parsed search parameters.
 */
const parseXPath = function (query) {
  const nodeQuery = /^\/\/(\w+)$/
  const attributeQuery = /^\/\/(\w+)\[@(\w+)]$/

  let elementName, attributeName

  const attributeMatch = query.match(attributeQuery)
  if (attributeMatch) {
    ;[, elementName, attributeName] = attributeMatch
  } else {
    const nodeMatch = query.match(nodeQuery)
    if (nodeMatch) {
      ;[, elementName] = nodeMatch
    } else {
      return {}
    }
  }
  return { elementName: elementName, attributeName: attributeName }
}

/**
 * Search for children of an element with a given name and attribute.
 *
 * @param {object} element An xml2js element.
 * @param {string} elementName The element name.
 * @param {string} attributeName The attribute name.
 * @return {object[]} An array of xml2js elements with the given name and attribute.
 */
const search = function (element, elementName, attributeName) {
  let result = []
  if (
    attributeName === undefined ||
    ('$' in element && attributeName in element.$)
  ) {
    result.push(element)
  }
  if (elementName in element) {
    result = result.concat(
      element[elementName].flatMap((element) => {
        return search(element, elementName, attributeName)
      }),
    )
  }
  return result
}

module.exports = {
  find: find,
}
