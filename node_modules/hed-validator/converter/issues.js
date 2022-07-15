const issuesUtil = require('../utils/issues/issues')

/**
 * Generate an issue object for tag conversion.
 *
 * This is simply a wrapper around the corresponding function in utils/issues.js
 * that handles conversion-specific functionality.
 *
 * @param {string} code The issue code.
 * @param {string} hedString The source HED string.
 * @param {object} parameters The parameters to the format string.
 * @param {number[]} bounds The bounds of the problem tag.
 * @return {Issue} The issue object.
 */
const generateIssue = function (code, hedString, parameters = {}, bounds = []) {
  parameters.tag = hedString.slice(bounds[0], bounds[1])
  parameters.bounds = bounds
  const issue = issuesUtil.generateIssue(code, parameters)
  issue.sourceString = hedString
  return issue
}

module.exports = generateIssue
