const issueData = require('./data')

/**
 * A HED validation error or warning.
 */
class Issue {
  /**
   * Constructor.
   * @param {string} internalCode The internal error code.
   * @param {string} hedCode The HED 3 error code.
   * @param {string} level The issue level (error or warning).
   * @param {string} message The detailed error message.
   */
  constructor(internalCode, hedCode, level, message) {
    /**
     * The internal error code.
     * @type {string}
     */
    this.internalCode = internalCode
    /**
     * Also the internal error code.
     *
     * TODO: This is kept for backward compatibility until the next major version bump.
     * @type {string}
     */
    this.code = internalCode
    /**
     * The HED 3 error code.
     * @type {string}
     */
    this.hedCode = hedCode
    /**
     * The issue level (error or warning).
     * @type {string}
     */
    this.level = level
    /**
     * The detailed error message.
     * @type {string}
     */
    this.message = `${level.toUpperCase()}: [${hedCode}] ${message}`
  }
}

/**
 * Generate a new issue object.
 *
 * @param {string} internalCode The internal error code.
 * @param {object<string, (string|number[])>} parameters The error string parameters.
 * @return {Issue} An object representing the issue.
 */
const generateIssue = function (internalCode, parameters) {
  const issueCodeData = issueData[internalCode] || issueData.genericError
  const { hedCode, level, message } = issueCodeData
  const bounds = parameters.bounds || []
  const parsedMessage = message(...bounds, parameters)

  return new Issue(internalCode, hedCode, level, parsedMessage)
}

module.exports = {
  generateIssue: generateIssue,
  Issue: Issue,
}
